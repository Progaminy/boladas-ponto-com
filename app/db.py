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

    caption TEXT,
    call_to_action_generated TEXT,
    hashtags TEXT,

    image_key TEXT,
    caption_key TEXT,
    provenance_key TEXT,
    thumbnail_key TEXT,
    image_url TEXT,
    moderation_status TEXT NOT NULL DEFAULT 'approved'
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
        _ensure_column(conn, "businesses", "profile_photo_key", "profile_photo_key TEXT")
        _ensure_column(conn, "businesses", "profile_photo_url", "profile_photo_url TEXT")
        _ensure_column(conn, "businesses", "cover_photo_key", "cover_photo_key TEXT")
        _ensure_column(conn, "businesses", "cover_photo_url", "cover_photo_url TEXT")
        _ensure_column(
            conn, "posts", "moderation_status", "moderation_status TEXT NOT NULL DEFAULT 'approved'"
        )
        _backfill_business_owners(conn)


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
    from app.config import ADMIN_EMAIL

    now = _now()
    is_admin = 1 if ADMIN_EMAIL and email.strip().lower() == ADMIN_EMAIL else 0
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (user_id, email, password_hash, display_name, created_at, "
            "terms_accepted_at, is_admin) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, email, password_hash, display_name, now, now, is_admin),
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
    query = "SELECT * FROM posts WHERE status = 'completed' AND moderation_status = 'approved'"
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
