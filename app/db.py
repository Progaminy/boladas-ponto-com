import json
import math
import sqlite3
import uuid
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
    created_at TEXT NOT NULL,
    terms_accepted_at TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    profile_photo_key TEXT,
    profile_photo_url TEXT,
    cover_photo_key TEXT,
    cover_photo_url TEXT
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
    size INTEGER NOT NULL,
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
    created_at TEXT NOT NULL
);

-- Uma empresa pode ter vários gestores (sócios). O criador fica como
-- 'proprietario'; os restantes como 'gestor'. Ambos podem publicar e editar,
-- mas só o proprietário pode remover gestores ou apagar a empresa.
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
    price_mt REAL,
    location TEXT,
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
    moderation_status TEXT NOT NULL DEFAULT 'approved'
);

CREATE TABLE IF NOT EXISTS post_reactions (
    reaction_id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(post_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    type TEXT NOT NULL, -- 'like' ou 'dislike'
    reason TEXT, -- obrigatório quando type = 'dislike'
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


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """Adiciona uma coluna a uma tabela já existente se ainda não existir —
    evita perder dados locais/em produção quando o schema evolui."""
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _ensure_businesses_allow_multiple(conn: sqlite3.Connection) -> None:
    """Versões antigas do schema tinham UNIQUE(user_id) em businesses,
    limitando a um negócio por utilizador. Remove a restrição recriando a
    tabela e preservando os dados existentes — não perde negócios já
    registados."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='businesses'"
    ).fetchone()
    if row is None or "user_id TEXT NOT NULL UNIQUE" not in (row["sql"] or ""):
        return
    conn.execute("ALTER TABLE businesses RENAME TO businesses_old")
    conn.executescript(SCHEMA)
    old_cols = {r["name"] for r in conn.execute("PRAGMA table_info(businesses_old)")}
    new_cols = {r["name"] for r in conn.execute("PRAGMA table_info(businesses)")}
    common = ", ".join(old_cols & new_cols)
    conn.execute(f"INSERT INTO businesses ({common}) SELECT {common} FROM businesses_old")
    conn.execute("DROP TABLE businesses_old")


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _ensure_businesses_allow_multiple(conn)
        _ensure_column(conn, "users", "terms_accepted_at", "terms_accepted_at TEXT")
        _ensure_column(conn, "users", "is_admin", "is_admin INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "users", "profile_photo_key", "profile_photo_key TEXT")
        _ensure_column(conn, "users", "profile_photo_url", "profile_photo_url TEXT")
        _ensure_column(conn, "users", "cover_photo_key", "cover_photo_key TEXT")
        _ensure_column(conn, "users", "cover_photo_url", "cover_photo_url TEXT")
        _ensure_column(conn, "users", "seasonal_theme", "seasonal_theme TEXT DEFAULT 'padrao'")
        _ensure_column(conn, "users", "phone", "phone TEXT")
        _ensure_column(conn, "users", "phone_prefix", "phone_prefix TEXT")
        _ensure_column(conn, "users", "google_id", "google_id TEXT")
        _ensure_column(conn, "users", "auth_provider", "auth_provider TEXT DEFAULT 'email'")
        _ensure_column(conn, "businesses", "profile_photo_key", "profile_photo_key TEXT")
        _ensure_column(conn, "businesses", "profile_photo_url", "profile_photo_url TEXT")
        _ensure_column(conn, "businesses", "cover_photo_key", "cover_photo_key TEXT")
        _ensure_column(conn, "businesses", "cover_photo_url", "cover_photo_url TEXT")
        _ensure_column(conn, "businesses", "seasonal_theme", "seasonal_theme TEXT DEFAULT 'padrao'")
        _ensure_column(conn, "businesses", "latitude", "latitude REAL")
        _ensure_column(conn, "businesses", "longitude", "longitude REAL")
        _ensure_column(conn, "businesses", "description", "description TEXT")
        _ensure_column(
            conn, "posts", "moderation_status", "moderation_status TEXT NOT NULL DEFAULT 'approved'"
        )
        _ensure_column(conn, "posts", "description", "description TEXT")
        _ensure_column(conn, "posts", "description_source", "description_source TEXT")
        _ensure_column(conn, "posts", "image_skipped_reason", "image_skipped_reason TEXT")
        _ensure_column(conn, "posts", "latitude", "latitude REAL")
        _ensure_column(conn, "posts", "longitude", "longitude REAL")
        _ensure_column(conn, "posts", "currency", "currency TEXT NOT NULL DEFAULT 'MZN'")
        _backfill_business_owners(conn)
        seed_demo_stores_if_needed(conn)


def _backfill_business_owners(conn: sqlite3.Connection) -> None:
    """Garante que o criador de cada empresa consta como proprietário em
    business_members. Empresas criadas antes desta funcionalidade existirem
    ficariam sem qualquer gestor registado."""
    conn.execute(
        """
        INSERT OR IGNORE INTO business_members (business_id, user_id, role, added_at, added_by)
        SELECT business_id, user_id, 'proprietario', created_at, user_id FROM businesses
        """
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- users -----------------------------------------------------------------

def create_user(user_id: str, email: str, password_hash: str, display_name: str) -> None:
    create_user_full(user_id=user_id, display_name=display_name, email=email, password_hash=password_hash)


def create_user_full(
    user_id: str,
    display_name: str,
    email: str | None = None,
    password_hash: str | None = None,
    phone: str | None = None,
    phone_prefix: str | None = None,
    google_id: str | None = None,
    auth_provider: str = "email",
) -> None:
    from app.config import ADMIN_EMAIL

    now = _now()
    clean_email = email.strip().lower() if email else f"user_{user_id[:8]}@boladas.com"
    clean_hash = password_hash or "auth_external"
    is_admin = 1 if ADMIN_EMAIL and email and email.strip().lower() == ADMIN_EMAIL else 0
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users (
                user_id, email, password_hash, display_name, created_at,
                terms_accepted_at, is_admin, phone, phone_prefix, google_id, auth_provider
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id, clean_email, clean_hash, display_name, now, now, is_admin,
                phone, phone_prefix, google_id, auth_provider,
            ),
        )


def get_user_by_email(email: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.strip().lower(),))
        return cur.fetchone()


def get_user_by_phone(phone: str) -> sqlite3.Row | None:
    clean_phone = phone.strip().replace(" ", "")
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM users WHERE phone = ? OR REPLACE(phone, ' ', '') = ?",
            (phone.strip(), clean_phone),
        )
        return cur.fetchone()


def get_user_by_email_or_phone(identifier: str) -> sqlite3.Row | None:
    ident = identifier.strip()
    clean_ident = ident.replace(" ", "")
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM users
            WHERE LOWER(email) = ? OR phone = ? OR REPLACE(phone, ' ', '') = ?
            """,
            (ident.lower(), ident, clean_ident),
        )
        return cur.fetchone()


def get_user_by_google_id(google_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id.strip(),))
        return cur.fetchone()


