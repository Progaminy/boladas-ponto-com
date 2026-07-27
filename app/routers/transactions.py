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
    if not db.post_is_public(post):
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


def _row_val(row, key, default=None):
    if row is None:
        return default
    keys = row.keys() if hasattr(row, "keys") else []
    if key in keys and row[key] is not None:
        return row[key]
    return default


@router.get("/transacoes/{transaction_id}/fatura.pdf")
def download_transaction_pdf(request: Request, transaction_id: str):
    from fastapi.responses import Response
    from app.currencies import format_price
    from app.pdf_invoice import generate_invoice_pdf

    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    tx = db.get_transaction(transaction_id)
    if tx is None or user["user_id"] not in (tx["buyer_id"], tx["seller_id"]):
        return RedirectResponse("/transacoes", status_code=303)

    post = db.get_post(tx["post_id"])
    seller = db.get_user_by_id(tx["seller_id"])
    buyer = db.get_user_by_id(tx["buyer_id"])

    curr = _row_val(post, "currency", "MZN")
    price_formatted = format_price(post["price_mt"], curr) if post else "0.00 MZN"

    pdf_bytes = generate_invoice_pdf(
        invoice_number=f"INV-{transaction_id[:8].upper()}",
        title=_row_val(post, "theme", "Produto Boladas"),
        seller_name=_row_val(seller, "display_name", "Vendedor Boladas"),
        seller_contact=_row_val(seller, "phone") or _row_val(seller, "email") or "+258 872599084",
        seller_location=_row_val(post, "location", "Moçambique"),
        buyer_name=_row_val(buyer, "display_name", "Cliente"),
        buyer_contact=_row_val(buyer, "phone") or _row_val(buyer, "email"),
        item_description=_row_val(post, "caption_txt", "Produto negociado"),
        item_category=_row_val(post, "category", "geral"),
        price_formatted=price_formatted,
        currency_code=curr,
        b2_key=_row_val(post, "b2_image_key"),
        created_at=_row_val(tx, "created_at"),
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=fatura_boladas_{transaction_id[:8]}.pdf"},
    )


@router.get("/posts/{post_id}/fatura.pdf")
def download_post_pdf(request: Request, post_id: str):
    from fastapi.responses import Response
    from app.currencies import format_price
    from app.pdf_invoice import generate_invoice_pdf

    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    post = db.get_post(post_id)
    is_owner = post is not None and post["user_id"] == user["user_id"]
    is_admin = bool(user["is_admin"])
    if post is None or (
        not db.post_is_public(post) and not is_owner and not is_admin
    ):
        return RedirectResponse("/explorar", status_code=303)

    seller = db.get_user_by_id(post["user_id"])
    curr = _row_val(post, "currency", "MZN")
    price_formatted = format_price(post["price_mt"], curr)

    pdf_bytes = generate_invoice_pdf(
        invoice_number=f"PROD-{post_id[:8].upper()}",
        title=_row_val(post, "theme", "Anúncio"),
        seller_name=_row_val(seller, "display_name", "Vendedor Boladas"),
        seller_contact=_row_val(post, "contact") or _row_val(seller, "phone") or _row_val(seller, "email") or "+258 872599084",
        seller_location=_row_val(post, "location", "Moçambique"),
        buyer_name=_row_val(user, "display_name", "Consumidor Final") if user["user_id"] != post["user_id"] else "Consumidor Final",
        buyer_contact=_row_val(user, "phone") or _row_val(user, "email"),
        item_description=_row_val(post, "caption_txt") or _row_val(post, "business", "Anúncio"),
        item_category=_row_val(post, "category", "geral"),
        price_formatted=price_formatted,
        currency_code=curr,
        b2_key=_row_val(post, "b2_image_key"),
        created_at=_row_val(post, "created_at"),
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=comprovativo_post_{post_id[:8]}.pdf"},
    )
