import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app import db
from app.auth import get_current_user, login_redirect, safe_next_url
from app.categories import get_category, list_categories
from app.config import MAX_POSTS_PER_USER_PER_DAY
from app.models import ListingStatus, PostInput, PostStatus, PublisherType
from app.moderation import check_text_blocklist
from app.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def root(request: Request):
    if get_current_user(request) is not None:
        return RedirectResponse("/explorar", status_code=303)
    return templates.TemplateResponse(request, "landing.html", {"categories": list_categories()})


@router.get("/criar", response_class=HTMLResponse)
def create_form(request: Request):
    user = get_current_user(request)
    if user is None:
        return login_redirect(request)
    return templates.TemplateResponse(request, "create.html", {"categories": list_categories(), "businesses": db.list_businesses_by_user(user["user_id"])})


@router.post("/posts")
def create_post(
    request: Request,
    business: str = Form(...),
    category: str | None = Form(None),
    category_custom: str | None = Form(None),
    publish_as: str = Form("individual"),
    price_mt: float | None = Form(None),
    currency: str = Form("MZN"),
    location: str | None = Form(None),
    contact: str = Form(...),
    phone_prefix: str | None = Form(None),
    description: str | None = Form(None),
):
    user = get_current_user(request)
    if user is None:
        return JSONResponse({"error": "Sessão expirada. Entra novamente."}, status_code=401)

    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    if db.count_posts_by_user_since(user["user_id"], since) >= MAX_POSTS_PER_USER_PER_DAY:
        return JSONResponse({"error": f"Limite de {MAX_POSTS_PER_USER_PER_DAY} anúncios por dia atingido. Tenta novamente mais tarde."}, status_code=429)

    selected_business_id = None
    brand_name = None
    if publish_as != "individual":
        candidate = db.get_business(publish_as)
        if candidate is None or not db.can_manage_business(publish_as, user["user_id"]):
            return JSONResponse({"error": "Empresa inválida."}, status_code=422)
        selected_business_id = publish_as
        brand_name = candidate["name"]

    if (category_custom or "").strip():
        final_category = category_custom.strip()
    elif publish_as != "individual":
        final_category = (category or "").strip() or "outro"
    else:
        final_category = "venda_informal"

    from app.currencies import format_contact
    final_contact = format_contact(phone_prefix, contact)
    clean_business = business.strip()
    clean_description = (description or "").strip() or None

    try:
        post_input = PostInput(
            theme=clean_business,
            business=clean_business,
            category=final_category,
            publisher_type=PublisherType.BUSINESS if selected_business_id else PublisherType.INDIVIDUAL,
            brand_name=brand_name,
            target_audience="Compradores interessados",
            objective="Publicar anúncio",
            tone="direto",
            language="pt",
            call_to_action="Contactar vendedor",
            price_mt=price_mt,
            currency=currency or "MZN",
            location=location or None,
            contact=final_contact,
            phone_prefix=phone_prefix,
            color_reference=None,
            description=clean_description,
            description_source="manual" if clean_description else None,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    if check_text_blocklist(post_input.business, post_input.description or "", post_input.category):
        return JSONResponse({"error": "Conteúdo não permitido pelos Termos de Uso. Revê o texto do anúncio."}, status_code=422)

    post_id = uuid.uuid4().hex
    db.create_post(post_id, user["user_id"], selected_business_id, post_input)
    db.update_status(post_id, PostStatus.COMPLETED)
    return JSONResponse({"post_id": post_id, "status": PostStatus.COMPLETED.value}, status_code=200)


@router.get("/posts/{post_id}", response_class=HTMLResponse)
def result_page(request: Request, post_id: str):
    row = db.get_post(post_id)
    if row is None:
        return templates.TemplateResponse(request, "result.html", {"post": None, "post_id": post_id, "moderated": False}, status_code=404)

    user = get_current_user(request)
    is_owner = user is not None and user["user_id"] == row["user_id"]
    is_admin = bool(user and user["is_admin"])
    if not db.post_is_public(row) and not is_owner and not is_admin:
        return templates.TemplateResponse(request, "result.html", {"post": None, "post_id": post_id, "moderated": False}, status_code=404)

    return templates.TemplateResponse(request, "result.html", {
        "post": row,
        "post_id": post_id,
        "category": get_category(row["category"]),
        "media": db.list_product_media(post_id),
        "reactions": db.get_post_reactions(post_id, user["user_id"] if user else None),
        "comments": db.get_post_comments(post_id),
        "is_owner": is_owner,
        "current_user": user,
    })


@router.post("/posts/{post_id}/react")
def react_to_post(request: Request, post_id: str, type: str | None = Form(None), reaction_type: str | None = Form(None), reason: str | None = Form(None), return_to: str | None = Form(None)):
    user = get_current_user(request)
    wants_json = request.headers.get("x-requested-with") == "BoladasFetch" or (return_to is None and request.headers.get("referer") is None)
    if user is None:
        if not wants_json:
            return RedirectResponse(f"/entrar?next=%2Fposts%2F{post_id}", status_code=303)
        return JSONResponse({"error": "Autenticação necessária."}, status_code=401)

    row = db.get_post(post_id)
    if not db.post_is_public(row):
        return JSONResponse({"error": "Post não encontrado."}, status_code=404)

    final_type = (type or reaction_type or "").strip().lower() or "like"
    try:
        res = db.add_post_reaction(post_id, user["user_id"], final_type, reason)
        if not wants_json:
            return RedirectResponse(safe_next_url(return_to, f"/posts/{post_id}"), status_code=303)
        return JSONResponse(res)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)


