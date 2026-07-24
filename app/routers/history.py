from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.auth import get_current_user
from app.categories import get_category
from app.templating import templates

router = APIRouter()


@router.get("/historico", response_class=HTMLResponse)
def history_page(request: Request):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    rows = db.list_posts_by_user(user["user_id"])
    posts = [{"row": row, "category": get_category(row["category"])} for row in rows]
    return templates.TemplateResponse(request, "history.html", {"posts": posts})