def get_user_by_id(user_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()


# --- businesses --------------------------------------------------------------

def create_business(business_id: str, user_id: str, data: BusinessInput) -> None:
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO businesses (business_id, user_id, name, category, description, "
            "location, contact, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                business_id, user_id, data.name, data.category, data.description,
                data.location, data.contact, now,
            ),
        )
        # quem cria fica automaticamente como proprietário
        conn.execute(
            "INSERT OR IGNORE INTO business_members (business_id, user_id, role, added_at, "
            "added_by) VALUES (?, ?, 'proprietario', ?, ?)",
            (business_id, user_id, now, user_id),
        )


def update_business(business_id: str, data: BusinessInput) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE businesses SET name = ?, category = ?, description = ?, location = ?, "
            "contact = ? WHERE business_id = ?",
            (data.name, data.category, data.description, data.location, data.contact, business_id),
        )


def list_businesses_by_user(user_id: str) -> list[sqlite3.Row]:
    """Empresas que o utilizador gere — as que criou e aquelas onde foi
    adicionado como sócio/gestor."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT b.* FROM businesses b
            JOIN business_members m ON m.business_id = b.business_id
            WHERE m.user_id = ?
            ORDER BY b.created_at ASC
            """,
            (user_id,),
        )
        return cur.fetchall()


def get_business(business_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM businesses WHERE business_id = ?", (business_id,))
        return cur.fetchone()


# --- gestores da empresa (sócios) --------------------------------------------

def add_business_member(
    business_id: str, user_id: str, added_by: str, role: str = "gestor"
) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO business_members (business_id, user_id, role, added_at, "
            "added_by) VALUES (?, ?, ?, ?, ?)",
            (business_id, user_id, role, _now(), added_by),
        )


def remove_business_member(business_id: str, user_id: str) -> None:
    """Remove um gestor. Nunca remove o proprietário — uma empresa sem
    proprietário ficaria órfã e inacessível."""
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM business_members WHERE business_id = ? AND user_id = ? "
            "AND role != 'proprietario'",
            (business_id, user_id),
        )


