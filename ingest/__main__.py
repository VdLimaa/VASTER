"""CLI da ingestão.

    python -m ingest migrate
    python -m ingest species
    python -m ingest sets
    python -m ingest cards
    python -m ingest details --species sableye
    python -m ingest links   --species sableye
    python -m ingest slots   --species sableye
    python -m ingest gate    --species sableye

O scheduler da F2 chama exatamente estes comandos. Enquanto a F0 estiver
sendo validada, rode na mão.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from . import pipeline
from .config import Config
from .db import connect, migrate, query, refresh_price_current
from .pokeapi import listar_especies


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m ingest", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("migrate", help="aplica as migrations pendentes")
    sub.add_parser("species", help="popula species a partir da PokéAPI")
    sub.add_parser("sets", help="ingere sets e o overlay de nome em PT")
    sub.add_parser("cards", help="ingere todas as cartas (2 requisições)")
    sub.add_parser("refresh", help="recalcula a materialized view de preço")
    sub.add_parser("coverage", help="relatório de cobertura PT por era")

    d = sub.add_parser("details", help="busca variants/rarity/dexId por carta")
    _escopo(d)
    d.add_argument("--refazer", action="store_true", help="rebusca o que já tem detalhe")
    d.add_argument("--limite", type=int, help="para no N-ésimo (útil para testar)")

    li = sub.add_parser("links", help="preenche card_species")
    li.add_argument("--species")
    li.add_argument("--all", action="store_true", dest="todas")

    s = sub.add_parser("slots", help="gera os slots de variante")
    _escopo(s)
    s.add_argument("--langs", default="en,pt", help="idiomas dos slots (padrão en,pt)")
    s.add_argument(
        "--no-auto-confirm-pt",
        action="store_false",
        dest="auto_confirmar_pt",
        help="não promove o slot principal em PT mesmo com scan no TCGdex",
    )

    g = sub.add_parser("gate", help="verifica o gate da F0 para uma espécie")
    g.add_argument("--species", default="sableye")

    m = sub.add_parser("masterset", help="imprime o masterset de uma espécie")
    m.add_argument("--species", required=True)
    m.add_argument("--user", type=int, help="id do usuário para trazer o status")
    m.add_argument(
        "--lang",
        help="idiomas separados por vírgula ('pt', 'pt,en'). Padrão: todos",
    )
    m.add_argument("--include-absent", action="store_true")
    m.add_argument("--include-digital", action="store_true")
    m.add_argument("--json", action="store_true", help="saída em JSON")

    args = p.parse_args(argv)
    cfg = Config.from_env()

    with connect(cfg.dsn) as conn:
        if args.cmd == "migrate":
            novas = migrate(conn)
            print(
                f"migrate: {len(novas)} migrations aplicadas"
                if novas
                else "migrate: nada pendente"
            )
            return 0

        if args.cmd == "species":
            especies = asyncio.run(listar_especies(cfg.pokeapi_base, timeout=cfg.timeout))
            print(pipeline.gravar_especies(conn, especies))
            return 0

        if args.cmd == "sets":
            print(asyncio.run(pipeline.ingerir_sets(conn, cfg)))
            return 0

        if args.cmd == "cards":
            print(asyncio.run(pipeline.ingerir_cartas(conn, cfg)))
            return 0

        if args.cmd == "details":
            print(
                asyncio.run(
                    pipeline.ingerir_detalhes(
                        conn,
                        cfg,
                        species_slug=args.species,
                        set_id=args.set,
                        todas=args.todas,
                        refazer=args.refazer,
                        limite=args.limite,
                    )
                )
            )
            return 0

        if args.cmd == "links":
            print(pipeline.ligar_especies(conn, species_slug=args.species, todas=args.todas))
            return 0

        if args.cmd == "slots":
            idiomas = tuple(x.strip() for x in args.langs.split(",") if x.strip())
            print(
                pipeline.gerar(
                    conn,
                    cfg,
                    species_slug=args.species,
                    set_id=args.set,
                    todas=args.todas,
                    idiomas=idiomas,
                    auto_confirmar_pt=args.auto_confirmar_pt,
                )
            )
            return 0

        if args.cmd == "refresh":
            refresh_price_current(conn)
            print("refresh: price_current recalculada")
            return 0

        if args.cmd == "coverage":
            _coverage(conn)
            return 0

        if args.cmd == "masterset":
            _masterset(conn, args)
            return 0

        if args.cmd == "gate":
            return _gate(conn, args.species)

    return 0


def _escopo(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--species", help="slug da espécie")
    sp.add_argument("--set", help="tcgdex_id do set")
    sp.add_argument("--all", action="store_true", dest="todas")


def _coverage(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            select st.serie, min(st.serie_name) as serie_name,
                   min(st.serie_released) as lancada,
                   count(distinct st.id) as sets,
                   count(distinct st.id) filter (where st.pt_card_count > 0) as sets_pt,
                   count(c.id) as cartas_en,
                   count(c.id) filter (where c.has_pt) as cartas_pt
            from card_set st left join card c on c.set_id = st.id
            group by st.serie order by min(st.serie_released) nulls first, st.serie
        """)
        linhas = cur.fetchall()
    print(f"{'série':<26} {'lançada':<11} {'sets':>5} {'c/PT':>5} {'EN':>7} {'PT':>7} {'%':>5}")
    print("-" * 72)
    ten = tpt = 0
    for r in linhas:
        ten += r["cartas_en"]
        tpt += r["cartas_pt"]
        pct = 100 * r["cartas_pt"] / r["cartas_en"] if r["cartas_en"] else 0
        print(
            f"{(r['serie_name'] or r['serie'])[:26]:<26} "
            f"{str(r['lancada'] or '-'):<11} {r['sets']:>5} {r['sets_pt']:>5} "
            f"{r['cartas_en']:>7} {r['cartas_pt']:>7} {pct:>4.0f}%"
        )
    print("-" * 72)
    print(f"{'TOTAL':<26} {'':<11} {'':>5} {'':>5} {ten:>7} {tpt:>7} "
          f"{100 * tpt / ten if ten else 0:>4.0f}%")


