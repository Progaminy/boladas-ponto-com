import io
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from PIL import Image

from app import db
from app.auth import get_current_user
from app.categories import get_category, list_categories
from app.category_classify import suggest_category
from app.config import MAX_POSTS_PER_USER_PER_DAY
from app.describe import DescriptionError, describe_from_image, describe_from_text
from app.image_compose import add_business_overlay
from app.media_validate import MediaValidationError, validate_photo
from app.models import PostInput, PostStatus, PublisherType
from app.moderation import check_text_blocklist, check_text_with_ai
from app.pipeline import GenerationError, build_fallback_caption, generate_caption, generate_image
from app.provenance import build_caption_txt, build_provenance
from app.storage import StorageError, post_key, upload_and_verify
from app.templating import templates

router = APIRouter()

THUMBNAIL_SIZE = 320


@router.get("/", response_class=HTMLResponse)
def root(request: Request, categoria: str | None = None, local: str | None = None):
    rows = db.list_public_posts(category=categoria or None, location_query=local or None)
    posts = [{"row": row, "category": get_category(row["category"])} for row in rows]
    return templates.TemplateResponse(
        request, "explore.html",
        {
            "posts": posts,
            "categories": list_categories(),
            "selected_category": categoria or "",
            "location_query": local or "",
        },
    )


@router.get("/criar", response_class=HTMLResponse)
def create_form(request: Request):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    businesses = db.list_businesses_by_user(user["user_id"])
    return templates.TemplateResponse(
        request, "create.html", {"categories": list_categories(), "businesses": businesses}
    )


@router.post("/categoria/sugerir")
def suggest_category_endpoint(request: Request, description: str = Form(...)):
    if get_current_user(request) is None:
        return JSONResponse({"error": "Sessão expirada."}, status_code=401)

    slug = suggest_category(description)
    if slug is None:
        return JSONResponse(
            {
                "error": (
                    "Sugestão automática indisponível. Verifica o acesso à IA "
                    "em /estado, ou escolhe a categoria manualmente."
                )
            },
            status_code=503,
        )
    return JSONResponse({"slug": slug, "label": get_category(slug).label})


@router.post("/descricao/sugerir")
async def suggest_description_endpoint(
    request: Request,
    explicacao: str | None = Form(None),
    foto: UploadFile | None = File(default=None),
):
    """Gera a descrição do produto a partir de uma fotografia real ou de uma
    explicação escrita à pressa. Quem preferir escreve à mão e não passa por
    aqui."""
    if get_current_user(request) is None:
        return JSONResponse({"error": "Sessão expirada."}, status_code=401)

    tem_foto = foto is not None and bool(foto.filename)
    try:
        if tem_foto:
            dados = await foto.read()
            validate_photo(dados, foto.content_type)
            texto = describe_from_image(
                dados, foto.content_type, contexto=explicacao or ""
            )
            origem = "ia_foto"
        else:
            texto = describe_from_text(explicacao or "")
            origem = "ia_texto"
    except MediaValidationError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    except DescriptionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)

    return JSONResponse({"description": texto, "source": origem})


