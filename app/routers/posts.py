import io
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from PIL import Image

from app import db
from app.auth import get_current_user
from app.categories import get_category, list_categories
from app.config import MAX_POSTS_PER_USER_PER_DAY
from app.image_compose import add_business_overlay
from app.models import PostInput, PostStatus, PublisherType
from app.moderation import check_text_blocklist
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

    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    recent_count = db.count_posts_by_user_since(user["user_id"], since)
    if recent_count >= MAX_POSTS_PER_USER_PER_DAY:
        return JSONResponse(
            {
                "error": (
                    f"Limite de {MAX_POSTS_PER_USER_PER_DAY} posts por dia atingido. "
                    "Tenta novamente mais tarde."
                )
            },
            status_code=429,
        )

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

    blocked_terms = check_text_blocklist(
        post_input.theme, post_input.business, post_input.target_audience,
        post_input.objective, post_input.call_to_action,
    )
    if blocked_terms:
        return JSONResponse(
            {"error": "Conteúdo não permitido pelos Termos de Uso. Revê o texto do post."},
            status_code=422,
        )

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
    except Exception as exc:  # nunca deixar um post preso em "generating"
        error = f"Falha inesperada na geração ({type(exc).__name__}): {exc}"
        db.update_status(post_id, PostStatus.FAILED, error=error)
        return {"post_id": post_id, "status": PostStatus.FAILED.value, "error": error}

    db.update_status(post_id, PostStatus.UPLOADING)
    try:
        final_image_bytes = add_business_overlay(
            image_result.bytes_,
            category=category,
            business_name=post_input.brand_name or post_input.business,
            price_mt=post_input.price_mt,
            call_to_action=caption_result.call_to_action,
        )
        image_file = upload_and_verify(
            post_key(post_id, "image.png"), final_image_bytes, "image/png"
        )
        caption_txt = build_caption_txt(caption_result)
        caption_file = upload_and_verify(
            post_key(post_id, "caption.txt"), caption_txt.encode("utf-8"), "text/plain"
        )

        thumbnail_key = None
        try:
            thumb_bytes = _make_thumbnail(final_image_bytes)
            thumb_file = upload_and_verify(
                post_key(post_id, "thumbnail.webp"), thumb_bytes, "image/webp"
            )
            thumbnail_key = thumb_file.key
        except Exception:
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
    except Exception as exc:  # nunca deixar um post preso em "uploading"
        error = f"Falha inesperada no armazenamento ({type(exc).__name__}): {exc}"
        db.update_status(post_id, PostStatus.FAILED, error=error)
        return {"post_id": post_id, "status": PostStatus.FAILED.value, "error": error}

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
    # Público de propósito: um post tem de poder ser partilhado (WhatsApp,
    # redes sociais) e a sua proveniência verificada sem exigir conta.
    row = db.get_post(post_id)
    if row is None:
        return templates.TemplateResponse(
            request, "result.html", {"post": None, "post_id": post_id, "moderated": False},
            status_code=404,
        )

    user = get_current_user(request)
    is_owner = user is not None and user["user_id"] == row["user_id"]
    is_admin = bool(user and user["is_admin"])

    if row["moderation_status"] != "approved" and not is_owner and not is_admin:
        return templates.TemplateResponse(
            request, "result.html", {"post": None, "post_id": post_id, "moderated": True},
            status_code=403,
        )

    category = get_category(row["category"])
    media = db.list_product_media(post_id)
    return templates.TemplateResponse(
        request, "result.html",
        {"post": row, "post_id": post_id, "category": category, "media": media},
    )
