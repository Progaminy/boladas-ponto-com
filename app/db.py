import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import DB_PATH
from app.models import BusinessInput, PostInput, PostStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS businesses (
    business_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(user_id),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    location TEXT,
    contact TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    post_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    business_id TEXT REFERENCES businesses(business_id),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT,

    theme TEXT NOT NULL,
    business TEXT NOT NULL,
    category TEXT NOT NULL,
    publisher_type TEXT NOT NULL,
    brand_name TEXT,
    target_audience TEXT NOT NULL,
    objective TEXT NOT NULL,
    tone TEXT NOT NULL,
    language TEXT NOT NULL,
    call_to_action_input TEXT NOT NULL,
    price_mt REAL,
    location TEXT,
    contact TEXT NOT NULL,
    color_reference TEXT,

    caption TEXT,
    call_to_action_generated TEXT,
    hashtags TEXT,

    image_key TEXT,
    caption_key TEXT,
    provenance_key TEXT,
    thumbnail_key TEXT,
    image_url TEXT
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- users -----------------------------------------------------------------

def create_user(user_id: str, email: str, password_hash: str, display_name: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (user_id, email, password_hash, display_name, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, email, password_hash, display_name, _now()),
        )


def get_user_by_email(email: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
        return cur.fetchone()


def get_user_by_id(user_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()


# --- businesses --------------------------------------------------------------

def create_business(business_id: str, user_id: str, data: BusinessInput) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO businesses (business_id, user_id, name, category, description, "
            "location, contact, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                business_id, user_id, data.name, data.category, data.description,
                data.location, data.contact, _now(),
            ),
        )


def update_business(business_id: str, data: BusinessInput) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET name = ?, category = ?, description = ?, location = ?, "
            "contact = ? WHERE business_id = ?",
            (data.name, data.category, data.description, data.location, data.contact, business_id),
        )


def get_business_by_user(user_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM businesses WHERE user_id = ?", (user_id,))
        return cur.fetchone()


def get_business(business_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM businesses WHERE business_id = ?", (business_id,))
        return cur.fetchone()


# --- posts -------------------------------------------------------------------

def create_post(post_id: str, user_id: str, business_id: str | None, data: PostInput) -> str:
    now = _now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO posts (
                post_id, user_id, business_id, status, created_at, updated_at, error,
                theme, business, category, publisher_type, brand_name,
                target_audience, objective, tone, language, call_to_action_input,
                price_mt, location, contact, color_reference
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post_id, user_id, business_id, PostStatus.PENDING.value, now, now,
                data.theme, data.business, data.category, data.publisher_type.value,
                data.brand_name, data.target_audience, data.objective, data.tone,
                data.language, data.call_to_action, data.price_mt, data.location,
                data.contact, data.color_reference,
            ),
        )
    return now


def update_status(post_id: str, status: PostStatus, error: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE posts SET status = ?, error = ?, updated_at = ? WHERE post_id = ?",
            (status.value, error, _now(), post_id),
        )


def save_generation_result(
    post_id: str,
    *,
    caption: str,
    call_to_action_generated: str,
    hashtags: list[str],
    image_key: str,
    caption_key: str,
    provenance_key: str,
    thumbnail_key: str | None,
    image_url: str,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE posts SET
                caption = ?, call_to_action_generated = ?, hashtags = ?,
                image_key = ?, caption_key = ?, provenance_key = ?,
                thumbnail_key = ?, image_url = ?, updated_at = ?
            WHERE post_id = ?
            """,
            (
                caption, call_to_action_generated, json.dumps(hashtags, ensure_ascii=False),
                image_key, caption_key, provenance_key, thumbnail_key, image_url,
                _now(), post_id,
            ),
        )


def get_post(post_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM posts WHERE post_id = ?", (post_id,))
        return cur.fetchone()


def count_posts_by_user_since(user_id: str, since_iso: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) as c FROM posts WHERE user_id = ? AND created_at >= ?",
            (user_id, since_iso),
        )
        return cur.fetchone()["c"]


def list_posts_by_user(user_id: str, limit: int = 50) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        return cur.fetchall()


def list_posts_by_business(business_id: str, limit: int = 50) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM posts WHERE business_id = ? AND status = 'completed' "
            "ORDER BY created_at DESC LIMIT ?",
            (business_id, limit),
        )
        return cur.fetchall()


def list_public_posts(
    category: str | None = None, location_query: str | None = None, limit: int = 100
) -> list[sqlite3.Row]:
    query = "SELECT * FROM posts WHERE status = 'completed'"
    params: list = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if location_query:
        query += " AND location LIKE ?"
        params.append(f"%{location_query}%")
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        cur = conn.execute(query, params)
        return cur.fetchall()
