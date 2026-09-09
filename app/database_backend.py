"""Database backend bridge.

The application historically talks to ``sqlite3`` directly.  Rewriting every
query in one risky change would make the production migration unnecessarily
fragile, so this module provides a small DB-API compatibility layer when
``DATABASE_URL`` points at PostgreSQL/Supabase.

When DATABASE_URL is absent nothing is patched and the existing SQLite test /
local-development path behaves exactly as before.
"""

from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Iterator, Mapping
from typing import Any


POSTGRES_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    terms_accepted_at TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    profile_photo_key TEXT,
    profile_photo_url TEXT,
    cover_photo_key TEXT,
    cover_photo_url TEXT,
    seasonal_theme TEXT DEFAULT 'padrao',
    phone TEXT,
    phone_prefix TEXT,
    google_id TEXT,
    auth_provider TEXT DEFAULT 'email'
);

CREATE TABLE IF NOT EXISTS businesses (
    business_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    location TEXT,
    contact TEXT NOT NULL,
    profile_photo_key TEXT,
    profile_photo_url TEXT,
    cover_photo_key TEXT,
    cover_photo_url TEXT,
    seasonal_theme TEXT DEFAULT 'padrao',
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS business_members (
    business_id TEXT NOT NULL REFERENCES businesses(business_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    role TEXT NOT NULL DEFAULT 'gestor',
    added_at TEXT NOT NULL,
    added_by TEXT REFERENCES users(user_id),
    PRIMARY KEY (business_id, user_id)
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
    price_mt DOUBLE PRECISION,
    currency TEXT NOT NULL DEFAULT 'MZN',
    location TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    contact TEXT NOT NULL,
    color_reference TEXT,
    description TEXT,
    description_source TEXT,
    caption TEXT,
    call_to_action_generated TEXT,
    hashtags TEXT,
    image_skipped_reason TEXT,
    image_key TEXT,
    caption_key TEXT,
    provenance_key TEXT,
    thumbnail_key TEXT,
    image_url TEXT,
    moderation_status TEXT NOT NULL DEFAULT 'approved',
    listing_status TEXT NOT NULL DEFAULT 'active'
        CHECK (listing_status IN ('active', 'paused', 'sold'))
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    post_id TEXT REFERENCES posts(post_id),
    sender_id TEXT NOT NULL REFERENCES users(user_id),
    recipient_id TEXT REFERENCES users(user_id),
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_at TEXT
);

CREATE TABLE IF NOT EXISTS product_media (
    media_id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(post_id),
    media_type TEXT NOT NULL,
    b2_key TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size BIGINT NOT NULL,
    sha256 TEXT NOT NULL,
    url TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(post_id),
    buyer_id TEXT NOT NULL REFERENCES users(user_id),
    seller_id TEXT NOT NULL REFERENCES users(user_id),
    status TEXT NOT NULL,
    with_mediation INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(post_id),
    reporter_id TEXT NOT NULL REFERENCES users(user_id),
    reason TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'user',
    resolved INTEGER NOT NULL DEFAULT 0,
    resolution TEXT,
    resolved_by TEXT REFERENCES users(user_id),
    resolved_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS post_reactions (
    reaction_id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(post_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    type TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(post_id, user_id)
);

CREATE TABLE IF NOT EXISTS post_comments (
    comment_id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(post_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_posts_user_created ON posts(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_business_created ON posts(business_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_public_feed ON posts(status, moderation_status, listing_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category);
CREATE INDEX IF NOT EXISTS idx_businesses_category ON businesses(category);
CREATE INDEX IF NOT EXISTS idx_business_members_user ON business_members(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id, created_at);
CREATE INDEX IF NOT EXISTS idx_product_media_post ON product_media(post_id, order_index);
CREATE INDEX IF NOT EXISTS idx_transactions_buyer ON transactions(buyer_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_seller ON transactions(seller_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_open ON reports(resolved, created_at);
CREATE INDEX IF NOT EXISTS idx_reactions_post ON post_reactions(post_id);
CREATE INDEX IF NOT EXISTS idx_comments_post ON post_comments(post_id, created_at);

-- Boladas uses its own server-side authentication.  These tables are not a
-- public Supabase Data API. RLS plus revoked API roles prevents accidental
-- exposure even if the public schema is enabled in project settings.
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_media ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_reactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_comments ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE users, businesses, business_members, posts, messages,
    product_media, transactions, reports, post_reactions, post_comments
    FROM anon, authenticated;
"""


class CompatRow(Mapping[str, Any]):
    """A row that supports both sqlite3.Row styles: row['x'] and row[0]."""

    def __init__(self, columns: list[str], values: tuple[Any, ...]):
        self._columns = columns
        self._values = values
        self._index = {name: i for i, name in enumerate(columns)}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._index[key]]

    def __iter__(self) -> Iterator[str]:
        return iter(self._columns)

    def __len__(self) -> int:
        return len(self._columns)

    def keys(self):
        return list(self._columns)


class CompatCursor:
    def __init__(self, cursor=None, static_rows: list[CompatRow] | None = None):
        self._cursor = cursor
        self._static_rows = static_rows
        self._static_pos = 0

    @property
    def rowcount(self) -> int:
        if self._cursor is None:
            return len(self._static_rows or [])
        return self._cursor.rowcount

    def _columns(self) -> list[str]:
        if self._cursor is None or self._cursor.description is None:
            return []
        return [d.name if hasattr(d, "name") else d[0] for d in self._cursor.description]

    def fetchone(self):
        if self._static_rows is not None:
            if self._static_pos >= len(self._static_rows):
                return None
            row = self._static_rows[self._static_pos]
            self._static_pos += 1
            return row
        raw = self._cursor.fetchone()
        if raw is None:
            return None
        return CompatRow(self._columns(), tuple(raw))

    def fetchall(self):
        if self._static_rows is not None:
            rows = self._static_rows[self._static_pos :]
            self._static_pos = len(self._static_rows)
            return rows
        columns = self._columns()
        return [CompatRow(columns, tuple(row)) for row in self._cursor.fetchall()]


_INSERT_OR_IGNORE_RE = re.compile(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b", re.I | re.S)


def _translate_sql(sql: str) -> str:
    translated = sql.replace("?", "%s")
    if _INSERT_OR_IGNORE_RE.search(translated):
        translated = _INSERT_OR_IGNORE_RE.sub("INSERT INTO", translated, count=1)
        stripped = translated.rstrip()
        had_semicolon = stripped.endswith(";")
        if had_semicolon:
            stripped = stripped[:-1].rstrip()
        if " ON CONFLICT " not in stripped.upper():
            stripped += " ON CONFLICT DO NOTHING"
        translated = stripped + (";" if had_semicolon else "")
    return translated


def _split_sql_script(script: str) -> list[str]:
    # The controlled schema above has no procedural blocks or semicolons inside
    # string literals, so a simple split keeps this small and auditable.
    statements: list[str] = []
    cleaned_lines = []
    for line in script.splitlines():
        if line.lstrip().startswith("--"):
            continue
        cleaned_lines.append(line)
    for statement in "\n".join(cleaned_lines).split(";"):
        statement = statement.strip()
        if statement:
            statements.append(statement)
    return statements


class PostgresCompatConnection:
    def __init__(self, raw_connection):
        self._raw = raw_connection
        self._row_factory = None

    @property
    def row_factory(self):
        return self._row_factory

    @row_factory.setter
    def row_factory(self, value):
        # app.db assigns sqlite3.Row. PostgreSQL rows are adapted by CompatRow.
        self._row_factory = value

    def execute(self, sql: str, params=()):
        normalized = sql.strip().lower()
        if normalized.startswith("pragma foreign_keys"):
            return CompatCursor(static_rows=[])
        if normalized.startswith("pragma table_info("):
            table = sql[sql.find("(") + 1 : sql.rfind(")")].strip().strip('"')
            cur = self._raw.cursor()
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position",
                (table,),
            )
            rows = [CompatRow(["name"], (r[0],)) for r in cur.fetchall()]
            cur.close()
            return CompatCursor(static_rows=rows)
        if " from sqlite_master " in f" {normalized} ":
            # This query exists only to detect an obsolete SQLite UNIQUE layout.
            # The PostgreSQL schema is already created in the modern form.
            return CompatCursor(static_rows=[])

        cur = self._raw.cursor()
        cur.execute(_translate_sql(sql), tuple(params) if params is not None else ())
        return CompatCursor(cur)

    def executescript(self, _sqlite_script: str):
        cur = self._raw.cursor()
        try:
            for statement in _split_sql_script(POSTGRES_SCHEMA):
                cur.execute(statement)
        finally:
            cur.close()

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


_INSTALLED = False
_ORIGINAL_SQLITE_CONNECT = sqlite3.connect


def install_database_backend() -> bool:
    """Use PostgreSQL for sqlite3.connect calls when DATABASE_URL is defined.

    Returns True when the PostgreSQL backend is active.
    """
    global _INSTALLED
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        return False
    if not database_url.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("DATABASE_URL deve ser uma ligação PostgreSQL válida.")
    if _INSTALLED:
        return True

    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - deployment/configuration guard
        raise RuntimeError(
            "DATABASE_URL está definido, mas psycopg não está instalado. "
            "Instala requirements.txt antes de iniciar o serviço."
        ) from exc

    def _postgres_connect(*_args, **_kwargs):
        raw = psycopg.connect(database_url, autocommit=False)
        return PostgresCompatConnection(raw)

    sqlite3.connect = _postgres_connect
    _INSTALLED = True
    return True


def database_backend_name() -> str:
    return "postgresql" if os.environ.get("DATABASE_URL", "").strip() else "sqlite"
