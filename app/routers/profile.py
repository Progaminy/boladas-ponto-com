"""Perfil pessoal autenticado e fotos de perfil/capa — uma pessoal (conta) e
uma por cada empresa que o utilizador registar."""

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.auth import get_current_user
from app.media_validate import MediaValidationError, validate_photo
from app.storage import StorageError, business_key, upload_and_verify, user_key
from app.templating import templates

router = APIRouter()


@router.get("/perfil", response_class=HTMLResponse)
def my_profile_redirect(request: Request):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)
    tab = request.query_params.get("tab") or "produtos"
    created = request.query_params.get("created")
    url = f"/utilizador/{user['user_id']}?tab={tab}"
    if created:
        url += f"&created={created}"
    return RedirectResponse(url, status_code=303)


@router.get("/utilizador/{user_id}", response_class=HTMLResponse)
def user_profile(request: Request, user_id: str):
    current_user = get_current_user(request)
    if current_user is None:
        return RedirectResponse("/entrar", status_code=303)

    profile_user = db.get_user_by_id(user_id)
    if profile_user is None:
        return templates.TemplateResponse(
            request, "user_profile.html", {"profile_user": None, "posts": [], "businesses": []},
            status_code=404,
        )

    is_owner = current_user["user_id"] == user_id
    active_tab = request.query_params.get("tab") or "produtos"
    created_id = request.query_params.get("created")

    if is_owner:
        posts = db.list_posts_by_user(user_id)
        raw_txs = db.list_transactions_for_user(user_id)
        transactions = []
        for tx in raw_txs:
            tx_post = db.get_post(tx["post_id"])
            other_id = tx["seller_id"] if tx["buyer_id"] == user_id else tx["buyer_id"]
            other_u = db.get_user_by_id(other_id)
            transactions.append({
                "tx": tx,
                "post": tx_post,
                "role": "buyer" if tx["buyer_id"] == user_id else "seller",
                "other_user": other_u,
            })
    else:
        posts = db.list_public_individual_posts_by_user(user_id)
        transactions = []

    businesses = db.list_businesses_by_user(user_id)

    from app.currencies import list_currencies, list_phone_prefixes

    return templates.TemplateResponse(
        request, "user_profile.html",
        {
            "profile_user": profile_user,
            "is_owner": is_owner,
            "posts": posts,
            "businesses": businesses,
            "transactions": transactions,
            "active_tab": active_tab,
            "created_id": created_id,
            "currencies": list_currencies(),
            "phone_prefixes": list_phone_prefixes(),
        },
    )


@router.get("/perfil/fotos", response_class=HTMLResponse)
def my_photos_form(request: Request):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    return templates.TemplateResponse(request, "photos_form.html", {"error": None, "target": "user"})


@router.post("/perfil/fotos")
async def my_photos_upload(
    request: Request,
    profile_photo: UploadFile | None = File(default=None),
    cover_photo: UploadFile | None = File(default=None),
):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    error = await _handle_photo_uploads(
        profile_photo, cover_photo,
        key_fn=lambda filename: user_key(user["user_id"], filename),
        save_fn=lambda kind, key, url: db.set_user_photo(user["user_id"], kind, key, url),
    )
    if error:
        return templates.TemplateResponse(
            request, "photos_form.html", {"error": error, "target": "user"}, status_code=422
        )
    return RedirectResponse(f"/utilizador/{user['user_id']}", status_code=303)


@router.get("/empresa/{business_id}/fotos", response_class=HTMLResponse)
def business_photos_form(request: Request, business_id: str):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    biz = db.get_business(business_id)
    if biz is None or not db.can_manage_business(business_id, user["user_id"]):
        return RedirectResponse("/empresa", status_code=303)

    return templates.TemplateResponse(
        request, "photos_form.html", {"error": None, "target": "business", "business": biz}
    )


@router.post("/empresa/{business_id}/fotos")
async def business_photos_upload(
    request: Request,
    business_id: str,
    profile_photo: UploadFile | None = File(default=None),
    cover_photo: UploadFile | None = File(default=None),
):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    biz = db.get_business(business_id)
    if biz is None or not db.can_manage_business(business_id, user["user_id"]):
        return RedirectResponse("/empresa", status_code=303)

    error = await _handle_photo_uploads(
        profile_photo, cover_photo,
        key_fn=lambda filename: business_key(business_id, filename),
        save_fn=lambda kind, key, url: db.set_business_photo(business_id, kind, key, url),
    )
    if error:
        return templates.TemplateResponse(
            request, "photos_form.html",
            {"error": error, "target": "business", "business": biz}, status_code=422,
        )
    return RedirectResponse(f"/negocio/{business_id}", status_code=303)


_EXT_BY_CONTENT_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


async def _handle_photo_uploads(profile_photo, cover_photo, *, key_fn, save_fn) -> str | None:
    for kind, upload in (("profile", profile_photo), ("cover", cover_photo)):
        if upload is None or not upload.filename:
            continue
        data = await upload.read()
        try:
            validate_photo(data, upload.content_type)
        except MediaValidationError as exc:
            return str(exc)
        ext = _EXT_BY_CONTENT_TYPE.get(upload.content_type, "jpg")
        key = key_fn(f"{kind}.{ext}")
        try:
            uploaded = upload_and_verify(key, data, upload.content_type)
        except StorageError as exc:
            return f"Falha ao guardar no B2: {exc}"
        save_fn(kind, uploaded.key, uploaded.url)
    return None


@router.post("/perfil/tema")
def set_user_theme(request: Request, theme: str = Form("padrao")):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)
    db.set_user_seasonal_theme(user["user_id"], theme)
    return RedirectResponse(f"/utilizador/{user['user_id']}", status_code=303)


@router.post("/empresa/{business_id}/tema")
def set_business_theme(request: Request, business_id: str, theme: str = Form("padrao")):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)
    try:
        db.set_business_seasonal_theme(business_id, user["user_id"], theme)
    except PermissionError:
        pass
    return RedirectResponse(f"/negocio/{business_id}", status_code=303)
