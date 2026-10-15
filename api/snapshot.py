"""Snapshot estático da tela: alguns recortes prontos, gravados como JSON.

A tela responde qualquer recorte porque pergunta ao Postgres. Isto aqui é o
contrário: um punhado de recortes já calculados num arquivo, para a tela abrir
**sem backend nenhum** — `npm run dev` e pronto, sem Docker, sem Python, sem
ingestão.

Serve a três coisas:

* quem quer só *ver* o projeto antes de instalar qualquer coisa;
* a hospedagem estática (Vercel não tem Postgres);
* demonstrar os sinais que são o ponto do projeto — "sem foto" e "fora do
  catálogo" — com coleções escolhidas justamente por terem esses casos.

O payload de cada recorte é o mesmo que `GET /api/binder` devolve, porque sai
da mesma função (`consultas.binder`). Se a rota mudar, o snapshot muda junto.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from dataclasses import dataclass

from . import consultas


@dataclass(frozen=True)
class Recorte:
    chave: str
    nome: str
    nota: str
    idioma: str
    colecao: str | None = None
    regiao: str | None = None
    tipo: str | None = None


# Português primeiro, que é o ponto do projeto. Cada recorte existe para
# mostrar uma coisa diferente, e a nota diz qual.
RECORTES: tuple[Recorte, ...] = (
    Recorte(
        chave="151-kanto-arte",
        nome="151 · Kanto · arte especial",
        nota="O recorte que motivou o projeto: as illustration rares de Pokémon "
        "de Kanto na coleção 151, em português.",
        idioma="pt",
        colecao="sv03.5",
        regiao="kanto",
        tipo="arte",
    ),
    Recorte(
        chave="151-tudo",
        nome="151 · masterset inteiro",
        nota="Todos os slots da coleção 151 em português — é o masterset "
        "completo dela.",
        idioma="pt",
        colecao="sv03.5",
    ),
    Recorte(
        chave="me05",
        nome="Escuridão Absoluta",
        nota="Coleção recente, 100% catalogada em português e com scan de "
        "todas as cartas.",
        idioma="pt",
        colecao="me05",
    ),
    Recorte(
        chave="30th-classica",
        nome="30 Anos · Coleção Clássica",
        nota="As 30 cartas estão no catálogo em português e nenhuma tem foto "
        "ainda: é o caso 'sem foto', que já dá para confirmar.",
        idioma="pt",
        colecao="30th-c",
    ),
    Recorte(
        chave="base1",
        nome="Base Set (1999)",
        nota="O TCGdex não tem uma única carta em português antes de 2011, e o "
        "Brasil recebeu essa coleção. Todo slot aqui é 'fora do catálogo' — "
        "é o que a curadoria existe para resolver.",
        idioma="pt",
        colecao="base1",
    ),
    Recorte(
        chave="151-en",
        nome="151 · em inglês",
        nota="A mesma coleção no catálogo inglês, para comparar com o "
        "português.",
        idioma="en",
        colecao="sv03.5",
    ),
    Recorte(
        chave="151-ja",
        nome="151 · em japonês",
        nota="O japonês é outro catálogo, com ids próprios: a 151 japonesa é "
        "a coleção SV2a, não uma tradução da ocidental.",
        idioma="ja",
        colecao="SV2a",
    ),
)


def gerar(conn, recortes: tuple[Recorte, ...] = RECORTES) -> dict:
    """Monta o snapshot. Recorte que não devolve slot nenhum fica de fora:
    chip vazio na tela é pior que chip a menos."""
    saida = []
    for r in recortes:
        dados = consultas.binder(
            conn,
            set_id=r.colecao,
            region=r.regiao,
            tipo=[r.tipo] if r.tipo else None,
            idiomas=[r.idioma],
        )
        if not dados["slots"]:
            continue
        saida.append({"chave": r.chave, "nome": r.nome, "nota": r.nota, **dados})

    return {
        "gerado_em": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "saude": consultas.saude(conn),
        "idiomas": [{"valor": k, "nome": v} for k, v in consultas.IDIOMAS.items()],
        "recortes": saida,
    }


def gravar(conn, destino: pathlib.Path) -> tuple[int, int]:
    """Grava o snapshot e devolve (recortes, bytes)."""
    dados = gerar(conn)
    destino.parent.mkdir(parents=True, exist_ok=True)
    # default=str resolve date e Decimal; ensure_ascii=False mantém o arquivo
    # legível e menor, já que quase todo nome tem acento ou kana.
    texto = json.dumps(dados, default=str, ensure_ascii=False)
    destino.write_text(texto, encoding="utf-8")
    return len(dados["recortes"]), len(texto.encode())