def list_business_members(business_id: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT m.*, u.display_name, u.email
            FROM business_members m
            JOIN users u ON u.user_id = m.user_id
            WHERE m.business_id = ?
            ORDER BY CASE m.role WHEN 'proprietario' THEN 0 ELSE 1 END, m.added_at ASC
            """,
            (business_id,),
        )
        return cur.fetchall()


def get_business_role(business_id: str, user_id: str) -> str | None:
    """Papel do utilizador nesta empresa, ou None se não for gestor."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT role FROM business_members WHERE business_id = ? AND user_id = ?",
            (business_id, user_id),
        )
        row = cur.fetchone()
        return row["role"] if row else None


def can_manage_business(business_id: str, user_id: str) -> bool:
    return get_business_role(business_id, user_id) is not None


def is_business_owner(business_id: str, user_id: str) -> bool:
    return get_business_role(business_id, user_id) == "proprietario"


def set_user_photo(user_id: str, kind: str, key: str, url: str) -> None:
    col_key, col_url = f"{kind}_photo_key", f"{kind}_photo_url"
    with get_conn() as conn:
        conn.execute(
            f"UPDATE users SET {col_key} = ?, {col_url} = ? WHERE user_id = ?", (key, url, user_id)
        )


def set_business_photo(business_id: str, kind: str, key: str, url: str) -> None:
    col_key, col_url = f"{kind}_photo_key", f"{kind}_photo_url"
    with get_conn() as conn:
        conn.execute(
            f"UPDATE businesses SET {col_key} = ?, {col_url} = ? WHERE business_id = ?",
            (key, url, business_id),
        )


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
                price_mt, currency, location, contact, color_reference,
                description, description_source
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post_id, user_id, business_id, PostStatus.PENDING.value, now, now,
                data.theme, data.business, data.category, data.publisher_type.value,
                data.brand_name, data.target_audience, data.objective, data.tone,
                data.language, data.call_to_action, data.price_mt, getattr(data, "currency", "MZN") or "MZN", data.location,
                data.contact, data.color_reference,
                data.description, data.description_source,
            ),
        )
    return now


def update_status(post_id: str, status: PostStatus | str, error: str | None = None) -> None:
    val = status.value if hasattr(status, "value") else str(status)
    with get_conn() as conn:
        conn.execute(
            "UPDATE posts SET status = ?, error = ?, updated_at = ? WHERE post_id = ?",
            (val, error, _now(), post_id),
        )