@router.post("/posts")
def create_post(
    request: Request,
    theme: str | None = Form(None),
    business: str = Form(...),
    category: str | None = Form(None),
    category_custom: str | None = Form(None),
    publish_as: str = Form("individual"),
    target_audience: str | None = Form(None),
    objective: str | None = Form(None),
    tone: str | None = Form(None),
    language: str = Form("pt"),
    call_to_action: str | None = Form(None),
    price_mt: float | None = Form(None),
    location: str | None = Form(None),
    contact: str = Form(...),
    color_reference: str | None = Form(None),
    description: str | None = Form(None),
    description_source: str | None = Form(None),
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

    selected_business_id = None
    brand_name = None
    if publish_as != "individual":
        candidate = db.get_business(publish_as)
        if candidate is None or candidate["user_id"] != user["user_id"]:
            return JSONResponse({"error": "Empresa inválida."}, status_code=422)
        selected_business_id = publish_as
        brand_name = candidate["name"]
    if (category_custom or "").strip():
        final_category = category_custom.strip()
    elif publish_as != "individual":
        final_category = (category or "").strip() or "outro"
    else:
        final_category = "venda_informal"

    # Modo simples (publicação individual/eventual): campos avançados ficam
    # colapsados no formulário com valores pré-preenchidos; isto garante os
    # mesmos valores por omissão também para quem submeter sem JS/via API.
    final_theme = (theme or "").strip() or business
    final_target_audience = (target_audience or "").strip() or "Pessoas interessadas em comprar"
    final_objective = (objective or "").strip() or "Vender rapidamente"
    final_tone = (tone or "").strip() or "casual e direto"
    final_call_to_action = (call_to_action or "").strip() or "Contacta-me já!"

    try:
        post_input = PostInput(
            theme=final_theme,
            business=business,
            category=final_category,
            publisher_type=PublisherType.BUSINESS if selected_business_id else PublisherType.INDIVIDUAL,
            brand_name=brand_name,
            target_audience=final_target_audience,
            objective=final_objective,
            tone=final_tone,
            language=language,
            call_to_action=final_call_to_action,
            price_mt=price_mt,
            location=location or None,
            contact=contact,
            color_reference=color_reference or None,
            description=(description or "").strip() or None,
            # se veio texto mas sem origem declarada, foi escrito à mão
            description_source=(description_source or "manual")
            if (description or "").strip()
            else None,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    moderation_texts = (
        post_input.theme, post_input.business, post_input.target_audience,
        post_input.objective, post_input.call_to_action,
    )

    # 1ª camada: lista de bloqueio local, sem custo, antes de gastar geração.
    blocked_terms = check_text_blocklist(*moderation_texts)
    if blocked_terms:
        return JSONResponse(
            {"error": "Conteúdo não permitido pelos Termos de Uso. Revê o texto do post."},
            status_code=422,
        )

    # 2ª camada: classificação por IA. Devolve None quando não conseguiu
    # verificar — nesse caso seguimos em frente, porque "não verificado" não
    # é motivo para bloquear um anúncio legítimo (o reporte cobre o resto).
    ai_check = check_text_with_ai(*moderation_texts)
    if ai_check and ai_check["flagged"]:
        return JSONResponse(
            {
                "error": (
                    "O conteúdo foi sinalizado pela moderação: "
                    + (ai_check["reason"] or "possível violação")
                )
            },
            status_code=422,
        )

    post_id = uuid.uuid4().hex
    db.create_post(post_id, user["user_id"], selected_business_id, post_input)

    result = _run_generation(post_id, post_input)
    return JSONResponse(result, status_code=200 if result["status"] == "completed" else 502)


def _run_generation(post_id: str, post_input: PostInput) -> dict:
    category = get_category(post_input.category)

    db.update_status(post_id, PostStatus.GENERATING)

    caption_result = None
    caption_skipped_reason = None
    try:
        caption_result = generate_caption(post_input, category)
    except Exception as exc:
        caption_skipped_reason = str(exc)
        caption_result = build_fallback_caption(post_input, category)

    image_result = None
    image_skipped_reason = None
    try:
        image_result = generate_image(post_input, category)
    except Exception as exc:
        image_skipped_reason = str(exc)

    db.update_status(post_id, PostStatus.UPLOADING)
    try:
        image_file = None
        thumbnail_key = None
        if image_result is not None:
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
            try:
                thumb_bytes = _make_thumbnail(final_image_bytes)
                thumb_file = upload_and_verify(
                    post_key(post_id, "thumbnail.webp"), thumb_bytes, "image/webp"
                )
                thumbnail_key = thumb_file.key
            except Exception:
                thumbnail_key = None  # miniatura é best-effort; não bloqueia o post

        caption_txt = build_caption_txt(caption_result)
        caption_file = upload_and_verify(
            post_key(post_id, "caption.txt"), caption_txt.encode("utf-8"), "text/plain"
        )

        provenance_doc = build_provenance(
            post_id=post_id,
            status=PostStatus.COMPLETED.value,
            post_input=post_input,
            image_result=image_result,
            caption_result=caption_result,
            image_file=image_file,
            caption_file=caption_file,
            image_skipped_reason=image_skipped_reason,
            caption_skipped_reason=caption_skipped_reason,
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
        image_key=image_file.key if image_file else None,
        caption_key=caption_file.key,
        provenance_key=provenance_file.key,
        thumbnail_key=thumbnail_key,
        image_url=image_file.url if image_file else None,
        image_skipped_reason=image_skipped_reason,
    )
    db.update_status(post_id, PostStatus.COMPLETED)

    return {
        "post_id": post_id,
        "status": PostStatus.COMPLETED.value,
        "image_skipped_reason": image_skipped_reason,
    }


def _make_thumbnail(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    img = img.resize((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=80)
    return out.getvalue()


@router.get("/posts/{post_id}", response_class=HTMLResponse)
def result_page(request: Request, post_id: str):
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
    reactions = db.get_post_reactions(post_id, user["user_id"] if user else None)
    comments = db.get_post_comments(post_id)

    return templates.TemplateResponse(
        request, "result.html",
        {
            "post": row,
            "post_id": post_id,
            "category": category,
            "media": media,
            "reactions": reactions,
            "comments": comments,
            "is_owner": is_owner,
            "current_user": user,
        },
    )


@router.post("/posts/{post_id}/react")
def react_to_post(
    request: Request,
    post_id: str,
    type: str | None = Form(None),
    reaction_type: str | None = Form(None),
    reason: str | None = Form(None),
):
    user = get_current_user(request)
    if user is None:
        referer = request.headers.get("referer")
        if referer:
            return RedirectResponse("/entrar", status_code=303)
        return JSONResponse({"error": "Autenticação necessária."}, status_code=401)

    final_type = (type or reaction_type or "").strip().lower()
    if not final_type:
        final_type = "like"

    try:
        res = db.add_post_reaction(post_id, user["user_id"], final_type, reason)
        referer = request.headers.get("referer")
        if referer:
            return RedirectResponse(referer, status_code=303)
        return JSONResponse(res)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)


@router.post("/posts/{post_id}/comments")
def add_comment(
    request: Request,
    post_id: str,
    body: str = Form(...),
):
    user = get_current_user(request)
    if user is None:
        referer = request.headers.get("referer")
        if referer:
            return RedirectResponse("/entrar", status_code=303)
        return JSONResponse({"error": "Autenticação necessária."}, status_code=401)

    try:
        comment = db.add_post_comment(post_id, user["user_id"], body)
        referer = request.headers.get("referer")
        if referer:
            return RedirectResponse(referer, status_code=303)
        return JSONResponse({"success": True, "comment": comment})
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)


@router.post("/posts/{post_id}/editar")
def edit_post(
    request: Request,
    post_id: str,
    theme: str = Form(...),
    price_mt: float | None = Form(None),
    contact: str = Form(...),
    location: str | None = Form(None),
    description: str | None = Form(None),
):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    try:
        db.update_post_details(
            post_id, user["user_id"], theme, price_mt, contact, location, description
        )
        return RedirectResponse(f"/posts/{post_id}", status_code=303)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=403)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)


@router.post("/posts/{post_id}/eliminar")
def delete_post_endpoint(request: Request, post_id: str):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    try:
        db.delete_post(post_id, user["user_id"])
        return RedirectResponse("/historico", status_code=303)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=403)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)

