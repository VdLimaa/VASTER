"""Os passos da ingestão. Cada um é um comando do CLI e é idempotente.

Ordem para a F0:
    migrate -> species -> sets -> cards -> details -> links -> slots

A divisão não é arbitrária. 'cards' custa 2 requisições para 23.736 cartas,
porque o TCGdex tem endpoint em lote. 'details' custa 1 requisição por carta,
porque variants só existe no detalhe. Separar os dois é o que deixa a
ingestão retomável e permite fechar o gate do Sableye com 35 requisições em
vez de 23.736.

Regra inviolável: o job nunca sobrescreve curadoria. Toda escrita em
card_variant é ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re
from collections import defaultdict
from dataclasses import dataclass

import psycopg

from .config import Config
from .species import Especie, IndiceEspecies, eh_pokemon
from .tcgdex import TCGdex, image_url
from .variants import Carta, Politica, gerar_slots

# A série do Pokémon TCG Pocket é app, não carta impressa. Fica no catálogo
# para não mentir sobre o que o TCGdex tem, mas sai do masterset físico.
SERIES_DIGITAIS = frozenset({"tcgp"})

# Quantas cartas por lote no passo 'details'. O lote existe para gravar e
# commitar incrementalmente: o catálogo japonês tem 12.781 cartas e perder
# seis minutos de coleta por uma falha no fim seria burrice.
LOTE_DETALHES = 400


def _num_sort(numero: str) -> int | None:
    m = re.search(r"\d+", numero or "")
    return int(m.group()) if m else None


def _set_de_carta(card_id: str, set_ids: list[str]) -> str | None:
    """O id da carta é '{set}-{localId}', e localId pode ter hífen
    ('swshp-SWSH001'). Casar pelo prefixo mais longo resolve sv03 vs sv03.5."""
    for sid in set_ids:
        if card_id.startswith(f"{sid}-"):
            return sid
    return None


@dataclass
class Resultado:
    passo: str
    inseridos: int = 0
    atualizados: int = 0
    ignorados: int = 0
    observacoes: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.observacoes is None:
            self.observacoes = []

    def __str__(self) -> str:
        base = (
            f"{self.passo}: {self.inseridos} novos, "
            f"{self.atualizados} atualizados, {self.ignorados} ignorados"
        )
        return "\n".join([base, *(f"    {o}" for o in self.observacoes)])


# --------------------------------------------------------------------------
# espécies
# --------------------------------------------------------------------------


def gravar_especies(conn: psycopg.Connection, especies: list[Especie]) -> Resultado:
    res = Resultado("species")
    with conn.cursor() as cur:
        for e in especies:
            cur.execute(
                """
                insert into species (dex_number, slug, name_en, name_pt, name_ja)
                values (%s, %s, %s, %s, %s)
                on conflict (dex_number) do update
                  set slug = excluded.slug,
                      name_en = excluded.name_en,
                      name_pt = excluded.name_pt,
                      name_ja = coalesce(excluded.name_ja, species.name_ja)
                returning (xmax = 0) as novo
                """,
                (e.dex_number, e.slug, e.name_en, e.name_pt, e.name_ja),
            )
            row = cur.fetchone()
            if row and row["novo"]:
                res.inseridos += 1
            else:
                res.atualizados += 1
    conn.commit()
    return res


def carregar_indice(conn: psycopg.Connection) -> IndiceEspecies:
    with conn.cursor() as cur:
        cur.execute("select dex_number, slug, name_en, name_pt, name_ja from species")
        return IndiceEspecies([Especie(**r) for r in cur.fetchall()])


# --------------------------------------------------------------------------
# sets
# --------------------------------------------------------------------------


async def ingerir_sets(
    conn: psycopg.Connection, cfg: Config, *, region: str = "west"
) -> Resultado:
    """Sets de uma região.

    No oeste o inglês é a espinha e o português é overlay. No Japão não há
    overlay: o catálogo é outro, com ids próprios, e o único idioma é o
    japonês. Por isso a chave de card_set é (tcgdex_id, region) — 'neo1'
    existe nos dois e são coleções diferentes.

    pt_release vira 'yes' quando o set aparece em /pt/sets. A ausência NÃO
    vira 'no': o documento é explícito que ausência na API não prova
    inexistência, e a medição de cobertura confirma — base1 aparece em
    /pt/sets com zero cartas em PT, e o Brasil recebeu a Coleção Básica.
    """
    res = Resultado(f"sets[{region}]")
    lang = cfg.lang_ja if region == "jp" else cfg.lang_en

    async with TCGdex(cfg.tcgdex_base, concurrency=cfg.concurrency, timeout=cfg.timeout) as api:
        series = await api.series(lang)
        serie_de_set: dict[str, tuple[str, str, dt.date | None]] = {}
        detalhes = await asyncio.gather(
            *(api.serie_detail(lang, s["id"]) for s in series)
        )
        for s, det in zip(series, detalhes, strict=True):
            if not det:
                continue
            lancamento = _data(det.get("releaseDate"))
            for st in det.get("sets", []):
                serie_de_set[st["id"]] = (s["id"], s.get("name") or s["id"], lancamento)

        resumos = await api.sets(lang)
        completos = await asyncio.gather(
            *(api.set_detail(lang, s["id"]) for s in resumos)
        )

        nome_pt: dict[str, str | None] = {}
        pt_por_set: dict[str, int] = defaultdict(int)
        if region == "west":
            resumos_pt = await api.sets(cfg.lang_pt)
            nome_pt = {s["id"]: s.get("name") for s in resumos_pt}
            # Cobertura PT por set em uma requisição, em vez de uma por set.
            cartas_pt = await api.all_cards(cfg.lang_pt)
            set_ids = sorted({s["id"] for s in resumos}, key=len, reverse=True)
            for c in cartas_pt:
                sid = _set_de_carta(c["id"], set_ids)
                if sid:
                    pt_por_set[sid] += 1

    with conn.cursor() as cur:
        for resumo, det in zip(resumos, completos, strict=True):
            sid = resumo["id"]
            d = det or resumo
            serie, serie_nome, serie_data = serie_de_set.get(sid, (None, None, None))
            serie = serie or (d.get("serie") or {}).get("id") or "?"
            contagem = d.get("cardCount") or {}
            cur.execute(
                """
                insert into card_set (
                  tcgdex_id, region, serie, serie_name, serie_released, name_en,
                  name_pt, release_date, count_official, count_total, symbol_url,
                  logo_url, is_digital, pt_release, pt_card_count
                ) values (
                  %(id)s, %(region)s, %(serie)s, %(serie_name)s, %(serie_released)s,
                  %(name_en)s, %(name_pt)s, %(release_date)s, %(official)s, %(total)s,
                  %(symbol)s, %(logo)s, %(digital)s, %(pt_release)s, %(pt_count)s
                )
                on conflict (tcgdex_id, region) do update set
                  serie = excluded.serie,
                  serie_name = excluded.serie_name,
                  serie_released = excluded.serie_released,
                  name_en = excluded.name_en,
                  name_pt = coalesce(excluded.name_pt, card_set.name_pt),
                  release_date = excluded.release_date,
                  count_official = excluded.count_official,
                  count_total = excluded.count_total,
                  symbol_url = excluded.symbol_url,
                  logo_url = excluded.logo_url,
                  is_digital = excluded.is_digital,
                  -- 'yes' só sobe, nunca desce: ausência não é prova.
                  pt_release = case
                    when excluded.pt_release = 'yes' then 'yes'
                    else card_set.pt_release end,
                  pt_card_count = excluded.pt_card_count,
                  ingested_at = now()
                returning (xmax = 0) as novo
                """,
                {
                    "id": sid,
                    "region": region,
                    "serie": serie,
                    "serie_name": serie_nome,
                    "serie_released": serie_data,
                    # No catálogo japonês este campo guarda o nome japonês:
                    # é o único nome que a coleção tem.
                    "name_en": d.get("name") or sid,
                    "name_pt": nome_pt.get(sid),
                    "release_date": _data(d.get("releaseDate")),
                    "official": contagem.get("official"),
                    "total": contagem.get("total"),
                    "symbol": d.get("symbol"),
                    "logo": d.get("logo"),
                    "digital": serie in SERIES_DIGITAIS,
                    "pt_release": "yes" if sid in nome_pt else "unknown",
                    "pt_count": pt_por_set.get(sid, 0),
                },
            )
            row = cur.fetchone()
            if row and row["novo"]:
                res.inseridos += 1
            else:
                res.atualizados += 1
    conn.commit()

    if region == "west":
        com_nome_sem_carta = sorted(s for s in nome_pt if pt_por_set.get(s, 0) == 0)
        res.observacoes.append(
            f"{len(nome_pt)} sets listados em /{cfg.lang_pt}/sets, "
            f"{len(com_nome_sem_carta)} deles sem nenhuma carta em PT"
        )
        if com_nome_sem_carta:
            res.observacoes.append(
                "fila de curadoria no nível de set: "
                + ", ".join(com_nome_sem_carta[:12])
                + ("..." if len(com_nome_sem_carta) > 12 else "")
            )
    else:
        res.observacoes.append(f"{len(resumos)} coleções no catálogo japonês")
    return res


def _data(valor: str | None) -> dt.date | None:
    if not valor:
        return None
    for formato in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return dt.datetime.strptime(valor, formato).date()
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# cartas
# --------------------------------------------------------------------------


async def ingerir_cartas(
    conn: psycopg.Connection, cfg: Config, *, region: str = "west"
) -> Resultado:
    """Todas as cartas de uma região em uma ou duas requisições.

    O endpoint em lote /{lang}/cards devolve id, localId, name e image. Falta
    variants, rarity e dexId, que vêm no passo 'details'.
    """
    res = Resultado(f"cards[{region}]")
    async with TCGdex(cfg.tcgdex_base, concurrency=cfg.concurrency, timeout=cfg.timeout) as api:
        if region == "jp":
            principal = await api.all_cards(cfg.lang_ja)
            traduzidas: dict[str, dict] = {}
        else:
            principal, pt = await asyncio.gather(
                api.all_cards(cfg.lang_en), api.all_cards(cfg.lang_pt)
            )
            traduzidas = {c["id"]: c for c in pt}

    with conn.cursor() as cur:
        cur.execute("select id, tcgdex_id from card_set where region = %s", (region,))
        set_db = {r["tcgdex_id"]: r["id"] for r in cur.fetchall()}
    set_ids = sorted(set_db, key=len, reverse=True)

    with conn.cursor() as cur:
        for c in principal:
            sid = _set_de_carta(c["id"], set_ids)
            if sid is None:
                res.ignorados += 1
                continue
            p = traduzidas.get(c["id"])
            numero = str(c.get("localId") or "")
            japonesa = region == "jp"
            cur.execute(
                """
                insert into card (
                  tcgdex_id, region, set_id, number, number_sort, name_en, name_pt,
                  name_ja, image_url, image_url_pt, image_url_ja, has_pt, has_ja
                ) values (
                  %(id)s, %(region)s, %(set_id)s, %(number)s, %(number_sort)s,
                  %(name_en)s, %(name_pt)s, %(name_ja)s, %(image)s, %(image_pt)s,
                  %(image_ja)s, %(has_pt)s, %(has_ja)s
                )
                on conflict (tcgdex_id, region) do update set
                  set_id = excluded.set_id,
                  number = excluded.number,
                  number_sort = excluded.number_sort,
                  name_en = coalesce(excluded.name_en, card.name_en),
                  name_pt = coalesce(excluded.name_pt, card.name_pt),
                  name_ja = coalesce(excluded.name_ja, card.name_ja),
                  image_url = coalesce(excluded.image_url, card.image_url),
                  image_url_pt = coalesce(excluded.image_url_pt, card.image_url_pt),
                  image_url_ja = coalesce(excluded.image_url_ja, card.image_url_ja),
                  has_pt = excluded.has_pt or card.has_pt,
                  has_ja = excluded.has_ja or card.has_ja
                returning (xmax = 0) as novo
                """,
                {
                    "id": c["id"],
                    "region": region,
                    "set_id": set_db[sid],
                    "number": numero,
                    "number_sort": _num_sort(numero),
                    # Carta japonesa não tem nome em inglês no TCGdex: /en/cards
                    # devolve 404 para SM7b-016 e S6K-028.
                    "name_en": None if japonesa else (c.get("name") or "?"),
                    "name_pt": (p or {}).get("name"),
                    "name_ja": c.get("name") if japonesa else None,
                    "image": None if japonesa else image_url(c.get("image")),
                    "image_pt": image_url((p or {}).get("image")),
                    "image_ja": image_url(c.get("image")) if japonesa else None,
                    "has_pt": p is not None,
                    # A carta está no catálogo japonês; é essa a evidência.
                    "has_ja": japonesa,
                },
            )
            row = cur.fetchone()
            if row and row["novo"]:
                res.inseridos += 1
            else:
                res.atualizados += 1
    conn.commit()

    if region == "jp":
        com_scan = sum(1 for c in principal if c.get("image"))
        res.observacoes.append(
            f"{len(principal)} cartas em {cfg.lang_ja}, {com_scan} com scan "
            f"({100 * com_scan / max(len(principal), 1):.0f}%)"
        )
    else:
        res.observacoes.append(
            f"{len(principal)} cartas em {cfg.lang_en}, {len(traduzidas)} em "
            f"{cfg.lang_pt} ({100 * len(traduzidas) / max(len(principal), 1):.0f}% "
            f"de cobertura)"
        )
    return res


# --------------------------------------------------------------------------
# detalhes
# --------------------------------------------------------------------------


async def ingerir_detalhes(
    conn: psycopg.Connection,
    cfg: Config,
    *,
    species_slug: str | None = None,
    set_id: str | None = None,
    todas: bool = False,
    region: str | None = None,
    refazer: bool = False,
    limite: int | None = None,
) -> Resultado:
    """GET /cards/{id} por carta: variants, variants_detailed, rarity,
    category e dexId. É o passo caro, então sempre escopado.

    Os alvos carregam a região junto do id porque os dois catálogos repetem
    ids: 'neo1-1' existe no oeste e no Japão, em coleções diferentes.
    """
    res = Resultado("details")
    alvos = await _alvos(
        conn, cfg, species_slug=species_slug, set_id=set_id, todas=todas, region=region
    )
    if not refazer and alvos:
        with conn.cursor() as cur:
            cur.execute(
                """
                select tcgdex_id, region from card
                where details_at is not null
                  and (tcgdex_id, region) in (
                    select * from unnest(%s::text[], %s::text[])
                  )
                """,
                ([a[0] for a in alvos], [a[1] for a in alvos]),
            )
            prontas = {(r["tcgdex_id"], r["region"]) for r in cur.fetchall()}
        res.ignorados = len(prontas)
        alvos = [a for a in alvos if a not in prontas]
    if limite:
        alvos = alvos[:limite]
    if not alvos:
        res.observacoes.append("nada a buscar")
        return res

    def lang_principal(reg: str) -> str:
        return cfg.lang_ja if reg == "jp" else cfg.lang_en

    # Em lotes, gravando e commitando a cada um. Com 12.781 cartas japonesas
    # um gather único seguraria tudo na memória e perderia o trabalho inteiro
    # numa falha no meio; assim o que já entrou fica, e details_at faz a
    # próxima execução continuar de onde parou.
    async with TCGdex(cfg.tcgdex_base, concurrency=cfg.concurrency, timeout=cfg.timeout) as api:
        for inicio in range(0, len(alvos), LOTE_DETALHES):
            lote = alvos[inicio : inicio + LOTE_DETALHES]
            await _gravar_lote_detalhes(conn, cfg, api, lote, lang_principal, res)
            if len(alvos) > LOTE_DETALHES:
                feitos = min(inicio + LOTE_DETALHES, len(alvos))
                print(f"    {feitos}/{len(alvos)} cartas", flush=True)
    return res


async def _gravar_lote_detalhes(
    conn: psycopg.Connection,
    cfg: Config,
    api: TCGdex,
    alvos: list[tuple[str, str]],
    lang_principal,
    res: Resultado,
) -> None:
    principais = await asyncio.gather(
        *(api.card(lang_principal(reg), cid) for cid, reg in alvos)
    )
    # O overlay em português só existe no catálogo do oeste.
    pede_pt = [
        cid
        for (cid, reg), d in zip(alvos, principais, strict=True)
        if d and reg == "west"
    ]
    pt = await asyncio.gather(*(api.card(cfg.lang_pt, cid) for cid in pede_pt))
    pt_por_id = {cid: d for cid, d in zip(pede_pt, pt, strict=True) if d}

    with conn.cursor() as cur:
        for (cid, reg), d in zip(alvos, principais, strict=True):
            if not d:
                res.ignorados += 1
                continue
            p = pt_por_id.get(cid)
            japonesa = reg == "jp"
            cur.execute(
                """
                update card set
                  rarity_en = %(rarity_en)s,
                  rarity_pt = coalesce(%(rarity_pt)s, card.rarity_pt),
                  category_en = %(category)s,
                  illustrator = %(illustrator)s,
                  api_variants = %(variants)s,
                  api_variants_detailed = %(variants_detailed)s,
                  api_dex_id = %(dex_id)s,
                  name_ja = coalesce(%(name_ja)s, card.name_ja),
                  has_pt = %(has_pt)s or card.has_pt,
                  has_ja = %(has_ja)s or card.has_ja,
                  image_url_pt = coalesce(%(image_pt)s, card.image_url_pt),
                  image_url_ja = coalesce(%(image_ja)s, card.image_url_ja),
                  details_at = now()
                where tcgdex_id = %(id)s and region = %(region)s
                """,
                {
                    "id": cid,
                    "region": reg,
                    # A raridade vem em inglês mesmo no catálogo japonês.
                    "rarity_en": d.get("rarity"),
                    "rarity_pt": (p or {}).get("rarity"),
                    "category": d.get("category"),
                    "illustrator": d.get("illustrator"),
                    "variants": psycopg.types.json.Jsonb(d.get("variants") or {}),
                    "variants_detailed": psycopg.types.json.Jsonb(
                        d.get("variants_detailed") or []
                    ),
                    "dex_id": d.get("dexId") or None,
                    "name_ja": d.get("name") if japonesa else None,
                    "has_pt": p is not None,
                    "has_ja": japonesa,
                    "image_pt": image_url((p or {}).get("image")),
                    "image_ja": image_url(d.get("image")) if japonesa else None,
                },
            )
            res.atualizados += cur.rowcount
    conn.commit()


async def ingerir_detalhes_bulk(conn: psycopg.Connection, cfg: Config) -> Resultado:
    """Detalhes de TODO o catálogo ocidental em uma requisição GraphQL.

    É o que torna o produto viável para as 1.025 espécies: o caminho REST
    custa uma requisição por carta, ~23.700 só no oeste. O GraphQL devolve
    id, variants, rarity, category, dexId e illustrator de todas elas de uma
    vez, em menos de um segundo.

    Duas coisas o GraphQL NÃO dá, e por isso o caminho carta a carta continua
    existindo:
      * variants_detailed, que traz o variantId e o preço por variante e é a
        fonte da F3;
      * rarity_pt, que só vem do detalhe em português.
    O catálogo japonês também fica de fora: o GraphQL não tem filtro de idioma
    e id japonês volta vazio.
    """
    res = Resultado("details[west/graphql]")
    async with TCGdex(cfg.tcgdex_base, concurrency=cfg.concurrency, timeout=cfg.timeout) as api:
        cartas = await api.todas_cartas_detalhadas()
    if not cartas:
        res.observacoes.append("GraphQL não devolveu nada")
        return res

    linhas = [
        (
            c.get("rarity"),
            c.get("category"),
            c.get("illustrator"),
            psycopg.types.json.Jsonb(c.get("variants") or {}),
            c.get("dexId") or None,
            c["id"],
        )
        for c in cartas
        if c.get("id")
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            update card set
              rarity_en = %s,
              category_en = %s,
              illustrator = coalesce(%s, card.illustrator),
              api_variants = %s,
              api_dex_id = %s,
              details_at = now()
            where tcgdex_id = %s and region = 'west'
            """,
            linhas,
        )
        res.atualizados = cur.rowcount if cur.rowcount and cur.rowcount > 0 else len(linhas)
    conn.commit()

    sem_dex = sum(1 for c in cartas if not c.get("dexId"))
    res.observacoes.append(
        f"{len(cartas)} cartas em 1 requisição GraphQL; {sem_dex} sem dexId "
        f"(Trainer, Energy e algumas antigas) caem no casamento por nome"
    )
    res.observacoes.append(
        "variants_detailed e rarity_pt não vêm por aqui: para o preço da F3, "
        "rode 'details' no caminho REST sobre o recorte que interessar"
    )
    return res