def save_generation_result(
    post_id: str,
    *,
    caption: str,
    call_to_action_generated: str,
    hashtags: list[str],
    image_key: str | None,
    caption_key: str,
    provenance_key: str,
    thumbnail_key: str | None,
    image_url: str | None,
    image_skipped_reason: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE posts SET
                caption = ?, call_to_action_generated = ?, hashtags = ?,
                image_key = ?, caption_key = ?, provenance_key = ?,
                thumbnail_key = ?, image_url = ?, image_skipped_reason = ?, updated_at = ?
            WHERE post_id = ?
            """,
            (
                caption, call_to_action_generated, json.dumps(hashtags, ensure_ascii=False),
                image_key, caption_key, provenance_key, thumbnail_key, image_url,
                image_skipped_reason, _now(), post_id,
            ),
        )


def create_message(
    message_id: str, post_id: str | None, sender_id: str, recipient_id: str | None, body: str
) -> str:
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (message_id, post_id, sender_id, recipient_id, body, "
            "created_at, read_at) VALUES (?, ?, ?, ?, ?, ?, NULL)",
            (message_id, post_id, sender_id, recipient_id, body, now),
        )
    return now


def list_messages_for_user(user_id: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM messages WHERE sender_id = ? OR recipient_id = ? ORDER BY created_at ASC",
            (user_id, user_id),
        )
        return cur.fetchall()


def list_thread(user_id: str, post_id: str | None, other_user_id: str | None) -> list[sqlite3.Row]:
    with get_conn() as conn:
        if post_id is None and other_user_id is None:
            cur = conn.execute(
                "SELECT * FROM messages WHERE post_id IS NULL AND recipient_id IS NULL "
                "AND sender_id = ? ORDER BY created_at ASC",
                (user_id,),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM messages WHERE post_id = ? "
                "AND ((sender_id = ? AND recipient_id = ?) OR (sender_id = ? AND recipient_id = ?)) "
                "ORDER BY created_at ASC",
                (post_id, user_id, other_user_id, other_user_id, user_id),
            )
        return cur.fetchall()


def mark_thread_read(user_id: str, post_id: str | None, other_user_id: str | None) -> None:
    if post_id is None and other_user_id is None:
        return
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "UPDATE messages SET read_at = ? WHERE post_id = ? AND sender_id = ? "
            "AND recipient_id = ? AND read_at IS NULL",
            (now, post_id, other_user_id, user_id),
        )


def add_product_media(
    media_id: str, post_id: str, media_type: str, b2_key: str, content_type: str,
    size: int, sha256: str, url: str, order_index: int,
) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO product_media (media_id, post_id, media_type, b2_key, content_type, "
            "size, sha256, url, order_index, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (media_id, post_id, media_type, b2_key, content_type, size, sha256, url, order_index, _now()),
        )


def list_product_media(post_id: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM product_media WHERE post_id = ? ORDER BY order_index ASC",
            (post_id,),
        )
        return cur.fetchall()


def count_product_media(post_id: str, media_type: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) as c FROM product_media WHERE post_id = ? AND media_type = ?",
            (post_id, media_type),
        )
        return cur.fetchone()["c"]


def get_product_media(media_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM product_media WHERE media_id = ?", (media_id,))
        return cur.fetchone()


def delete_product_media(media_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM product_media WHERE media_id = ?", (media_id,))


def create_transaction(
    transaction_id: str, post_id: str, buyer_id: str, seller_id: str, with_mediation: bool
) -> None:
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transactions (transaction_id, post_id, buyer_id, seller_id, status, "
            "with_mediation, notes, created_at, updated_at) VALUES (?, ?, ?, ?, 'pendente', ?, NULL, ?, ?)",
            (transaction_id, post_id, buyer_id, seller_id, int(with_mediation), now, now),
        )


def get_transaction(transaction_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,))
        return cur.fetchone()


def update_transaction_status(transaction_id: str, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE transactions SET status = ?, updated_at = ? WHERE transaction_id = ?",
            (status, _now(), transaction_id),
        )


def list_transactions_for_user(user_id: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE buyer_id = ? OR seller_id = ? ORDER BY updated_at DESC",
            (user_id, user_id),
        )
        return cur.fetchall()


def set_post_moderation_status(post_id: str, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE posts SET moderation_status = ?, updated_at = ? WHERE post_id = ?",
            (status, _now(), post_id),
        )


def create_report(report_id: str, post_id: str, reporter_id: str, reason: str, source: str = "user") -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reports (report_id, post_id, reporter_id, reason, source, "
            "resolved, created_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
            (report_id, post_id, reporter_id, reason, source, _now()),
        )


def list_open_reports() -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM reports WHERE resolved = 0 ORDER BY created_at ASC")
        return cur.fetchall()


def get_report(report_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,))
        return cur.fetchone()


def resolve_report(report_id: str, resolved_by: str, resolution: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE reports SET resolved = 1, resolution = ?, resolved_by = ?, resolved_at = ? "
            "WHERE report_id = ?",
            (resolution, resolved_by, _now(), report_id),
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
            "AND moderation_status = 'approved' ORDER BY created_at DESC LIMIT ?",
            (business_id, limit),
        )
        return cur.fetchall()


def list_public_individual_posts_by_user(user_id: str, limit: int = 50) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM posts WHERE user_id = ? AND business_id IS NULL AND status = 'completed' "
            "AND moderation_status = 'approved' ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        return cur.fetchall()


def list_public_posts(
    category: str | None = None, location_query: str | None = None, limit: int = 100
) -> list[sqlite3.Row]:
    query = """
    SELECT p.*,
           COALESCE(b.profile_photo_url, u.profile_photo_url) AS seller_photo_url
    FROM posts p
    LEFT JOIN users u ON p.user_id = u.user_id
    LEFT JOIN businesses b ON p.business_id = b.business_id
    WHERE p.status = 'completed' AND p.moderation_status = 'approved'
    """
    params: list = []
    if category:
        query += " AND p.category = ?"
        params.append(category)
    if location_query:
        query += " AND p.location LIKE ?"
        params.append(f"%{location_query}%")
    query += " ORDER BY p.created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        cur = conn.execute(query, params)
        return cur.fetchall()


# --- Reações (Likes / Dislikes) & Comentários ------------------------------

def add_post_reaction(post_id: str, user_id: str, reaction_type: str, reason: str | None = None) -> dict:
    reaction_type = reaction_type.lower().strip()
    if reaction_type not in ("like", "dislike"):
        raise ValueError("Tipo de reação inválido. Usa 'like' ou 'dislike'.")
    if reaction_type == "dislike" and (not reason or not reason.strip()):
        raise ValueError("O dislike exige uma justificativa/motivo obrigatório.")

    now = _now()
    reaction_id = str(uuid.uuid4())
    reason_clean = reason.strip() if reason else None

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT type FROM post_reactions WHERE post_id = ? AND user_id = ?",
            (post_id, user_id),
        ).fetchone()

        if existing and existing["type"] == reaction_type and reaction_type == "like":
            # Toggling off (remover o Gostar se tornar a clicar)
            conn.execute(
                "DELETE FROM post_reactions WHERE post_id = ? AND user_id = ?",
                (post_id, user_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO post_reactions (reaction_id, post_id, user_id, type, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id, user_id) DO UPDATE SET
                    type = excluded.type,
                    reason = excluded.reason,
                    created_at = excluded.created_at
                """,
                (reaction_id, post_id, user_id, reaction_type, reason_clean, now),
            )

            # Se for um dislike, encaminha AUTOMATICAMENTE um alerta para a equipa da plataforma (reports)
            if reaction_type == "dislike" and reason_clean:
                report_id = str(uuid.uuid4())
                report_reason = f"[FEEDBACK DISLIKE AUTOMÁTICO] Post {post_id} recebeu dislike de {user_id}: {reason_clean}"
                conn.execute(
                    """
                    INSERT INTO reports (report_id, post_id, reporter_id, reason, source, created_at)
                    VALUES (?, ?, ?, ?, 'dislike_feedback', ?)
                    """,
                    (report_id, post_id, user_id, report_reason, now),
                )

    return get_post_reactions(post_id, user_id)


