"""API do Masterset BR.

    uvicorn api.main:app --reload

Nenhuma rota consulta API externa. O app lê só o Postgres, que o job de
ingestão alimenta — é a decisão do documento de arquitetura, e é o que faz a
tela responder rápido mesmo com 89 mil slots.

Português é o padrão em toda rota. Quem quer inglês ou japonês pede.
"""

from __future__ import annotations

import pathlib
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ingest.config import Config
from ingest.db import connect, query
from ingest.species import NOME_REGIAO

from . import consultas

RAIZ = pathlib.Path(__file__).resolve().parent.parent
# O React compilado. Em desenvolvimento o Vite serve a tela em :5173 e
# repassa /api para cá; em produção o FastAPI serve o dist e sobe um processo só.
WEB = RAIZ / "web" / "app" / "dist"

app = FastAPI(
    title="Masterset BR",
    description="Todos os slots de variante que compõem o masterset de um recorte.",
    version="0.1.0",
)
cfg = Config.from_env()


def banco():
    with connect(cfg.dsn) as conn:
        yield conn


Conn = Annotated[object, Depends(banco)]


@app.get("/api/saude")
def saude(conn: Conn) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            select (select count(*) from card_set)     as colecoes,
                   (select count(*) from card)         as cartas,
                   (select count(*) from card_variant) as slots,
                   (select count(*) from species where region is not null) as especies
            """
        )
        return {"ok": True, **dict(cur.fetchone())}


@app.get("/api/regioes")
def rota_regioes(conn: Conn) -> list[dict]:
    return consultas.regioes(conn)


@app.get("/api/idiomas")
def rota_idiomas() -> list[dict]:
    return [{"valor": k, "nome": v} for k, v in consultas.IDIOMAS.items()]


@app.get("/api/tipos")
def rota_tipos(conn: Conn, colecao: str | None = None) -> list[dict]:
    return consultas.tipos(conn, set_id=colecao)


@app.get("/api/colecoes")
def rota_colecoes(
    conn: Conn,
    regiao: str | None = None,
    idioma: Annotated[list[str] | None, Query()] = None,
    incluir_digital: bool = False,
    busca: str | None = None,
) -> list[dict]:
    """As coleções que têm slot no recorte pedido."""
    idioma = idioma or ["pt"]
    with conn.cursor() as cur:
        cur.execute(
            query("binder_colecoes"),
            {
                "region": regiao,
                "languages": idioma or None,
                "include_digital": incluir_digital,
            },
        )
        linhas = [dict(r) for r in cur.fetchall()]
    if busca:
        alvo = busca.strip().lower()
        linhas = [
            r
            for r in linhas
            if alvo in (r["set_name"] or "").lower()
            or alvo in (r["name_en"] or "").lower()
            or alvo in (r["set_id"] or "").lower()
        ]
    return linhas


@app.get("/api/binder")
def rota_binder(
    conn: Conn,
    colecao: str | None = None,
    regiao: str | None = None,
    especie: str | None = None,
    tipo: Annotated[list[str] | None, Query()] = None,
    idioma: Annotated[list[str] | None, Query()] = None,
    usuario: int | None = None,
    incluir_absent: bool = False,
    incluir_digital: bool = False,
) -> dict:
    """O recorte do masterset, com o resumo de progresso junto.

    Sem nenhum filtro isto devolveria os 89 mil slots do catálogo, o que não
    serve para ninguém e derruba a tela. Pelo menos um recorte é obrigatório.
    """
    idioma = idioma or ["pt"]
    if not any((colecao, regiao, especie)):
        raise HTTPException(
            status_code=400,
            detail="Escolha pelo menos uma coleção, região ou espécie.",
        )

    with conn.cursor() as cur:
        cur.execute(
            query("binder"),
            {
                "user_id": usuario,
                "set_id": colecao,
                "region": regiao,
                "species": especie,
                "kinds": consultas.kinds_do_grupo(tipo),
                "languages": idioma or None,
                "status": None,
                "include_absent": incluir_absent,
                "include_digital": incluir_digital,
            },
        )
        slots = [dict(r) for r in cur.fetchall()]

    tenho = sum(1 for s in slots if s["status"] == "owned")
    quero = sum(1 for s in slots if s["status"] == "wanted")
    return {
        "recorte": {
            "colecao": colecao,
            "regiao": regiao,
            "regiao_nome": NOME_REGIAO.get(regiao or "", regiao),
            "especie": especie,
            "tipo": tipo,
            "idioma": idioma,
        },
        "resumo": {
            "slots": len(slots),
            "cartas": len({s["card_id"] for s in slots}),
            "colecoes": len({s["set_id"] for s in slots}),
            "tenho": tenho,
            "quero": quero,
            "falta": len(slots) - tenho,
            "confirmados": sum(1 for s in slots if s["exists_state"] == "confirmed"),
            "inferidos": sum(1 for s in slots if s["created_by"] == "inferred"),
            "sem_foto": sum(1 for s in slots if s["no_catalogo"] and not s["has_scan"]),
            "fora_do_catalogo": sum(1 for s in slots if not s["no_catalogo"]),
        },
        "slots": slots,
    }


if (WEB / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(WEB / "assets")), name="assets")

    @app.get("/")
    def pagina() -> FileResponse:
        return FileResponse(WEB / "index.html")

else:

    @app.get("/")
    def sem_build() -> dict:
        return {
            "erro": "A tela ainda não foi compilada.",
            "faca": "cd web/app && npm install && npm run build",
            "ou": "cd web/app && npm run dev  (Vite em :5173, com proxy para esta API)",
        }