async def _alvos(
    conn: psycopg.Connection,
    cfg: Config,
    *,
    species_slug: str | None,
    set_id: str | None,
    todas: bool,
    region: str | None = None,
) -> list[tuple[str, str]]:
    """Pares (tcgdex_id, region) a buscar."""
    regioes = [region] if region else ["west", "jp"]

    if species_slug:
        with conn.cursor() as cur:
            cur.execute("select dex_number from species where slug = %s", (species_slug,))
            row = cur.fetchone()
        if not row:
            raise SystemExit(
                f"espécie '{species_slug}' não está na tabela species. "
                f"Rode 'python -m ingest species' primeiro."
            )
        alvos: list[tuple[str, str]] = []
        async with TCGdex(
            cfg.tcgdex_base, concurrency=cfg.concurrency, timeout=cfg.timeout
        ) as api:
            for reg in regioes:
                lang = cfg.lang_ja if reg == "jp" else cfg.lang_en
                cartas = await api.cards_by_dex(lang, row["dex_number"])
                alvos.extend((c["id"], reg) for c in cartas)
        return alvos

    with conn.cursor() as cur:
        if set_id:
            cur.execute(
                """
                select c.tcgdex_id, c.region from card c
                join card_set s on s.id = c.set_id
                where s.tcgdex_id = %s and c.region = any(%s)
                order by c.number_sort nulls last, c.number
                """,
                (set_id, regioes),
            )
        elif todas:
            cur.execute(
                "select tcgdex_id, region from card where region = any(%s) "
                "order by region, tcgdex_id",
                (regioes,),
            )
        else:
            raise SystemExit("escolha --species, --set ou --all")
        return [(r["tcgdex_id"], r["region"]) for r in cur.fetchall()]