@router.post("/posts/{post_id}/comments")
def add_comment(request: Request, post_id: str, body: str = Form(...), return_to: str | None = Form(None)):
    user = get_current_user(request)
    wants_json = request.headers.get("x-requested-with") == "BoladasFetch" or (return_to is None and request.headers.get("referer") is None)
    if user is None:
        if not wants_json:
            return RedirectResponse(f"/entrar?next=%2Fposts%2F{post_id}", status_code=303)
        return JSONResponse({"error": "Autenticação necessária."}, status_code=401)

    row = db.get_post(post_id)
    if not db.post_is_public(row):
        return JSONResponse({"error": "Post não encontrado."}, status_code=404)
    try:
        comment = db.add_post_comment(post_id, user["user_id"], body)
        if not wants_json:
            return RedirectResponse(safe_next_url(return_to, f"/posts/{post_id}"), status_code=303)
        return JSONResponse({"success": True, "comment": comment})
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)


@router.post("/posts/{post_id}/editar")
def edit_post(request: Request, post_id: str, theme: str = Form(...), price_mt: float | None = Form(None), contact: str = Form(...), location: str | None = Form(None), description: str | None = Form(None)):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)
    try:
        db.update_post_details(post_id, user["user_id"], theme, price_mt, contact, location, description)
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
        return RedirectResponse("/perfil?tab=produtos", status_code=303)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=403)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)


@router.post("/posts/{post_id}/estado")
def change_post_status(request: Request, post_id: str, new_status: str = Form(...)):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)
    post = db.get_post(post_id)
    if post is None or post["user_id"] != user["user_id"]:
        return RedirectResponse("/perfil?tab=produtos", status_code=303)
    try:
        listing_status = ListingStatus(new_status.strip().lower())
    except (AttributeError, ValueError):
        return JSONResponse({"error": "Estado inválido. Usa active, paused ou sold.", "allowed": [status.value for status in ListingStatus]}, status_code=422)
    if post["status"] != PostStatus.COMPLETED.value:
        return JSONResponse({"error": "A disponibilidade só pode ser alterada depois de o anúncio estar publicado."}, status_code=409)
    try:
        db.update_listing_status(post_id, listing_status)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    return RedirectResponse("/perfil?tab=produtos", status_code=303)
