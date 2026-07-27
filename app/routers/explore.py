from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.auth import get_current_user
from app.categories import get_category, list_categories
from app.templating import templates

router = APIRouter()


@router.get("/explorar", response_class=HTMLResponse)
def explore(request: Request, categoria: str | None = None, local: str | None = None):
    current_user = get_current_user(request)
    if current_user is None:
        return RedirectResponse("/entrar", status_code=303)

    rows = db.list_public_posts(category=categoria or None, location_query=local or None)

    user_id = current_user["user_id"]
    posts = []
    for row in rows:
        post_id = row["post_id"]
        reactions = db.get_post_reactions(post_id, user_id)
        comments = db.get_post_comments(post_id)
        posts.append({
            "row": row,
            "category": get_category(row["category"]),
            "reactions": reactions,
            "comments": comments,
        })

    return templates.TemplateResponse(
        request, "explore.html",
        {
            "posts": posts,
            "categories": list_categories(),
            "selected_category": categoria or "",
            "location_query": local or "",
        },
    )
