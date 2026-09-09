#!/usr/bin/env python3
"""Copy Boladas data from SQLite to PostgreSQL/Supabase without changing IDs.

Usage:
    DATABASE_URL='postgresql://...' python scripts/migrate_sqlite_to_postgres.py

Optional:
    python scripts/migrate_sqlite_to_postgres.py --sqlite /path/posts.db --database-url 'postgresql://...'

The operation is idempotent: primary/unique-key conflicts are left untouched.
It verifies row counts after each table and aborts the PostgreSQL transaction on
any error.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

import psycopg

# Allow running from the repository root or from scripts/ directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database_backend import POSTGRES_SCHEMA, _split_sql_script


TABLES = [
    "users",
    "businesses",
    "business_members",
    "posts",
    "messages",
    "product_media",
    "transactions",
    "reports",
    "post_reactions",
    "post_comments",
]


def sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]


def postgres_columns(conn: psycopg.Connection, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position",
            (table,),
        )
        return [row[0] for row in cur.fetchall()]


def count_sqlite(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def count_postgres(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        return int(cur.fetchone()[0])


def apply_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        for statement in _split_sql_script(POSTGRES_SCHEMA):
            cur.execute(statement)


def migrate_table(source: sqlite3.Connection, target: psycopg.Connection, table: str) -> tuple[int, int]:
    source_cols = sqlite_columns(source, table)
    if not source_cols:
        return 0, count_postgres(target, table)

    target_cols = set(postgres_columns(target, table))
    columns = [column for column in source_cols if column in target_cols]
    if not columns:
        raise RuntimeError(f"Nenhuma coluna compatível encontrada para {table}.")

    quoted = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = (
        f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders}) '
        "ON CONFLICT DO NOTHING"
    )

    rows = source.execute(f'SELECT {quoted} FROM "{table}"').fetchall()
    if rows:
        with target.cursor() as cur:
            cur.executemany(insert_sql, [tuple(row) for row in rows])

    return len(rows), count_postgres(target, table)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrar Boladas SQLite -> PostgreSQL/Supabase")
    parser.add_argument("--sqlite", default=str(ROOT / "data" / "posts.db"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite).expanduser().resolve()
    database_url = args.database_url.strip()

    if not sqlite_path.exists():
        print(f"ERRO: SQLite não encontrado: {sqlite_path}", file=sys.stderr)
        return 2
    if not database_url.startswith(("postgres://", "postgresql://")):
        print("ERRO: fornece DATABASE_URL PostgreSQL/Supabase válido.", file=sys.stderr)
        return 2

    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row

    print(f"Origem SQLite: {sqlite_path}")
    print("Destino PostgreSQL: ligação recebida (credenciais ocultas)")

    try:
        with psycopg.connect(database_url, autocommit=False) as target:
            try:
                apply_schema(target)
                print("Schema PostgreSQL verificado/criado.")

                failures: list[str] = []
                for table in TABLES:
                    before_source = count_sqlite(source, table) if sqlite_columns(source, table) else 0
                    copied, after_target = migrate_table(source, target, table)
                    # The destination can legitimately contain more rows from a previous run.
                    ok = after_target >= before_source
                    status = "OK" if ok else "FALHOU"
                    print(
                        f"{status:6} {table:18} origem={before_source:5} "
                        f"lidos={copied:5} destino={after_target:5}"
                    )
                    if not ok:
                        failures.append(table)

                if failures:
                    raise RuntimeError(
                        "Contagem de destino menor que a origem em: " + ", ".join(failures)
                    )

                target.commit()
                print("Migração confirmada. IDs e relações foram preservados.")
            except Exception:
                target.rollback()
                raise
    finally:
        source.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
