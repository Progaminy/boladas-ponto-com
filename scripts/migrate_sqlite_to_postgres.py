#!/usr/bin/env python3
"""Copy Boladas data from SQLite to an already-migrated PostgreSQL/Supabase DB.

Usage:
    DATABASE_URL='postgresql://...' python scripts/migrate_sqlite_to_postgres.py

Optional:
    python scripts/migrate_sqlite_to_postgres.py --sqlite /path/posts.db --database-url 'postgresql://...'

Schema migrations are deliberately NOT run here. In production the Boladas
runtime database role only has data privileges (SELECT/INSERT/UPDATE/DELETE),
not CREATE/ALTER/DROP. Apply schema changes through Supabase migrations first,
then use this script only to copy existing SQLite rows.

The operation is idempotent: primary/unique-key conflicts are left untouched.
It preserves IDs, copies tables in foreign-key order, verifies row counts, and
rolls back the PostgreSQL transaction on any error.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]

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


def verify_target_schema(conn: psycopg.Connection) -> None:
    missing: list[str] = []
    for table in TABLES:
        if not postgres_columns(conn, table):
            missing.append(table)
    if missing:
        raise RuntimeError(
            "Schema PostgreSQL ainda não foi migrado. Tabelas em falta: "
            + ", ".join(missing)
        )


def count_sqlite(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def count_postgres(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        return int(cur.fetchone()[0])


def migrate_table(
    source: sqlite3.Connection,
    target: psycopg.Connection,
    table: str,
) -> tuple[int, int]:
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
    parser = argparse.ArgumentParser(description="Migrar dados Boladas SQLite -> PostgreSQL/Supabase")
    parser.add_argument("--sqlite", default=str(ROOT / "data" / "posts.db"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite).expanduser().resolve()
    database_url = args.database_url.strip()

    if not sqlite_path.exists():
        print(f"ERRO: SQLite não encontrado: {sqlite_path}")
        return 2
    if not database_url.startswith(("postgres://", "postgresql://")):
        print("ERRO: fornece DATABASE_URL PostgreSQL/Supabase válido.")
        return 2

    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row

    print(f"Origem SQLite: {sqlite_path}")
    print("Destino PostgreSQL: ligação recebida (credenciais ocultas)")

    try:
        with psycopg.connect(database_url, autocommit=False) as target:
            try:
                verify_target_schema(target)
                print("Schema PostgreSQL já existente e verificado.")

                failures: list[str] = []
                for table in TABLES:
                    source_exists = bool(sqlite_columns(source, table))
                    before_source = count_sqlite(source, table) if source_exists else 0
                    copied, after_target = migrate_table(source, target, table)
                    # A execução pode ser repetida; o destino pode legitimamente
                    # ter mais linhas do que a origem graças a execuções anteriores.
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
