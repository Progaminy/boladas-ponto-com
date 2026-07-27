"""Autenticação simples por sessão assinada (cookie via SessionMiddleware).
Sem tokens/segredos guardados em texto simples: passwords só existem como
hash bcrypt na base de dados."""

import sqlite3
from urllib.parse import urlencode, urlsplit

import bcrypt
from fastapi import Request
from fastapi.responses import RedirectResponse

from app import db

SESSION_KEY = "user_id"
DEFAULT_AFTER_LOGIN = "/explorar"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def login_user(request: Request, user_id: str) -> None:
    request.session[SESSION_KEY] = user_id


def logout_user(request: Request) -> None:
    request.session.pop(SESSION_KEY, None)


def get_current_user(request: Request) -> sqlite3.Row | None:
    user_id = request.session.get(SESSION_KEY)
    if not user_id:
        return None
    return db.get_user_by_id(user_id)


def safe_next_url(value: str | None, default: str = DEFAULT_AFTER_LOGIN) -> str:
    """Aceita apenas destinos internos absolutos à raiz da aplicação."""
    candidate = (value or "").strip()
    if not candidate:
        return default
    if any(ord(char) < 32 or ord(char) == 127 for char in candidate):
        return default
    if "\\" in candidate or not candidate.startswith("/") or candidate.startswith("//"):
        return default

    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return default
    if parsed.scheme or parsed.netloc:
        return default

    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"
    return target


def login_redirect(request: Request) -> RedirectResponse:
    """Leva ao login preservando o caminho e a query GET atuais."""
    target = request.url.path
    if request.url.query:
        target += f"?{request.url.query}"
    return RedirectResponse(
        f"/entrar?{urlencode({'next': target})}",
        status_code=303,
    )
