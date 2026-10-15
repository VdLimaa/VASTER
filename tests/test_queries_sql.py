"""Executa cada .sql de db/queries contra um Postgres de verdade.

Pulado quando VASTER_TEST_DSN não está definido, então 'pytest' continua
rodando sem banco e sem rede. Este teste existe porque SQL quebrado não é
pego por teste de função pura: a consulta do masterset passou a análise
estática e falhou no Postgres com AmbiguousParameter, por um parâmetro sem
cast dentro de 'is null'.

    createdb vaster_test
    VASTER_TEST_DSN=postgresql://postgres@localhost:5432/vaster_test pytest
"""

import os
import pathlib

import pytest

psycopg = pytest.importorskip("psycopg")

DSN = os.environ.get("VASTER_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="VASTER_TEST_DSN não definido")

QUERIES = pathlib.Path(__file__).parent.parent / "db" / "queries"

# Todo parâmetro que qualquer .sql de db/queries possa pedir. O teste manda
# só os que a consulta usa, então a lista pode crescer sem quebrar as antigas.
PARAMS = {
    "slug": "sableye",
    "user_id": None,
    "include_absent": False,
    "include_digital": False,
    "languages": None,
    "set_id": None,
    "region": None,
    "species": None,
    "kinds": None,
    "status": None,
    "serie": None,
    "rarities": None,
    "ano_de": None,
    "ano_ate": None,
    "busca": None,
    "limite": 10,
    "forma": None,
    "categoria": None,
    "trainer_type": None,
    "tipos": None,
    "sufixo": None,
    "estagio": None,
    "forma_kind": None,
    "card_forma": None,
    "card_estagio": None,
}


@pytest.fixture(scope="module")
def conn():
    from psycopg.rows import dict_row

    from ingest.db import migrate

    with psycopg.connect(DSN, row_factory=dict_row) as c:
        migrate(c, verbose=False)
        yield c


@pytest.mark.parametrize("arquivo", sorted(p.name for p in QUERIES.glob("*.sql")))
def test_consulta_executa(conn, arquivo):
    """Banco vazio devolve zero linhas; o que importa é o Postgres aceitar."""
    sql = (QUERIES / arquivo).read_text(encoding="utf-8")
    usados = {k: v for k, v in PARAMS.items() if f"%({k})s" in sql}
    with conn.cursor() as cur:
        cur.execute(sql, usados)
        cur.fetchall()
    conn.rollback()


def test_migrations_sao_idempotentes(conn):
    from ingest.db import migrate

    assert migrate(conn, verbose=False) == []


def test_promover_sem_prova_e_rejeitado(conn):
    """A constraint que sustenta 'toda promoção exige source_url'."""
    with conn.cursor() as cur:
        cur.execute("""
            insert into card_set (tcgdex_id, serie, name_en)
            values ('zz-test', 'zz', 'Teste') returning id
        """)
        set_id = cur.fetchone()["id"]
        cur.execute(
            """
            insert into card (tcgdex_id, set_id, number, name_en)
            values ('zz-test-1', %s, '1', 'Teste') returning id
            """,
            (set_id,),
        )
        card_id = cur.fetchone()["id"]
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                """
                insert into card_variant (card_id, kind, language, exists_state)
                values (%s, 'regular', 'pt', 'confirmed')
                """,
                (card_id,),
            )
    conn.rollback()


def test_unlikely_dispensa_prova(conn):
    """Relato de fórum não tem URL e ainda assim é informação."""
    with conn.cursor() as cur:
        cur.execute("""
            insert into card_set (tcgdex_id, serie, name_en)
            values ('zz-test2', 'zz', 'Teste') returning id
        """)
        set_id = cur.fetchone()["id"]
        cur.execute(
            """
            insert into card (tcgdex_id, set_id, number, name_en)
            values ('zz-test2-1', %s, '1', 'Teste') returning id
            """,
            (set_id,),
        )
        card_id = cur.fetchone()["id"]
        cur.execute(
            """
            insert into card_variant (card_id, kind, language, exists_state)
            values (%s, 'regular', 'pt', 'unlikely') returning id
            """,
            (card_id,),
        )
        assert cur.fetchone()["id"]
    conn.rollback()
