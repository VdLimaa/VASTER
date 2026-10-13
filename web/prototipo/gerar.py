#!/usr/bin/env python3
"""Gera o protótipo da tela de masterset a partir do banco.

É um HTML solto, sem build, para validar a interação antes de escrever a tela
de verdade em Next.js na F2. O filtro de idioma aqui roda no cliente sobre os
slots já carregados; na F2 ele vira o parâmetro `languages` de
db/queries/masterset.sql, que já existe e já é testado.

    python web/prototipo/gerar.py --species sableye
    python web/prototipo/gerar.py --species tyranitar --out /tmp/tyranitar.html
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ))

from ingest.config import Config  # noqa: E402
from ingest.db import connect, query  # noqa: E402

# Só o que a tela usa. Preço e status entram quando a F3 e o login existirem.
CAMPOS = (
    "set_id", "set_name", "serie_name", "set_release", "number", "card_name",
    "rarity", "kind", "language", "exists_state", "has_pt_scan", "notes",
    "source_url", "card_id", "set_count_official", "image_url",
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--species", required=True, help="slug da espécie")
    p.add_argument("--out", type=pathlib.Path, help="padrão: web/prototipo/<slug>.html")
    p.add_argument("--include-digital", action="store_true",
                   help="inclui Pokémon TCG Pocket, que não é carta impressa")
    args = p.parse_args()

    cfg = Config.from_env()
    with connect(cfg.dsn) as conn, conn.cursor() as cur:
        cur.execute("select name_pt, name_en from species where slug = %s", (args.species,))
        especie = cur.fetchone()
        if not especie:
            p.error(f"espécie '{args.species}' não está no banco; rode 'python -m ingest species'")
        cur.execute(
            query("masterset"),
            {
                "slug": args.species,
                "user_id": None,
                "include_absent": False,
                "include_digital": args.include_digital,
                "languages": None,
            },
        )
        linhas = cur.fetchall()

    if not linhas:
        p.error(
            f"nenhum slot para '{args.species}'. Rode details, links e slots "
            f"para a espécie antes."
        )

    slots = [{k: linha.get(k) for k in CAMPOS} for linha in linhas]
    nome = especie["name_pt"] or especie["name_en"]
    sets = len({s["set_id"] for s in slots})

    template = (pathlib.Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    html = (
        template.replace("__SLOTS__", json.dumps(slots, ensure_ascii=False, default=str,
                                                 separators=(",", ":")))
        .replace("__TITULO__", f"Masterset {nome}")
        .replace("__NOME__", nome)
        .replace("__N_SLOTS__", str(len(slots)))
        .replace("__N_SETS__", str(sets))
        .replace("__SLUG__", args.species)
    )

    destino = args.out or (pathlib.Path(__file__).parent / f"{args.species}.html")
    destino.write_text(html, encoding="utf-8")
    confirmados = sum(1 for s in slots if s["exists_state"] == "confirmed")
    print(
        f"{destino}: {len(slots)} slots em {sets} coleções, "
        f"{confirmados} confirmados"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
