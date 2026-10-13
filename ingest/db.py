"""Conexão e migrations. SQL em db/migrations é a fonte da verdade do schema."""

from __future__ import annotations

import pathlib
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "db" / "migrations"
QUERIES = ROOT / "db" / "queries"


@contextmanager
def connect(dsn: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        yield conn


def query(name: str) -> str:
    """Lê um .sql de db/queries. Nada de SQL grande embutido em Python."""
    return (QUERIES / f"{name}.sql").read_text(encoding="utf-8")


def migrate(conn: psycopg.Connection, *, verbose: bool = True) -> list[str]:
    """Aplica as migrations pendentes em ordem de nome. Idempotente."""
    with conn.cursor() as cur:
        cur.execute("""
            create table if not exists schema_migration (
              filename   text primary key,
              applied_at timestamptz not null default now()
            )
        """)
        conn.commit()
        cur.execute("select filename from schema_migration")
        aplicadas = {r["filename"] for r in cur.fetchall()}

    novas: list[str] = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name in aplicadas:
            continue
        with conn.cursor() as cur:
            cur.execute(path.read_text(encoding="utf-8"))
            cur.execute(
                "insert into schema_migration (filename) values (%s)", (path.name,)
            )
        conn.commit()
        novas.append(path.name)
        if verbose:
            print(f"  aplicada {path.name}")
    return novas


def refresh_price_current(conn: psycopg.Connection) -> None:
    """CONCURRENTLY exige o índice único criado em 0004; sem ele o refresh
    bloqueia a leitura do app. Na primeira vez a view está vazia e o
    CONCURRENTLY falha, então cai para o refresh normal."""
    with conn.cursor() as cur:
        try:
            cur.execute("refresh materialized view concurrently price_current")
        except psycopg.errors.ObjectNotInPrerequisiteState:
            conn.rollback()
            cur.execute("refresh materialized view price_current")
    conn.commit()