def get_post_reactions(post_id: str, user_id: str | None = None) -> dict:
    with get_conn() as conn:
        likes = conn.execute(
            "SELECT COUNT(*) FROM post_reactions WHERE post_id = ? AND type = 'like'", (post_id,)
        ).fetchone()[0]
        dislikes = conn.execute(
            "SELECT COUNT(*) FROM post_reactions WHERE post_id = ? AND type = 'dislike'", (post_id,)
        ).fetchone()[0]

        user_reaction = None
        if user_id:
            row = conn.execute(
                "SELECT type FROM post_reactions WHERE post_id = ? AND user_id = ?",
                (post_id, user_id),
            ).fetchone()
            if row:
                user_reaction = row["type"]

        return {"likes": likes, "dislikes": dislikes, "user_reaction": user_reaction}


def add_post_comment(post_id: str, user_id: str, body: str) -> dict:
    body_clean = body.strip()
    if not body_clean:
        raise ValueError("O comentário não pode estar vazio.")
    comment_id = str(uuid.uuid4())
    now = _now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO post_comments (comment_id, post_id, user_id, body, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (comment_id, post_id, user_id, body_clean, now),
        )
    return {"comment_id": comment_id, "post_id": post_id, "user_id": user_id, "body": body_clean, "created_at": now}


def get_post_comments(post_id: str) -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT c.comment_id, c.post_id, c.user_id, c.body, c.created_at, u.display_name, u.profile_photo_url
            FROM post_comments c
            JOIN users u ON c.user_id = u.user_id
            WHERE c.post_id = ?
            ORDER BY c.created_at ASC
            """,
            (post_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# --- Autonomia Total (Edição e Remoção de Posts) ----------------------------

def update_post_details(
    post_id: str, user_id: str, theme: str, price_mt: float | None, contact: str, location: str | None, description: str | None
) -> None:
    post = get_post(post_id)
    if not post:
        raise ValueError("Post não encontrado.")
    if post["user_id"] != user_id:
        raise PermissionError("Apenas o proprietário pode editar este post.")

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE posts SET
                theme = ?,
                price_mt = ?,
                contact = ?,
                location = ?,
                description = ?,
                updated_at = ?
            WHERE post_id = ?
            """,
            (theme, price_mt, contact, location, description, _now(), post_id),
        )


