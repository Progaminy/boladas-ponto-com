import io
import json
import uuid

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from PIL import Image

from app import db
from app.auth import get_current_user
from app.categories import get_category, list_categories
from app.models import PostInput, PostStatus, PublisherType
from app.pipeline import GenerationError, generate_caption, generate_image
from app.provenance import build_caption_txt, build_provenance
from app.storage import StorageError, post_key, upload_and_verify
from app.templating import templates

router = APIRouter()

THUMBNAIL_SIZE = 320


@router.get("/", response_class=HTMLResponse)
def root(request: Request):
    return RedirectResponse("/explorar", status_code=303)


@router.get("/criar", response_class=HTMLResponse)
def create_form(request: Request):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    business = db.get_business_by_user(user["user_id"])
    return templates.TemplateResponse(
        request, "create.html", {"categories": list_categories(), "business": business}
    )


@router.post("/posts")
def create_post(
    request: Request,
    theme: str = Form(...),
    business: str = Form(...),
    category: str = Form(...),
    publisher_type: str = Form(...),
    brand_name: str | None = Form(None),
    target_audience: str = Form(...),
    objective: str = Form(...),
    tone: str = Form(...),
    language: str = Form("pt"),
    call_to_action: str = Form(...),
    price_mt: float | None = Form(None),
    location: str | None = Form(None),
    contact: str = Form(...),
    color_reference: str | None = Form(None),
):
    user = get_current_user(request)
    if user is None:
        return JSONResponse({"error": "Sessão expirada. Entra novamente."}, status_code=401)

    try:
        post_input = PostInput(
            theme=theme,
            business=business,
            category=category,
            publisher_type=PublisherType(publisher_type),
            brand_name=brand_name or None,
            target_audience=target_audience,
            objective=objective,
            tone=tone,
            language=language,
            call_to_action=call_to_action,
            price_mt=price_mt,
            location=location or None,
            contact=contact,
            color_reference=color_reference or None,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    user_business = db.get_business_by_user(user["user_id"])
    business_id = (
        user_business["business_id"]
        if user_business and post_input.publisher_type == PublisherType.BUSINESS
        else None
    )

    post_id = uuid.uuid4().hex
    db.create_post(post_id, user["user_id"], business_id, post_input)

    result = _run_generation(post_id, post_input)
    return JSONResponse(result, status_code=200 if result["status"] == "completed" else 502)


def _run_generation(post_id: str, post_input: PostInput) -> dict:
    category = get_category(post_input.category)

    db.update_status(post_id, PostStatus.GENERATING)
    try:
        image_result = generate_image(post_input, category)
        caption_result = generate_caption(post_input, category)
    except GenerationError as exc:
        db.update_status(post_id, PostStatus.FAILED, error=str(exc))
        return {"post_id": post_id, "status": PostStatus.FAILED.value, "error": str(exc)}

    db.update_status(post_id, PostStatus.UPLOADING)
    try:
        image_file = upload_and_verify(
            post_key(post_id, "image.png"), image_result.bytes_, "image/png"
        )
        caption_txt = build_caption_txt(caption_result)
        caption_file = upload_and_verify(
            post_key(post_id, "caption.txt"), caption_txt.encode("utf-8"), "text/plain"
        )

        thumbnail_key = None
        try:
            thumb_bytes = _make_thumbnail(image_result.bytes_)
            thumb_file = upload_and_verify(
                post_key(post_id, "thumbnail.webp"), thumb_bytes, "image/webp"
            )
            thumbnail_key = thumb_file.key
        except StorageError:
            thumbnail_key = None  # miniatura é best-effort; não bloqueia o post

        provenance_doc = build_provenance(
            post_id=post_id,
            status=PostStatus.COMPLETED.value,
            post_input=post_input,
            image_result=image_result,
            caption_result=caption_result,
            image_file=image_file,
            caption_file=caption_file,
        )
        provenance_file = upload_and_verify(
            post_key(post_id, "provenance.json"),
            json.dumps(provenance_doc, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json",
        )
    except StorageError as exc:
        db.update_status(post_id, PostStatus.FAILED, error=str(exc))
        return {"post_id": post_id, "status": PostStatus.FAILED.value, "error": str(exc)}

    db.save_generation_result(
        post_id,
        caption=caption_result.caption,
        call_to_action_generated=caption_result.call_to_action,
        hashtags=caption_result.hashtags,
        image_key=image_file.key,
        caption_key=caption_file.key,
        provenance_key=provenance_file.key,
        thumbnail_key=thumbnail_key,
        image_url=image_file.url,
    )
    db.update_status(post_id, PostStatus.COMPLETED)

    return {"post_id": post_id, "status": PostStatus.COMPLETED.value}


def _make_thumbnail(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    img = img.resize((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=80)
    return out.getvalue()


@router.get("/posts/{post_id}", response_class=HTMLResponse)
def result_page(request: Request, post_id: str):
    if get_current_user(request) is None:
        return RedirectResponse("/entrar", status_code=303)

    row = db.get_post(post_id)
    if row is None:
        return templates.TemplateResponse(
            request, "result.html", {"post": None, "post_id": post_id}, status_code=404
        )
    category = get_category(row["category"])
    return templates.TemplateResponse(
        request, "result.html", {"post": row, "post_id": post_id, "category": category}
    )
