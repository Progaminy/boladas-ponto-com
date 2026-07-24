import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.auth import get_current_user
from app.storage import get_backend
from app.templating import templates

router = APIRouter()


@router.get("/posts/{post_id}/provenance", response_class=HTMLResponse)
def provenance_page(request: Request, post_id: str):
    if get_current_user(request) is None:
        return RedirectResponse("/entrar", status_code=303)

    row = db.get_post(post_id)
    if row is None:
        return templates.TemplateResponse(
            request, "provenance.html",
            {"post_id": post_id, "post": None, "provenance": None, "fetch_error": "Post não encontrado."},
            status_code=404,
        )

    provenance = None
    fetch_error = None
    if row["provenance_key"]:
        try:
            backend = get_backend()
            raw = backend.get(row["provenance_key"])
            provenance = json.loads(raw)
        except Exception as exc:  # nunca finge: mostra o erro real, seja qual for a causa
            fetch_error = f"Não foi possível obter o provenance.json real do B2: {exc}"
    else:
        fetch_error = "Este post ainda não tem proveniência armazenada no B2."

    return templates.TemplateResponse(
        request,
        "provenance.html",
        {"post_id": post_id, "post": row, "provenance": provenance, "fetch_error": fetch_error},
    )