def delete_post(post_id: str, user_id: str) -> None:
    post = get_post(post_id)
    if not post:
        raise ValueError("Post não encontrado.")

    # Se for um post de empresa, gestores da empresa também podem apagar
    can_delete = post["user_id"] == user_id
    if not can_delete and post["business_id"]:
        membership = get_business_member(post["business_id"], user_id)
        if membership:
            can_delete = True

    if not can_delete:
        raise PermissionError("Sem permissão para eliminar este post.")

    with get_conn() as conn:
        conn.execute("DELETE FROM product_media WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM messages WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM post_reactions WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM post_comments WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM reports WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM transactions WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM posts WHERE post_id = ?", (post_id,))


# --- Temas Festivos (Utilizador & Empresa) ---------------------------------

def set_user_seasonal_theme(user_id: str, theme: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET seasonal_theme = ? WHERE user_id = ?", (theme, user_id))


def set_business_seasonal_theme(business_id: str, user_id: str, theme: str) -> None:
    member = get_business_member(business_id, user_id)
    if not member:
        raise PermissionError("Apenas gestores/proprietários da empresa podem alterar o tema.")
    with get_conn() as conn:
        conn.execute("UPDATE businesses SET seasonal_theme = ? WHERE business_id = ?", (theme, business_id))


# --- GPS Proximidade & Comparador de Preços --------------------------------

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0  # Raio da Terra em km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


def list_all_businesses(category: str | None = None, search: str | None = None) -> list[dict]:
    with get_conn() as conn:
        query = """
            SELECT b.*,
                   u.display_name AS owner_name,
                   (SELECT COUNT(*) FROM posts p WHERE p.business_id = b.business_id AND p.moderation_status = 'approved') AS product_count,
                   (SELECT COUNT(*) FROM business_members bm WHERE bm.business_id = b.business_id) AS member_count
            FROM businesses b
            JOIN users u ON u.user_id = b.user_id
            WHERE 1=1
        """
        params = []
        if category and category.strip():
            query += " AND b.category = ?"
            params.append(category.strip())
        if search and search.strip():
            query += " AND (b.name LIKE ? OR b.location LIKE ? OR b.description LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term, term])
        query += " ORDER BY b.created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def compare_prices_and_proximity(
    search_query: str | None = None,
    category: str | None = None,
    user_lat: float | None = None,
    user_lon: float | None = None,
    sort_by: str = "price_asc",
) -> list[dict]:
    with get_conn() as conn:
        query = """
            SELECT p.*,
                   b.name AS store_name,
                   b.business_id,
                   b.category AS store_category,
                   b.location AS store_location,
                   b.contact AS store_contact,
                   COALESCE(b.profile_photo_url, u.profile_photo_url) AS seller_photo_url,
                   b.latitude AS store_lat,
                   b.longitude AS store_lon
            FROM posts p
            LEFT JOIN businesses b ON b.business_id = p.business_id
            LEFT JOIN users u ON u.user_id = p.user_id
            WHERE p.moderation_status = 'approved'
        """
        params = []
        if search_query and search_query.strip():
            query += " AND (p.theme LIKE ? OR p.description LIKE ? OR p.business LIKE ?)"
            term = f"%{search_query.strip()}%"
            params.extend([term, term, term])
        if category and category.strip():
            query += " AND p.category = ?"
            params.append(category.strip())

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

        for r in rows:
            r["distance_km"] = None
            st_lat = r.get("store_lat") or r.get("latitude")
            st_lon = r.get("store_lon") or r.get("longitude")
            if user_lat is not None and user_lon is not None and st_lat is not None and st_lon is not None:
                try:
                    r["distance_km"] = haversine_distance(float(user_lat), float(user_lon), float(st_lat), float(st_lon))
                except (ValueError, TypeError):
                    r["distance_km"] = None

        if sort_by == "distance_asc":
            rows.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 999999, x.get("price_mt") or 999999))
        elif sort_by == "price_desc":
            rows.sort(key=lambda x: (-(x.get("price_mt") or 0)))
        else:
            rows.sort(key=lambda x: (x.get("price_mt") is None, x.get("price_mt") or 999999))

        return rows


