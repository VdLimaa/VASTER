"""Vocabulários de filtro e o recorte do binder.

Os rótulos são os que o colecionador brasileiro usa, não os do enum. Ninguém
procura 'alt_art': procura 'arte especial' ou 'full art'. O enum continua
sendo a verdade no banco; isto é a tradução para a tela.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Query

from ingest.db import query
from ingest.species import NOME_REGIAO

# Agrupa os tipos de slot como o colecionador pensa. A chave é o que vai na
# URL; os valores são os kinds do enum que entram no filtro.
GRUPOS_DE_TIPO: dict[str, tuple[str, tuple[str, ...]]] = {
    "normal": ("Normal", ("regular",)),
    "reverse": ("Reverse holo (RF)", ("reverse_holo",)),
    "holo": ("Holo", ("holo",)),
    "arte": ("Arte especial / full art", ("alt_art", "full_art")),
    "secreta": ("Rainbow e gold", ("rainbow", "gold")),
    "shiny": ("Shiny", ("shiny",)),
    "promo": ("Promo", ("promo",)),
    "primeira": ("1ª edição", ("first_edition",)),
}

IDIOMAS = {
    "pt": "Português",
    "en": "Inglês",
    "ja": "Japonês",
}

# Raridade a tela mostra como o catálogo escreve, traduzindo só o que tem
# tradução exata. 'Holo Rare' e 'Rare Holo' são dois valores diferentes no
# TCGdex, de eras diferentes — juntar os dois num rótulo só esconderia isso.
RARIDADE_PT = {
    "Common": "Comum",
    "Uncommon": "Incomum",
    "Rare": "Rara",
    "Promo": "Promo",
    "None": "Sem raridade",
}


@dataclass(frozen=True)
class Recorte:
    """O recorte do fichário: o que todas as consultas da tela compartilham.

    Vira dependência do FastAPI, então cada campo é um parâmetro de query. As
    três consultas — slots, facetas e coleções — leem os mesmos filtros, e
    tê-los num lugar só é o que impede uma ficar para trás da outra.
    """

    idioma: Annotated[list[str] | None, Query()] = None
    colecao: str | None = None
    regiao: str | None = None
    especie: str | None = None
    era: str | None = None
    tipo: Annotated[list[str] | None, Query()] = None
    raridade: Annotated[list[str] | None, Query()] = None
    ano_de: int | None = None
    ano_ate: int | None = None
    incluir_absent: bool = False
    incluir_digital: bool = False

    @property
    def idiomas(self) -> list[str]:
        """Português é o padrão em toda rota. Quem quer outro, pede."""
        return self.idioma or ["pt"]

    def tem_escopo(self) -> bool:
        """Sem nenhum destes, o recorte seria o catálogo inteiro."""
        return bool(self.colecao or self.regiao or self.especie or self.era)

    def sql(self, user_id: int | None = None) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "set_id": self.colecao,
            "region": self.regiao,
            "species": self.especie,
            "serie": self.era,
            "rarities": self.raridade or None,
            "ano_de": self.ano_de,
            "ano_ate": self.ano_ate,
            "kinds": kinds_do_grupo(self.tipo),
            "languages": self.idiomas,
            "status": None,
            "include_absent": self.incluir_absent,
            "include_digital": self.incluir_digital,
        }


def kinds_do_grupo(grupos: list[str] | None) -> list[str] | None:
    """Traduz os grupos da URL para os kinds do enum."""
    if not grupos:
        return None
    kinds: list[str] = []
    for g in grupos:
        par = GRUPOS_DE_TIPO.get(g)
        if par:
            kinds.extend(k for k in par[1] if k not in kinds)
    return kinds or None


def saude(conn) -> dict:
    """As contagens do catálogo. A tela mostra no subtítulo e o script de
    instalação usa para saber se precisa ingerir ou só atualizar."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select (select count(*) from card_set)     as colecoes,
                   (select count(*) from card)         as cartas,
                   (select count(*) from card_variant) as slots,
                   (select count(*) from species where region is not null) as especies
            """
        )
        return dict(cur.fetchone())


def binder(conn, recorte: Recorte, *, user_id: int | None = None) -> dict:
    """O recorte do masterset, com o resumo de progresso junto.

    Está aqui, e não na rota, porque o snapshot estático (`api/snapshot.py`)
    precisa gravar exatamente o mesmo payload que a rota devolve. Dois
    cálculos de resumo seriam duas verdades.
    """
    with conn.cursor() as cur:
        cur.execute(query("binder"), recorte.sql(user_id))
        slots = [dict(r) for r in cur.fetchall()]

    tenho = sum(1 for s in slots if s["status"] == "owned")
    quero = sum(1 for s in slots if s["status"] == "wanted")
    return {
        "recorte": {
            "colecao": recorte.colecao,
            "regiao": recorte.regiao,
            "regiao_nome": NOME_REGIAO.get(recorte.regiao or "", recorte.regiao),
            "especie": recorte.especie,
            "era": recorte.era,
            "tipo": recorte.tipo,
            "raridade": recorte.raridade,
            "ano_de": recorte.ano_de,
            "ano_ate": recorte.ano_ate,
            "idioma": recorte.idiomas,
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


def colecoes(conn, recorte: Recorte, busca: str | None = None) -> list[dict]:
    """As coleções que sobram no recorte, com quantos slots cada uma tem."""
    with conn.cursor() as cur:
        cur.execute(query("binder_colecoes"), recorte.sql())
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


def especies(conn, busca: str | None = None, regiao: str | None = None, limite: int = 40):
    """As espécies, para o campo de busca do masterset por Pokémon."""
    with conn.cursor() as cur:
        cur.execute(
            query("especies"),
            {"busca": busca.strip() if busca else None, "region": regiao, "limite": limite},
        )
        return [
            {
                "valor": r["slug"],
                "nome": r["name_en"] or r["name_ja"] or r["slug"].title(),
                "dex": r["dex_number"],
                "nome_ja": r["name_ja"],
                "regiao": r["region"],
                "regiao_nome": NOME_REGIAO.get(r["region"] or "", r["region"]),
            }
            for r in cur.fetchall()
        ]


def facetas(conn, recorte: Recorte) -> dict[str, list[dict]]:
    """O que ainda existe no recorte, por dimensão, com contagem.

    Uma requisição e uma consulta para cinco listas. Cada faceta é contada
    ignorando o próprio filtro, então trocar de era ou de ano não exige
    limpar o recorte antes — ver o comentário de `db/queries/facetas.sql`.
    """
    with conn.cursor() as cur:
        cur.execute(query("facetas"), recorte.sql())
        linhas = [dict(r) for r in cur.fetchall()]

    por_dim: dict[str, list[dict]] = {d: [] for d in ("era", "ano", "raridade", "tipo", "regiao")}
    for r in linhas:
        por_dim.setdefault(r["dim"], []).append(r)

    # O tipo é o único que não sai pronto: a tela filtra por grupo
    # ('arte' = alt_art + full_art) e a consulta conta por kind.
    por_kind = {r["valor"]: r["n"] for r in por_dim["tipo"]}
    tipos = [
        {"valor": chave, "nome": rotulo, "slots": n}
        for chave, (rotulo, kinds) in GRUPOS_DE_TIPO.items()
        if (n := sum(por_kind.get(k, 0) for k in kinds))
    ]

    return {
        # Era é linha do tempo, não ranking: ordena pelo ano mais antigo.
        "eras": [
            {"valor": r["valor"], "nome": r["valor"], "slots": r["n"], "desde": r["ordem"]}
            for r in sorted(por_dim["era"], key=lambda r: (r["ordem"] is None, r["ordem"]))
        ],
        "anos": [
            {"valor": r["valor"], "nome": r["valor"], "slots": r["n"]}
            for r in sorted(por_dim["ano"], key=lambda r: r["valor"], reverse=True)
        ],
        "raridades": [
            {"valor": r["valor"], "nome": RARIDADE_PT.get(r["valor"], r["valor"]), "slots": r["n"]}
            for r in por_dim["raridade"]
        ],
        "tipos": tipos,
        "regioes": [
            {
                "valor": r["valor"],
                "nome": NOME_REGIAO.get(r["valor"], r["valor"].title()),
                "slots": r["n"],
            }
            for r in por_dim["regiao"]
        ],
    }
