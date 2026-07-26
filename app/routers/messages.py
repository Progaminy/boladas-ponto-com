"""'Boladas Message' — contacto interno ligado ao post/produto em causa, e
canal para contactar a equipa da plataforma para ajuda/mediação. Não envolve
dinheiro: é só comunicação (ver app/db.py para o modelo de dados)."""

import uuid

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.auth import get_current_user
from app.templating import templates

router = APIRouter()


def _group_conversations(messages: list, user_id: str) -> list[dict]:
    groups: dict[tuple, list] = {}
    for m in messages:
        other = m["recipient_id"] if m["sender_id"] == user_id else m["sender_id"]
        key = (m["post_id"], other)
        groups.setdefault(key, []).append(m)

    conversations = []
    for (post_id, other_id), msgs in groups.items():
        last = msgs[-1]
        unread = sum(1 for m in msgs if m["recipient_id"] == user_id and m["read_at"] is None)
        post = db.get_post(post_id) if post_id else None
        other_user = db.get_user_by_id(other_id) if other_id else None
        conversations.append({
            "post_id": post_id,
            "other_user_id": other_id,
            "post_theme": post["theme"] if post else None,
            "other_name": other_user["display_name"] if other_user else "Equipa Boladas",
            "last_body": last["body"],
            "last_created_at": last["created_at"],
            "unread": unread,
        })
    conversations.sort(key=lambda c: c["last_created_at"], reverse=True)
    return conversations


@router.get("/mensagens", response_class=HTMLResponse)
def inbox(request: Request):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    messages = db.list_messages_for_user(user["user_id"])
    conversations = _group_conversations(messages, user["user_id"])
    return templates.TemplateResponse(request, "inbox.html", {"conversations": conversations})


@router.get("/mensagens/plataforma", response_class=HTMLResponse)
def platform_thread(request: Request):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    thread = db.list_thread(user["user_id"], None, None)
    return templates.TemplateResponse(
        request, "thread.html",
        {"thread": thread, "post": None, "other_user": None, "is_platform": True},
    )


@router.post("/mensagens/plataforma")
def platform_thread_reply(request: Request, body: str = Form(...)):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    body = body.strip()
    if body:
        db.create_message(uuid.uuid4().hex, None, user["user_id"], None, body)
    return RedirectResponse("/mensagens/plataforma", status_code=303)


@router.get("/mensagens/posto/{post_id}/{other_user_id}", response_class=HTMLResponse)
def post_thread(request: Request, post_id: str, other_user_id: str):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    post = db.get_post(post_id)
    other_user = db.get_user_by_id(other_user_id)
    if post is None or other_user is None:
        return templates.TemplateResponse(
            request, "thread.html",
            {"thread": [], "post": None, "other_user": None, "is_platform": False},
            status_code=404,
        )

    db.mark_thread_read(user["user_id"], post_id, other_user_id)
    thread = db.list_thread(user["user_id"], post_id, other_user_id)
    return templates.TemplateResponse(
        request, "thread.html",
        {"thread": thread, "post": post, "other_user": other_user, "is_platform": False},
    )


@router.post("/mensagens/posto/{post_id}/{other_user_id}")
def post_thread_reply(request: Request, post_id: str, other_user_id: str, body: str = Form(...)):
    """Responde dentro de uma conversa já existente sobre um post — funciona
    em ambos os sentidos (comprador → vendedor e vendedor → comprador),
    porque o destinatário vem explícito na URL, não é sempre o dono do post."""
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    if db.get_post(post_id) is None or db.get_user_by_id(other_user_id) is None:
        return RedirectResponse("/mensagens", status_code=303)

    body = body.strip()
    if body:
        db.create_message(uuid.uuid4().hex, post_id, user["user_id"], other_user_id, body)

    return RedirectResponse(f"/mensagens/posto/{post_id}/{other_user_id}", status_code=303)


@router.post("/posts/{post_id}/contactar")
def contact_post_owner(request: Request, post_id: str, body: str = Form(...)):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    post = db.get_post(post_id)
    if post is None:
        return RedirectResponse("/explorar", status_code=303)

    owner_id = post["user_id"]
    if owner_id == user["user_id"]:
        return RedirectResponse(f"/posts/{post_id}", status_code=303)

    body = body.strip()
    if body:
        full_body = f"[Sobre: {post['theme']} — post #{post_id[:8]}]\n{body}"
        db.create_message(uuid.uuid4().hex, post_id, user["user_id"], owner_id, full_body)

    return RedirectResponse(f"/mensagens/posto/{post_id}/{owner_id}", status_code=303)


@router.post("/mensagens/iniciar")
def initiate_messenger_chat(
    request: Request,
    post_id: str | None = Form(None),
    business_id: str | None = Form(None),
    initial_text: str | None = Form("Olá! Estou interessado no vosso anúncio."),
):
    """Ponto de entrada único do Messenger Boladas-ponto-com a partir de qualquer
    anúncio ou loja empresarial."""
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    target_post_id = post_id
    target_owner_id = None

    if post_id:
        post = db.get_post(post_id)
        if post:
            target_owner_id = post["user_id"]
    elif business_id:
        biz = db.get_business(business_id)
        if biz:
            target_owner_id = biz["user_id"]
            posts = db.list_posts_by_business(business_id)
            if posts:
                target_post_id = posts[0]["post_id"]

    if not target_owner_id:
        return RedirectResponse("/explorar", status_code=303)

    if target_owner_id == user["user_id"]:
        return RedirectResponse("/mensagens", status_code=303)

    # Cria mensagem inicial se ainda não houver mensagens
    existing_thread = db.list_thread(user["user_id"], target_post_id, target_owner_id)
    if not existing_thread and initial_text:
        db.create_message(
            uuid.uuid4().hex, target_post_id, user["user_id"], target_owner_id, initial_text.strip()
        )

    if target_post_id:
        return RedirectResponse(f"/mensagens/posto/{target_post_id}/{target_owner_id}", status_code=303)
    return RedirectResponse("/mensagens", status_code=303)
