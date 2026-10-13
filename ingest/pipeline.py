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
                insert into species (dex_number, slug, name_en, name_pt)
                values (%s, %s, %s, %s)
                on conflict (dex_number) do update
                  set slug = excluded.slug,
                      name_en = excluded.name_en,
                      name_pt = excluded.name_pt
                returning (xmax = 0) as novo
                """,
                (e.dex_number, e.slug, e.name_en, e.name_pt),
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
        cur.execute("select dex_number, slug, name_en, name_pt from species")
        return IndiceEspecies([Especie(**r) for r in cur.fetchall()])


# --------------------------------------------------------------------------
# sets
# --------------------------------------------------------------------------


async def ingerir_sets(conn: psycopg.Connection, cfg: Config) -> Resultado:
    """Sets em inglês com série e data, mais o overlay de nome em português.

    pt_release vira 'yes' quando o set aparece em /pt/sets. A ausência NÃO
    vira 'no': o documento é explícito que ausência na API não prova
    inexistência, e a medição de cobertura confirma — base1 aparece em
    /pt/sets com zero cartas em PT, e o Brasil recebeu a Coleção Básica.
    """
    res = Resultado("sets")
    async with TCGdex(cfg.tcgdex_base, concurrency=cfg.concurrency, timeout=cfg.timeout) as api:
        series = await api.series(cfg.lang_en)
        serie_de_set: dict[str, tuple[str, str, dt.date | None]] = {}
        detalhes = await asyncio.gather(
            *(api.serie_detail(cfg.lang_en, s["id"]) for s in series)
        )
        for s, det in zip(series, detalhes, strict=True):
            if not det:
                continue
            lancamento = _data(det.get("releaseDate"))
            for st in det.get("sets", []):
                serie_de_set[st["id"]] = (s["id"], s.get("name") or s["id"], lancamento)

        resumos_en = await api.sets(cfg.lang_en)
        resumos_pt = await api.sets(cfg.lang_pt)
        nome_pt = {s["id"]: s.get("name") for s in resumos_pt}

        completos = await asyncio.gather(
            *(api.set_detail(cfg.lang_en, s["id"]) for s in resumos_en)
        )

        # Cobertura PT por set em uma requisição, em vez de uma por set.
        cartas_pt = await api.all_cards(cfg.lang_pt)

    set_ids = sorted({s["id"] for s in resumos_en}, key=len, reverse=True)
    pt_por_set: dict[str, int] = defaultdict(int)
    for c in cartas_pt:
        sid = _set_de_carta(c["id"], set_ids)
        if sid:
            pt_por_set[sid] += 1

    with conn.cursor() as cur:
        for resumo, det in zip(resumos_en, completos, strict=True):
            sid = resumo["id"]
            d = det or resumo
            serie, serie_nome, serie_data = serie_de_set.get(sid, (None, None, None))
            serie = serie or (d.get("serie") or {}).get("id") or "?"
            contagem = d.get("cardCount") or {}
            cur.execute(
                """
                insert into card_set (
                  tcgdex_id, serie, serie_name, serie_released, name_en, name_pt,
                  release_date, count_official, count_total, symbol_url, logo_url,
                  is_digital, pt_release, pt_card_count
                ) values (
                  %(id)s, %(serie)s, %(serie_name)s, %(serie_released)s, %(name_en)s,
                  %(name_pt)s, %(release_date)s, %(official)s, %(total)s, %(symbol)s,
                  %(logo)s, %(digital)s, %(pt_release)s, %(pt_count)s
                )
                on conflict (tcgdex_id) do update set
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
                    "serie": serie,
                    "serie_name": serie_nome,
                    "serie_released": serie_data,
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

    com_nome_sem_carta = sorted(s for s in nome_pt if pt_por_set.get(s, 0) == 0)
    res.observacoes.append(
        f"{len(nome_pt)} sets listados em /{cfg.lang_pt}/sets, "
        f"{len(com_nome_sem_carta)} deles sem nenhuma carta em PT"
    )
    if com_nome_sem_carta:
        res.observacoes.append(
            "fila de curadoria no nível de set: " + ", ".join(com_nome_sem_carta[:12])
            + ("..." if len(com_nome_sem_carta) > 12 else "")
        )
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


