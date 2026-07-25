"""Rastreio de estado de uma compra/venda entre utilizadores da plataforma.

Importante: isto NÃO é um sistema de pagamentos. A Boladas-ponto-com não
processa, recebe nem retém dinheiro — a troca de valores acontece sempre
diretamente entre comprador e vendedor (M-Pesa, E-Mola, transferência,
dinheiro em mão), fora da app. Isto é só um checklist de confiança
(pendente → vendido → recebido) com opção de pedir mediação da equipa."""

import uuid

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.auth import get_current_user
from app.templating import templates

router = APIRouter()

# (estado_atual, novo_estado) -> quem pode fazer a transição
_ALLOWED_TRANSITIONS = {
    ("pendente", "vendido"): "seller",
    ("pendente", "cancelado"): "both",
    ("vendido", "recebido"): "buyer",
    ("vendido", "cancelado"): "both",
}


@router.post("/posts/{post_id}/transacao")
def start_transaction(request: Request, post_id: str, with_mediation: str | None = Form(None)):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    post = db.get_post(post_id)
    if post is None:
        return RedirectResponse("/explorar", status_code=303)

    seller_id = post["user_id"]
    if seller_id == user["user_id"]:
        return RedirectResponse(f"/posts/{post_id}", status_code=303)

    transaction_id = uuid.uuid4().hex
    db.create_transaction(transaction_id, post_id, user["user_id"], seller_id, with_mediation == "on")
    return RedirectResponse(f"/transacoes/{transaction_id}", status_code=303)


@router.get("/transacoes", response_class=HTMLResponse)
def list_transactions(request: Request):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    rows = db.list_transactions_for_user(user["user_id"])
    items = []
    for row in rows:
        post = db.get_post(row["post_id"])
        items.append({
            "row": row,
            "post": post,
            "role": "buyer" if row["buyer_id"] == user["user_id"] else "seller",
        })
    return templates.TemplateResponse(request, "transactions.html", {"items": items})


@router.get("/transacoes/{transaction_id}", response_class=HTMLResponse)
def transaction_detail(request: Request, transaction_id: str):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    tx = db.get_transaction(transaction_id)
    if tx is None or user["user_id"] not in (tx["buyer_id"], tx["seller_id"]):
        return RedirectResponse("/transacoes", status_code=303)

    post = db.get_post(tx["post_id"])
    role = "buyer" if tx["buyer_id"] == user["user_id"] else "seller"
    other_id = tx["seller_id"] if role == "buyer" else tx["buyer_id"]
    other_user = db.get_user_by_id(other_id)

    next_actions = [
        new for (cur, new), who in _ALLOWED_TRANSITIONS.items()
        if cur == tx["status"] and (who == "both" or who == role)
    ]

    return templates.TemplateResponse(
        request, "transaction_detail.html",
        {"tx": tx, "post": post, "role": role, "other_user": other_user, "next_actions": next_actions},
    )


@router.post("/transacoes/{transaction_id}/estado")
def transaction_update_status(request: Request, transaction_id: str, new_status: str = Form(...)):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    tx = db.get_transaction(transaction_id)
    if tx is None or user["user_id"] not in (tx["buyer_id"], tx["seller_id"]):
        return RedirectResponse("/transacoes", status_code=303)

    role = "buyer" if tx["buyer_id"] == user["user_id"] else "seller"
    who_can = _ALLOWED_TRANSITIONS.get((tx["status"], new_status))
    if who_can is not None and (who_can == "both" or who_can == role):
        db.update_transaction_status(transaction_id, new_status)

    return RedirectResponse(f"/transacoes/{transaction_id}", status_code=303)