def seed_demo_stores_if_needed(conn: sqlite3.Connection) -> None:
    from app.auth import hash_password

    now = datetime.now(timezone.utc).isoformat()
    pass_hash = hash_password("senha12345")

    demo_stores = [
        {
            "user_id": "usr_seed_ferragem",
            "user_email": "carlos.ferragem@boladas.co.mz",
            "user_name": "Eng. Carlos Ferragem",
            "biz_id": "biz_seed_ferragem",
            "biz_name": "Ferragem Lendária Maputo",
            "category": "ferragem",
            "nuit": "400123987",
            "location": "Av. 24 de Julho nº 1420, Maputo",
            "lat": -25.9692,
            "lon": 32.5732,
            "contact": "841234567",
            "desc": "Especialistas em materiais de construção, cimento, tubagens, pregos e ferramentas para a sua obra em Moçambique.",
            "cover": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?w=1200",
            "profile": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=300",
            "products": [
                {
                    "post_id": "post_seed_cimento",
                    "theme": "Cimento Limpopo 42.5N (50kg)",
                    "price_mt": 480.0,
                    "desc": "Cimento Portland de alta resistência para fundações, placas e alvenaria.",
                    "image": "https://images.unsplash.com/photo-1589939705384-5185137a7f0f?w=800",
                },
                {
                    "post_id": "post_seed_tubo",
                    "theme": "Tubo PVC Esgoto 110mm (6 Metros)",
                    "price_mt": 650.0,
                    "desc": "Tubo de PVC reforçado para canalização de saneamento e águas residuais.",
                    "image": "https://images.unsplash.com/photo-1542013936693-884638332954?w=800",
                },
                {
                    "post_id": "post_seed_prego",
                    "theme": "Prego de Construção 3 Polegadas (Caixa 5kg)",
                    "price_mt": 350.0,
                    "desc": "Pregos de aço galvanizado para cofragens e marcenaria.",
                    "image": "https://images.unsplash.com/photo-1586864387967-d02ef85d93e8?w=800",
                },
            ],
        },
        {
            "user_id": "usr_seed_farmacia",
            "user_email": "ana.farmacia@boladas.co.mz",
            "user_name": "Dra. Ana Saúde",
            "biz_id": "biz_seed_farmacia",
            "biz_name": "Farmácia Moçambique Vida",
            "category": "saude",
            "nuit": "400987123",
            "location": "Av. Eduardo Mondlane nº 850, Maputo",
            "lat": -25.9650,
            "lon": 32.5800,
            "contact": "829876543",
            "desc": "Farmácia comunitária com medicamentos certificados, cuidados infantis, dermatologia e vitaminas de qualidade.",
            "cover": "https://images.unsplash.com/photo-1576602976047-174e57a47881?w=1200",
            "profile": "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=300",
            "products": [
                {
                    "post_id": "post_seed_paracetamol",
                    "theme": "Paracetamol 500mg (Caixa 20 Comprimidos)",
                    "price_mt": 75.0,
                    "desc": "Alívio eficaz de dores de cabeça, febres e sintomas gripais.",
                    "image": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800",
                },
                {
                    "post_id": "post_seed_vitamina",
                    "theme": "Vitamina C Efervescente 1000mg (Tubo 20 Comp)",
                    "price_mt": 220.0,
                    "desc": "Suplemento diário para reforço imunitário e vitalidade.",
                    "image": "https://images.unsplash.com/photo-1577401239170-897942555fb3?w=800",
                },
                {
                    "post_id": "post_seed_termometro",
                    "theme": "Termómetro Digital Infravermelho sem Contacto",
                    "price_mt": 850.0,
                    "desc": "Leitura ultrarrápida da temperatura corporal com visor LCD.",
                    "image": "https://images.unsplash.com/photo-1584017911766-d451b3d0e843?w=800",
                },
            ],
        },
        {
            "user_id": "usr_seed_boutique",
            "user_email": "clara.boutique@boladas.co.mz",
            "user_name": "Clara Moda",
            "biz_id": "biz_seed_boutique",
            "biz_name": "Moda & Estilo Boutique",
            "category": "vestuario",
            "nuit": "400456789",
            "location": "Rua da Bagamoyo nº 45, Baixa de Maputo",
            "lat": -25.9720,
            "lon": 32.5700,
            "contact": "873334455",
            "desc": "Roupas femininas e masculinas de alta qualidade, capulanas de luxo, vestidos de gala e acessórios de moda.",
            "cover": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1200",
            "profile": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=300",
            "products": [
                {
                    "post_id": "post_seed_capulana",
                    "theme": "Capulana Tradicional de Luxo (6 Jardas)",
                    "price_mt": 1200.0,
                    "desc": "Tecido 100% algodão com padrões tradicionais e cores vivas.",
                    "image": "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=800",
                },
                {
                    "post_id": "post_seed_vestido",
                    "theme": "Vestido Elegante de Festa Feminino",
                    "price_mt": 2500.0,
                    "desc": "Vestido longo de gala para casamentos, recepções e eventos festivos.",
                    "image": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=800",
                },
            ],
        },
        {
            "user_id": "usr_seed_mercado",
            "user_email": "maria.mercado@boladas.co.mz",
            "user_name": "Tia Maria Mercado",
            "biz_id": "biz_seed_mercado",
            "biz_name": "Mercado Popular de Xipamanine",
            "category": "alimentacao",
            "nuit": "400654321",
            "location": "Bairro Xipamanine, Bancada 12, Maputo",
            "lat": -25.9510,
            "lon": 32.5610,
            "contact": "845556677",
            "desc": "Venda por grosso e retalho de bens alimentares de primeira necessidade: arroz, óleo, feijão e farinha.",
            "cover": "https://images.unsplash.com/photo-1533900298318-6b8da08a523e?w=1200",
            "profile": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=300",
            "products": [
                {
                    "post_id": "post_seed_arroz",
                    "theme": "Saco de Arroz Premium 25kg",
                    "price_mt": 1350.0,
                    "desc": "Arroz de grão longo e solto de primeira qualidade.",
                    "image": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=800",
                },
                {
                    "post_id": "post_seed_oleo",
                    "theme": "Óleo Alimentar Vegetal 5 Litros",
                    "price_mt": 620.0,
                    "desc": "Óleo de girassol 100% puro para a sua cozinha.",
                    "image": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=800",
                },
            ],
        },
        {
            "user_id": "usr_seed_transporte",
            "user_email": "alberto.transporte@boladas.co.mz",
            "user_name": "Sr. Alberto Fretes",
            "biz_id": "biz_seed_transporte",
            "biz_name": "Transporte & Carga Expresso Moçambique",
            "category": "servicos",
            "nuit": "400789123",
            "location": "Terminal de Zimpeto, Maputo",
            "lat": -25.8600,
            "lon": 32.5750,
            "contact": "827778899",
            "desc": "Fretes e mudanças residenciais e comerciais para todo o país com viaturas fechadas e equipa de ajudantes.",
            "cover": "https://images.unsplash.com/photo-1601584115197-04ecc0da31d7?w=1200",
            "profile": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=300",
            "products": [
                {
                    "post_id": "post_seed_mudanca",
                    "theme": "Serviço de Mudança Residencial Canter 5T",
                    "price_mt": 3500.0,
                    "desc": "Mudança segura em camião fechado com 2 ajudantes incluídos.",
                    "image": "https://images.unsplash.com/photo-1580674684081-7617fbf3d745?w=800",
                },
                {
                    "post_id": "post_seed_frete_cimento",
                    "theme": "Transporte de Materiais de Construção por Viagem",
                    "price_mt": 2500.0,
                    "desc": "Entrega rápida de cimento, blocos e areia na obra.",
                    "image": "https://images.unsplash.com/photo-1519003722824-194d4455a60c?w=800",
                },
            ],
        },
    ]

    for st in demo_stores:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (user_id, email, password_hash, display_name, created_at, terms_accepted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (st["user_id"], st["user_email"], pass_hash, st["user_name"], now, now),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO businesses (business_id, user_id, name, category, description, location, latitude, longitude, contact, profile_photo_url, cover_photo_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                st["biz_id"],
                st["user_id"],
                st["biz_name"],
                st["category"],
                st["desc"],
                st["location"],
                st["lat"],
                st["lon"],
                st["contact"],
                st["profile"],
                st["cover"],
                now,
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO business_members (business_id, user_id, role, added_at, added_by)
            VALUES (?, ?, 'proprietario', ?, ?)
            """,
            (st["biz_id"], st["user_id"], now, st["user_id"]),
        )

        for p in st["products"]:
            conn.execute(
                """
                INSERT OR IGNORE INTO posts (
                    post_id, user_id, business_id, status, created_at, updated_at,
                    theme, business, category, publisher_type, target_audience, objective,
                    tone, language, call_to_action_input, price_mt, location, latitude, longitude, contact,
                    description, image_url, moderation_status
                )
                VALUES (?, ?, ?, 'completed', ?, ?, ?, ?, ?, 'business', 'Geral', 'Vender', 'casual', 'pt', 'Contacta-nos!', ?, ?, ?, ?, ?, ?, ?, 'approved')
                """,
                (
                    p["post_id"],
                    st["user_id"],
                    st["biz_id"],
                    now,
                    now,
                    p["theme"],
                    st["biz_name"],
                    st["category"],
                    p["price_mt"],
                    st["location"],
                    st["lat"],
                    st["lon"],
                    st["contact"],
                    p["desc"],
                    p["image"],
                ),
            )
