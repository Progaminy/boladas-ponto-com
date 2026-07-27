"""Reportar conteúdo (qualquer utilizador) + fila de revisão humana (admin).

Não há moderação visual automática (sem API de visão verificada) — reportar
é o mecanismo que cobre fotos/vídeo e qualquer texto que passe a lista de
bloqueio. Um post reportado fica oculto do público até um admin decidir."""

import uuid

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.auth import get_current_user
from app.templating import templates

router = APIRouter()


@router.post("/posts/{post_id}/reportar")
def report_post(request: Request, post_id: str, reason: str = Form(...)):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    post = db.get_post(post_id)
    if not db.post_is_public(post):
        return RedirectResponse("/explorar", status_code=303)

    if post["user_id"] != user["user_id"]:
        reason = reason.strip()[:500] or "Sem motivo indicado."
        db.create_report(uuid.uuid4().hex, post_id, user["user_id"], reason)
        db.set_post_moderation_status(post_id, "reported")

    return RedirectResponse(f"/posts/{post_id}", status_code=303)


def _require_admin(request: Request):
    user = get_current_user(request)
    if user is None:
        return None, RedirectResponse("/entrar", status_code=303)
    if not user["is_admin"]:
        return None, RedirectResponse("/explorar", status_code=303)
    return user, None


@router.get("/admin/moderacao", response_class=HTMLResponse)
def moderation_queue(request: Request):
    user, redirect = _require_admin(request)
    if redirect:
        return redirect

    reports = db.list_open_reports()
    items = [{"report": r, "post": db.get_post(r["post_id"])} for r in reports]
    return templates.TemplateResponse(request, "admin_moderation.html", {"items": items})


@router.post("/admin/moderacao/{report_id}/resolver")
def moderation_resolve(request: Request, report_id: str, decision: str = Form(...)):
    user, redirect = _require_admin(request)
    if redirect:
        return redirect

    report = db.get_report(report_id)
    if report is None:
        return RedirectResponse("/admin/moderacao", status_code=303)

    if decision == "aprovar":
        db.set_post_moderation_status(report["post_id"], "approved")
        db.resolve_report(report_id, user["user_id"], "approved")
    elif decision == "bloquear":
        db.set_post_moderation_status(report["post_id"], "blocked")
        db.resolve_report(report_id, user["user_id"], "blocked")

    return RedirectResponse("/admin/moderacao", status_code=303)
