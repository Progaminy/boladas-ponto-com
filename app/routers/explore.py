from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import db
from app.auth import get_current_user, login_redirect
from app.categories import get_category, list_categories
from app.templating import templates

router = APIRouter()


@router.get("/explorar", response_class=HTMLResponse)
def explore(request: Request, categoria: str | None = None, local: str | None = None):
    # O feed é público: quem chega tem de poder ver o que se vende antes de
    # decidir criar conta. Publicar, reagir, comentar e contactar continuam
    # a exigir sessão — o que se protege é agir, não olhar.
    current_user = get_current_user(request)

    rows = db.list_public_posts(category=categoria or None, location_query=local or None)

    user_id = current_user["user_id"] if current_user else None
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
