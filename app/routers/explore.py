from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.auth import get_current_user
from app.categories import get_category, list_categories
from app.templating import templates

router = APIRouter()


@router.get("/explorar", response_class=HTMLResponse)
def explore(request: Request, categoria: str | None = None, local: str | None = None):
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