async def atualizar(
    conn: psycopg.Connection, cfg: Config, *, verbose: bool = True
) -> list[Resultado]:
    """Pega o que entrou desde a última execução e para por aí.

    É o comando do scheduler. Todos os passos são idempotentes e o caro —
    details carta a carta no catálogo japonês — só toca carta sem details_at,
    então uma coleção japonesa nova custa ~100 requisições em vez de 12.781.

    Medido em 2026-10-14: o TCGdex tinha a coleção '30th', lançada 28 dias
    antes, completa em inglês e com o nome da coleção já em português. O
    overlay PT das cartas chega depois — 'me05', de 89 dias, estava 120/120 em
    português com scan. Ou seja: rodar isto uma vez por semana acompanha o
    inglês de perto e o português com algumas semanas de atraso, que é a
    latência da própria base.
    """
    antes = _retrato(conn)
    passos: list[Resultado] = []

    for regiao in ("west", "jp"):
        passos.append(await ingerir_sets(conn, cfg, region=regiao))
    for regiao in ("west", "jp"):
        passos.append(await ingerir_cartas(conn, cfg, region=regiao))

    # Oeste em uma requisição; japonês só nas cartas que ainda não têm detalhe.
    passos.append(await ingerir_detalhes_bulk(conn, cfg))
    passos.append(
        await ingerir_detalhes(conn, cfg, todas=True, region="jp", refazer=False)
    )

    passos.append(ligar_especies(conn, todas=True))
    passos.append(gerar(conn, cfg, todas=True))

    depois = _retrato(conn)
    resumo = Resultado("update")
    rotulos = {
        "colecoes": "coleções",
        "cartas": "cartas",
        "vinculos": "vínculos carta-espécie",
        "slots": "slots",
    }
    mudou = False
    for chave, rotulo in rotulos.items():
        delta = depois[chave] - antes[chave]
        if delta:
            mudou = True
            resumo.observacoes.append(f"+{delta} {rotulo} (total {depois[chave]})")
    if not mudou:
        resumo.observacoes.append("nada novo no catálogo")
    else:
        novas = _colecoes_novas(conn, antes["colecoes"])
        for linha in novas:
            resumo.observacoes.append(
                f"coleção nova: {linha['tcgdex_id']} [{linha['region']}] "
                f"{linha['nome']} ({linha['release_date']})"
            )
    passos.append(resumo)
    if verbose:
        for r in passos:
            print(r)
    return passos