def _masterset(conn, args) -> None:
    idiomas = (
        [x.strip() for x in args.lang.split(",") if x.strip()] if args.lang else None
    )
    with conn.cursor() as cur:
        cur.execute(
            query("masterset"),
            {
                "slug": args.species,
                "user_id": args.user,
                "include_absent": args.include_absent,
                "include_digital": args.include_digital,
                "languages": idiomas,
            },
        )
        linhas = cur.fetchall()

    if args.json:
        # default=str converte date e Decimal. É o mesmo payload que a rota
        # GET /species/{slug}/masterset vai devolver na F2.
        print(json.dumps(linhas, ensure_ascii=False, indent=2, default=str))
        return

    if not linhas:
        print(f"nenhum slot para '{args.species}'")
        return
    print(f"{'coleção':<30} {'nº':>6} {'variante':<14} {'id':<3} {'estado':<10} {'preço':>9}")
    print("-" * 80)
    for r in linhas:
        preco = f"R$ {r['median_brl']:.2f}" if r["median_brl"] else "-"
        print(
            f"{(r['set_name'] or '')[:30]:<30} {r['number']:>6} {r['kind']:<14} "
            f"{r['language']:<3} {r['exists_state']:<10} {preco:>9}"
        )
    print("-" * 80)
    por_idioma: dict[str, int] = {}
    for r in linhas:
        por_idioma[r["language"]] = por_idioma.get(r["language"], 0) + 1
    detalhe = ", ".join(f"{n} em {lang}" for lang, n in sorted(por_idioma.items()))
    print(f"{len(linhas)} slots ({detalhe})")


