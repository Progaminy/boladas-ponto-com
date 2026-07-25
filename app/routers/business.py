import uuid

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app import db
from app.auth import get_current_user
from app.categories import get_category, list_categories
from app.models import BusinessInput
from app.templating import templates

router = APIRouter()


@router.get("/empresa", response_class=HTMLResponse)
def business_list(request: Request):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    businesses = db.list_businesses_by_user(user["user_id"])
    return templates.TemplateResponse(request, "business_list.html", {"businesses": businesses})


@router.get("/empresa/nova", response_class=HTMLResponse)
def business_new_form(request: Request):
    if get_current_user(request) is None:
        return RedirectResponse("/entrar", status_code=303)

    return templates.TemplateResponse(
        request, "business_form.html",
        {"business": None, "categories": list_categories(), "error": None},
    )


@router.post("/empresa/nova", response_class=HTMLResponse)
def business_create(
    request: Request,
    name: str = Form(...),
    category: str = Form(...),
    category_custom: str | None = Form(None),
    description: str | None = Form(None),
    location: str | None = Form(None),
    contact: str = Form(...),
):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    final_category = (category_custom or "").strip() or category
    try:
        data = BusinessInput(
            name=name, category=final_category, description=description or None,
            location=location or None, contact=contact,
        )
    except ValidationError as exc:
        return templates.TemplateResponse(
            request, "business_form.html",
            {"business": None, "categories": list_categories(), "error": exc.errors()[0]["msg"]},
            status_code=422,
        )

    business_id = uuid.uuid4().hex
    db.create_business(business_id, user["user_id"], data)
    return RedirectResponse(f"/negocio/{business_id}", status_code=303)


@router.get("/empresa/{business_id}/editar", response_class=HTMLResponse)
def business_edit_form(request: Request, business_id: str):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    biz = db.get_business(business_id)
    if biz is None or biz["user_id"] != user["user_id"]:
        return RedirectResponse("/empresa", status_code=303)

    return templates.TemplateResponse(
        request, "business_form.html",
        {"business": biz, "categories": list_categories(), "error": None},
    )


@router.post("/empresa/{business_id}/editar", response_class=HTMLResponse)
def business_update(
    request: Request,
    business_id: str,
    name: str = Form(...),
    category: str = Form(...),
    category_custom: str | None = Form(None),
    description: str | None = Form(None),
    location: str | None = Form(None),
    contact: str = Form(...),
):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    biz = db.get_business(business_id)
    if biz is None or biz["user_id"] != user["user_id"]:
        return RedirectResponse("/empresa", status_code=303)

    final_category = (category_custom or "").strip() or category
    try:
        data = BusinessInput(
            name=name, category=final_category, description=description or None,
            location=location or None, contact=contact,
        )
    except ValidationError as exc:
        return templates.TemplateResponse(
            request, "business_form.html",
            {"business": biz, "categories": list_categories(), "error": exc.errors()[0]["msg"]},
            status_code=422,
        )

    db.update_business(business_id, data)
    return RedirectResponse(f"/negocio/{business_id}", status_code=303)


@router.get("/negocio/{business_id}", response_class=HTMLResponse)
def business_profile(request: Request, business_id: str):
    if get_current_user(request) is None:
        return RedirectResponse("/entrar", status_code=303)

    biz = db.get_business(business_id)
    if biz is None:
        return templates.TemplateResponse(
            request, "business_profile.html", {"business": None, "posts": []}, status_code=404
        )

    posts = db.list_posts_by_business(business_id)
    category = get_category(biz["category"])
    return templates.TemplateResponse(
        request, "business_profile.html", {"business": biz, "posts": posts, "category": category}
    )