async def ingerir_cartas(conn: psycopg.Connection, cfg: Config) -> Resultado:
    """Todas as cartas dos dois idiomas em duas requisições.

    O endpoint em lote /{lang}/cards devolve id, localId, name e image. Falta
    variants, rarity e dexId, que vêm no passo 'details'.
    """
    res = Resultado("cards")
    async with TCGdex(cfg.tcgdex_base, concurrency=cfg.concurrency, timeout=cfg.timeout) as api:
        en, pt = await asyncio.gather(
            api.all_cards(cfg.lang_en), api.all_cards(cfg.lang_pt)
        )

    with conn.cursor() as cur:
        cur.execute("select id, tcgdex_id from card_set")
        set_db = {r["tcgdex_id"]: r["id"] for r in cur.fetchall()}
    set_ids = sorted(set_db, key=len, reverse=True)

    pt_por_id = {c["id"]: c for c in pt}

    with conn.cursor() as cur:
        for c in en:
            sid = _set_de_carta(c["id"], set_ids)
            if sid is None:
                res.ignorados += 1
                continue
            p = pt_por_id.get(c["id"])
            numero = str(c.get("localId") or "")
            cur.execute(
                """
                insert into card (
                  tcgdex_id, set_id, number, number_sort, name_en, name_pt,
                  image_url, image_url_pt, has_pt
                ) values (
                  %(id)s, %(set_id)s, %(number)s, %(number_sort)s, %(name_en)s,
                  %(name_pt)s, %(image)s, %(image_pt)s, %(has_pt)s
                )
                on conflict (tcgdex_id) do update set
                  set_id = excluded.set_id,
                  number = excluded.number,
                  number_sort = excluded.number_sort,
                  name_en = excluded.name_en,
                  name_pt = coalesce(excluded.name_pt, card.name_pt),
                  image_url = coalesce(excluded.image_url, card.image_url),
                  image_url_pt = coalesce(excluded.image_url_pt, card.image_url_pt),
                  has_pt = excluded.has_pt or card.has_pt
                returning (xmax = 0) as novo
                """,
                {
                    "id": c["id"],
                    "set_id": set_db[sid],
                    "number": numero,
                    "number_sort": _num_sort(numero),
                    "name_en": c.get("name") or "?",
                    "name_pt": (p or {}).get("name"),
                    "image": image_url(c.get("image")),
                    "image_pt": image_url((p or {}).get("image")),
                    "has_pt": p is not None,
                },
            )
            row = cur.fetchone()
            if row and row["novo"]:
                res.inseridos += 1
            else:
                res.atualizados += 1
    conn.commit()

    res.observacoes.append(
        f"{len(en)} cartas em {cfg.lang_en}, {len(pt)} em {cfg.lang_pt} "
        f"({100 * len(pt) / max(len(en), 1):.0f}% de cobertura)"
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
    refazer: bool = False,
    limite: int | None = None,
) -> Resultado:
    """GET /cards/{id} por carta: variants, variants_detailed, rarity,
    category e dexId. É o passo caro, então sempre escopado."""
    res = Resultado("details")
    alvos = await _alvos(conn, cfg, species_slug=species_slug, set_id=set_id, todas=todas)
    if not refazer:
        with conn.cursor() as cur:
            cur.execute(
                "select tcgdex_id from card where details_at is not null and tcgdex_id = any(%s)",
                (alvos,),
            )
            prontas = {r["tcgdex_id"] for r in cur.fetchall()}
        res.ignorados = len(prontas)
        alvos = [a for a in alvos if a not in prontas]
    if limite:
        alvos = alvos[:limite]
    if not alvos:
        res.observacoes.append("nada a buscar")
        return res

    async with TCGdex(cfg.tcgdex_base, concurrency=cfg.concurrency, timeout=cfg.timeout) as api:
        en = await asyncio.gather(*(api.card(cfg.lang_en, cid) for cid in alvos))
        com_pt = [cid for cid, d in zip(alvos, en, strict=True) if d]
        pt = await asyncio.gather(*(api.card(cfg.lang_pt, cid) for cid in com_pt))
    pt_por_id = {cid: d for cid, d in zip(com_pt, pt, strict=True) if d}

    with conn.cursor() as cur:
        for cid, d in zip(alvos, en, strict=True):
            if not d:
                res.ignorados += 1
                continue
            p = pt_por_id.get(cid)
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
                  has_pt = %(has_pt)s or card.has_pt,
                  image_url_pt = coalesce(%(image_pt)s, card.image_url_pt),
                  details_at = now()
                where tcgdex_id = %(id)s
                """,
                {
                    "id": cid,
                    "rarity_en": d.get("rarity"),
                    "rarity_pt": (p or {}).get("rarity"),
                    "category": d.get("category"),
                    "illustrator": d.get("illustrator"),
                    "variants": psycopg.types.json.Jsonb(d.get("variants") or {}),
                    "variants_detailed": psycopg.types.json.Jsonb(
                        d.get("variants_detailed") or []
                    ),
                    "dex_id": d.get("dexId") or None,
                    "has_pt": p is not None,
                    "image_pt": image_url((p or {}).get("image")),
                },
            )
            res.atualizados += cur.rowcount
    conn.commit()
    return res


async def _alvos(
    conn: psycopg.Connection,
    cfg: Config,
    *,
    species_slug: str | None,
    set_id: str | None,
    todas: bool,
) -> list[str]:
    if species_slug:
        with conn.cursor() as cur:
            cur.execute("select dex_number from species where slug = %s", (species_slug,))
            row = cur.fetchone()
        if not row:
            raise SystemExit(
                f"espécie '{species_slug}' não está na tabela species. "
                f"Rode 'python -m ingest species' primeiro."
            )
        async with TCGdex(
            cfg.tcgdex_base, concurrency=cfg.concurrency, timeout=cfg.timeout
        ) as api:
            cartas = await api.cards_by_dex(cfg.lang_en, row["dex_number"])
        return [c["id"] for c in cartas]

    with conn.cursor() as cur:
        if set_id:
            cur.execute(
                """
                select c.tcgdex_id from card c
                join card_set s on s.id = c.set_id
                where s.tcgdex_id = %s order by c.number_sort nulls last, c.number
                """,
                (set_id,),
            )
        elif todas:
            cur.execute("select tcgdex_id from card order by tcgdex_id")
        else:
            raise SystemExit("escolha --species, --set ou --all")
        return [r["tcgdex_id"] for r in cur.fetchall()]


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
                select c.id, c.tcgdex_id, c.name_en, c.category_en, c.api_dex_id
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
                select id, tcgdex_id, name_en, category_en, api_dex_id
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
                achados = indice.casar(c["name_en"] or "")
                dex = [e.dex_number for e in achados]
                resolvedor = "name_match"
            if not dex:
                res.ignorados += 1
                res.observacoes.append(f"sem espécie: {c['tcgdex_id']} {c['name_en']!r}")
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
            select id, serie, kind::text, language::text, rarity_regex,
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
    idiomas: tuple[str, ...] = ("en", "pt"),
    auto_confirmar_pt: bool = True,
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

        cur.execute(
            f"""
            select c.id, c.tcgdex_id, c.rarity_en, c.api_variants,
                   c.api_variants_detailed, c.has_pt, c.image_url_pt,
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
                image_url_pt=r["image_url_pt"],
                serie=r["serie"],
                set_release=r["release_date"],
                set_pt_release=r["pt_release"],
            )
            slots = gerar_slots(
                carta,
                politicas,
                idiomas=idiomas,
                auto_confirmar_pt=auto_confirmar_pt,
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
                        values (%s, null, %s, %s, 'generator:tcgdex-pt', %s)
                        """,
                        (
                            novo["id"],
                            s.exists_state,
                            s.source_url,
                            "promovido em lote: o TCGdex tem esta carta em português",
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
