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

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ingest.config import Config
from ingest.db import connect

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
def rota_saude(conn: Conn) -> dict:
    return {"ok": True, **consultas.saude(conn)}


@app.get("/api/idiomas")
def rota_idiomas() -> list[dict]:
    return [{"valor": k, "nome": v} for k, v in consultas.IDIOMAS.items()]


@app.get("/api/facetas")
def rota_facetas(conn: Conn, recorte: Annotated[consultas.Recorte, Depends()]) -> dict:
    """Era, ano, raridade, tipo e região que ainda existem no recorte.

    Uma requisição para as cinco listas, e cada uma conta ignorando o próprio
    filtro — por isso trocar de era não exige limpar o recorte antes.
    """
    return consultas.facetas(conn, recorte)


@app.get("/api/especies")
def rota_especies(
    conn: Conn,
    busca: str | None = None,
    regiao: str | None = None,
    limite: int = 40,
) -> list[dict]:
    """As espécies, para montar o masterset de um Pokémon. Casa por nome em
    inglês, por nome japonês, pelo slug e pelo número da Pokédex."""
    return consultas.especies(conn, busca=busca, regiao=regiao, limite=min(limite, 200))


@app.get("/api/colecoes")
def rota_colecoes(
    conn: Conn,
    recorte: Annotated[consultas.Recorte, Depends()],
    busca: str | None = None,
) -> list[dict]:
    """As coleções que têm slot no recorte pedido."""
    return consultas.colecoes(conn, recorte, busca=busca)


@app.get("/api/binder")
def rota_binder(
    conn: Conn,
    recorte: Annotated[consultas.Recorte, Depends()],
    usuario: int | None = None,
) -> dict:
    """O recorte do masterset, com o resumo de progresso junto.

    Sem nenhum filtro isto devolveria os 89 mil slots do catálogo, o que não
    serve para ninguém e derruba a tela. Pelo menos um recorte é obrigatório.
    """
    if not recorte.tem_escopo():
        raise HTTPException(
            status_code=400,
            detail="Escolha pelo menos uma coleção, região, espécie ou era.",
        )
    return consultas.binder(conn, recorte, user_id=usuario)


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