def _retrato(conn: psycopg.Connection) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select (select count(*) from card_set)     as colecoes,
                   (select count(*) from card)         as cartas,
                   (select count(*) from card_species) as vinculos,
                   (select count(*) from card_variant) as slots
            """
        )
        return dict(cur.fetchone())


def _colecoes_novas(conn: psycopg.Connection, quantas_antes: int) -> list[dict]:
    """As coleções ingeridas mais recentemente, para o relatório dizer o que
    entrou em vez de só um número."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select tcgdex_id, region,
                   coalesce(name_pt, name_en) as nome, release_date
            from card_set
            order by ingested_at desc, id desc
            limit greatest(0, (select count(*) from card_set) - %s)
            """,
            (quantas_antes,),
        )
        return cur.fetchall()


# --------------------------------------------------------------------------
# vínculo carta-espécie
# --------------------------------------------------------------------------


def ligar_especies(
    conn: psycopg.Connection,
    *,
    species_slug: str | None = None,
    todas: bool = False,
) -> Resultado:
    """Preenche card_species a partir do dexId guardado, com casamento por
    nome só onde o dexId faltou. Trainer e Energy ficam de fora."""
    res = Resultado("links")
    indice = carregar_indice(conn)
    if not indice.por_dex:
        raise SystemExit("tabela species vazia. Rode 'python -m ingest species'.")

    with conn.cursor() as cur:
        if species_slug:
            cur.execute(
                """
                select c.id, c.tcgdex_id, c.name_en, c.name_ja, c.category_en,
                       c.api_dex_id
                from card c
                where c.details_at is not null
                  and c.api_dex_id && (
                    select array[dex_number] from species where slug = %s
                  )
                """,
                (species_slug,),
            )
        elif todas:
            cur.execute(
                """
                select id, tcgdex_id, name_en, name_ja, category_en, api_dex_id
                from card where details_at is not null
                """
            )
        else:
            raise SystemExit("escolha --species ou --all")
        cartas = cur.fetchall()

    with conn.cursor() as cur:
        cur.execute("select id, dex_number from species")
        id_por_dex = {r["dex_number"]: r["id"] for r in cur.fetchall()}

        for c in cartas:
            if not eh_pokemon(c["category_en"]):
                res.ignorados += 1
                continue
            dex = list(c["api_dex_id"] or [])
            resolvedor = "dex_id"
            if not dex:
                # Carta japonesa não tem name_en: o nome dela está em name_ja.
                achados = indice.casar(c["name_en"] or c["name_ja"] or "")
                dex = [e.dex_number for e in achados]
                resolvedor = "name_match"
            if not dex:
                res.ignorados += 1
                nome = c["name_en"] or c["name_ja"]
                res.observacoes.append(f"sem espécie: {c['tcgdex_id']} {nome!r}")
                continue
            for d in dex:
                sid = id_por_dex.get(d)
                if sid is None:
                    continue
                cur.execute(
                    """
                    insert into card_species (card_id, species_id, resolved_by)
                    values (%s, %s, %s)
                    on conflict (card_id, species_id) do update
                      set resolved_by = excluded.resolved_by
                    returning (xmax = 0) as novo
                    """,
                    (c["id"], sid, resolvedor),
                )
                row = cur.fetchone()
                if row and row["novo"]:
                    res.inseridos += 1
                else:
                    res.atualizados += 1
    conn.commit()
    if len(res.observacoes) > 10:
        extras = len(res.observacoes) - 10
        res.observacoes = res.observacoes[:10] + [f"... e outras {extras} cartas sem espécie"]
    return res


# --------------------------------------------------------------------------
# slots
# --------------------------------------------------------------------------


def carregar_politicas(conn: psycopg.Connection) -> list[Politica]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select id, serie, region, kind::text, language::text, rarity_regex,
                   min_set_release, max_set_release, allowed, annotate, reason, priority
            from variant_policy
            """
        )
        return [Politica(**r) for r in cur.fetchall()]


