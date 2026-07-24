"""Autenticação simples por sessão assinada (cookie via SessionMiddleware).
Sem tokens/segredos guardados em texto simples: passwords só existem como
hash bcrypt na base de dados."""

import sqlite3

import bcrypt
from fastapi import Request

from app import db

SESSION_KEY = "user_id"


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
