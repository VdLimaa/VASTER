"""Vocabulários de filtro e o recorte do binder.

Os rótulos são os que o colecionador brasileiro usa, não os do enum. Ninguém
procura 'alt_art': procura 'arte especial' ou 'full art'. O enum continua
sendo a verdade no banco; isto é a tradução para a tela.
"""

from __future__ import annotations

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


def regioes(conn) -> list[dict]:
    """As regiões, com quantas espécies e quantos slots cada uma tem."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select s.region,
                   count(distinct s.id) as especies,
                   count(v.id) as slots
            from species s
            left join card_species csp on csp.species_id = s.id
            left join card_variant v on v.card_id = csp.card_id
            where s.region is not null
            group by s.region
            order by min(s.dex_number)
            """
        )
        return [
            {
                "valor": r["region"],
                "nome": NOME_REGIAO.get(r["region"], r["region"].title()),
                "especies": r["especies"],
                "slots": r["slots"],
            }
            for r in cur.fetchall()
        ]


def tipos(conn, *, set_id: str | None = None) -> list[dict]:
    """Os grupos de tipo que de fato existem no recorte, com contagem.

    Mostrar um filtro que não filtra nada é pior que não mostrar: o grupo só
    entra na lista se houver slot dele.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            select v.kind::text as kind, count(*) as n
            from card_variant v
            join card c on c.id = v.card_id
            join card_set cs on cs.id = c.set_id
            where v.exists_state <> 'absent'
              and (%(set_id)s::text is null or cs.tcgdex_id = %(set_id)s)
            group by v.kind
            """,
            {"set_id": set_id},
        )
        por_kind = {r["kind"]: r["n"] for r in cur.fetchall()}

    saida = []
    for chave, (rotulo, kinds) in GRUPOS_DE_TIPO.items():
        n = sum(por_kind.get(k, 0) for k in kinds)
        if n:
            saida.append({"valor": chave, "nome": rotulo, "slots": n})
    return saida


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


def binder(
    conn,
    *,
    set_id: str | None = None,
    region: str | None = None,
    species: str | None = None,
    tipo: list[str] | None = None,
    idiomas: list[str] | None = None,
    user_id: int | None = None,
    incluir_absent: bool = False,
    incluir_digital: bool = False,
) -> dict:
    """O recorte do masterset, com o resumo de progresso junto.

    Está aqui, e não na rota, porque o snapshot estático (`api/snapshot.py`)
    precisa gravar exatamente o mesmo payload que a rota devolve. Dois
    cálculos de resumo seriam duas verdades.
    """
    idiomas = idiomas or ["pt"]
    with conn.cursor() as cur:
        cur.execute(
            query("binder"),
            {
                "user_id": user_id,
                "set_id": set_id,
                "region": region,
                "species": species,
                "kinds": kinds_do_grupo(tipo),
                "languages": idiomas or None,
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
            "colecao": set_id,
            "regiao": region,
            "regiao_nome": NOME_REGIAO.get(region or "", region),
            "especie": species,
            "tipo": tipo,
            "idioma": idiomas,
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