def gerar(
    conn: psycopg.Connection,
    cfg: Config,
    *,
    species_slug: str | None = None,
    set_id: str | None = None,
    todas: bool = False,
    region: str | None = None,
    idiomas: tuple[str, ...] = ("en", "pt", "ja"),
    auto_confirmar: bool = True,
) -> Resultado:
    """Gera os slots. ON CONFLICT DO NOTHING: curadoria nunca é sobrescrita."""
    res = Resultado("slots")
    politicas = carregar_politicas(conn)

    with conn.cursor() as cur:
        filtro, params = "c.details_at is not null", []
        if species_slug:
            filtro += """ and c.id in (
                select csp.card_id from card_species csp
                join species s on s.id = csp.species_id where s.slug = %s)"""
            params.append(species_slug)
        elif set_id:
            filtro += " and st.tcgdex_id = %s"
            params.append(set_id)
        elif not todas:
            raise SystemExit("escolha --species, --set ou --all")
        # A região é um recorte adicional, não um escopo por si: 'neo1' existe
        # nos dois catálogos e sem isso os dois entrariam no mesmo --set.
        if region:
            filtro += " and c.region = %s"
            params.append(region)

        cur.execute(
            f"""
            select c.id, c.tcgdex_id, c.rarity_en, c.api_variants,
                   c.api_variants_detailed, c.has_pt, c.has_ja,
                   c.image_url_pt, c.image_url_ja, c.region,
                   st.serie, st.release_date, st.pt_release
            from card c join card_set st on st.id = c.set_id
            where {filtro}
            order by c.tcgdex_id
            """,
            params,
        )
        cartas = cur.fetchall()

    vetos: list[str] = []
    with conn.cursor() as cur:
        for r in cartas:
            carta = Carta(
                tcgdex_id=r["tcgdex_id"],
                rarity_en=r["rarity_en"],
                api_variants=r["api_variants"],
                api_variants_detailed=r["api_variants_detailed"],
                has_pt=r["has_pt"],
                has_ja=r["has_ja"],
                image_url_pt=r["image_url_pt"],
                image_url_ja=r["image_url_ja"],
                region=r["region"],
                serie=r["serie"],
                set_release=r["release_date"],
                set_pt_release=r["pt_release"],
            )
            slots = gerar_slots(
                carta,
                politicas,
                idiomas=idiomas,
                auto_confirmar=auto_confirmar,
                base_api=cfg.tcgdex_base,
                lang_pt=cfg.lang_pt,
            )
            for s in slots:
                cur.execute(
                    """
                    insert into card_variant (
                      card_id, kind, language, exists_state, source_url, notes,
                      api_variant_id, checked_at, created_by
                    ) values (
                      %(card_id)s, %(kind)s, %(language)s, %(estado)s, %(fonte)s,
                      %(notas)s, %(variant_id)s, %(checked)s, 'generator'
                    )
                    on conflict (card_id, kind, language) do nothing
                    returning id
                    """,
                    {
                        "card_id": r["id"],
                        "kind": s.kind,
                        "language": s.language,
                        "estado": s.exists_state,
                        "fonte": s.source_url,
                        "notas": s.notes,
                        "variant_id": s.api_variant_id,
                        "checked": dt.datetime.now(dt.UTC)
                        if s.exists_state != "unknown"
                        else None,
                    },
                )
                novo = cur.fetchone()
                if novo is None:
                    res.ignorados += 1
                    continue
                res.inseridos += 1
                if s.exists_state != "unknown":
                    cur.execute(
                        """
                        insert into curation_event
                          (variant_id, from_state, to_state, source_url, actor, notes)
                        values (%s, null, %s, %s, %s, %s)
                        """,
                        (
                            novo["id"],
                            s.exists_state,
                            s.source_url,
                            f"generator:tcgdex-{s.language}",
                            "promovido em lote: o TCGdex tem esta carta em "
                            + ("português" if s.language == "pt" else "japonês"),
                        ),
                    )
            vetos.extend(carta.vetos)
    conn.commit()

    if vetos:
        por_razao: dict[str, int] = defaultdict(int)
        for v in vetos:
            por_razao[v.split(": ", 1)[-1]] += 1
        for razao, n in sorted(por_razao.items(), key=lambda x: -x[1]):
            res.observacoes.append(f"{n} slots vetados pela política: {razao}")
    return res