def _gate(conn, slug: str) -> int:
    """Gate da F0, do documento: 'Sableye traz todas as coleções conhecidas,
    sem duplicata e com a Tag Team ligada às duas espécies'."""
    ok = True
    print(f"=== Gate da F0 — espécie '{slug}' ===\n")

    with conn.cursor() as cur:
        cur.execute("select id, dex_number, name_en from species where slug = %s", (slug,))
        esp = cur.fetchone()
        if not esp:
            print(f"FALHOU: espécie '{slug}' não existe na tabela species")
            return 1
        print(f"espécie: {esp['name_en']} (dex {esp['dex_number']})\n")

        cur.execute(query("gate_f0"), {"slug": slug})
        colecoes = cur.fetchall()
        fisicas = [r for r in colecoes if not r["is_digital"]]
        digitais = [r for r in colecoes if r["is_digital"]]
        print(f"--- coleções físicas: {len(fisicas)} ---")
        for r in fisicas:
            print(
                f"  {str(r['release_date'] or '-'):<11} {r['set_id']:<10} "
                f"{(r['set_name'] or '')[:32]:<32} {r['cartas']:>2} carta(s)  "
                f"PT:{r['pt_release']:<7} {r['pt_card_count']:>4} cartas PT no set"
            )
        if not fisicas:
            ok = False
            print("  FALHOU: nenhuma coleção física")
        if digitais:
            print(
                f"\n--- Pokémon TCG Pocket (app, fora do masterset): "
                f"{len(digitais)} ---"
            )
            for r in digitais:
                print(f"  {str(r['release_date'] or '-'):<11} {r['set_id']:<10} "
                      f"{(r['set_name'] or '')[:32]:<32} {r['cartas']:>2} carta(s)")

        cur.execute("""
            select count(*) as cartas from card c
            join card_species csp on csp.card_id = c.id
            join species s on s.id = csp.species_id where s.slug = %s
        """, (slug,))
        total_cartas = cur.fetchone()["cartas"]

        cur.execute(query("gate_f0_duplicatas"), {"slug": slug})
        dups = cur.fetchall()
        print(f"\n--- duplicatas: {len(dups)} (esperado 0) ---")
        for r in dups:
            ok = False
            print(f"  FALHOU: {r['tcgdex_id']} aparece {r['vinculos']}x")

        cur.execute(query("gate_f0_multiespecie"), {"slug": slug})
        multi = cur.fetchall()
        print(f"\n--- cartas multiespécie: {len(multi)} ---")
        for r in multi:
            print(
                f"  {r['tcgdex_id']:<12} {r['name_en'][:38]:<38} "
                f"{r['especies']} via {r['resolvido_por']}"
            )
        if not multi:
            print("  (nenhuma — se a espécie tem Tag Team ou Mega dupla, isso é falha)")

        cur.execute("""
            select v.language::text as lang, v.kind::text as kind,
                   v.exists_state::text as estado, count(*) as n
            from card_variant v
            join card_species csp on csp.card_id = v.card_id
            join species s on s.id = csp.species_id
            where s.slug = %s
            group by 1,2,3 order by 1,2,3
        """, (slug,))
        slots = cur.fetchall()
        total_slots = sum(r["n"] for r in slots)
        print(f"\n--- slots gerados: {total_slots} em {total_cartas} cartas ---")
        for r in slots:
            print(f"  {r['lang']:<3} {r['kind']:<14} {r['estado']:<10} {r['n']:>4}")

        cur.execute("""
            select count(*) as n from card c
            join card_species csp on csp.card_id = c.id
            join species s on s.id = csp.species_id
            where s.slug = %s and c.details_at is null
        """, (slug,))
        sem_detalhe = cur.fetchone()["n"]
        if sem_detalhe:
            ok = False
            print(f"\nFALHOU: {sem_detalhe} cartas sem detalhe. Rode 'details --species {slug}'.")

    print("\n" + ("GATE PASSOU" if ok else "GATE FALHOU"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
