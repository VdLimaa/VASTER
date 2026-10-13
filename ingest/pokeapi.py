"""Lista de espécies da PokéAPI.

Só os números da dex e os slugs vêm daqui. Nome de exibição sai do slug com
a tabela de irregulares em species.py, o que evita 1.025 requisições só para
descobrir maiúsculas.

name_pt recebe o mesmo valor de name_en de propósito: nome de Pokémon não é
traduzido no Brasil. Quem joga em português compra 'Sableye', não 'Olho-Vivo'.
A coluna existe para o dia em que isso deixar de ser verdade.
"""

from __future__ import annotations

import httpx

from .species import Especie, nome_de_slug


async def listar_especies(
    base: str = "https://pokeapi.co/api/v2",
    *,
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> list[Especie]:
    proprio = client is None
    client = client or httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    try:
        r = await client.get(f"{base.rstrip('/')}/pokemon-species", params={"limit": 2000})
        r.raise_for_status()
        dados = r.json()
    finally:
        if proprio:
            await client.aclose()

    especies: list[Especie] = []
    for item in dados.get("results", []):
        slug = item["name"]
        try:
            dex = int(item["url"].rstrip("/").rsplit("/", 1)[-1])
        except ValueError:
            continue
        nome = nome_de_slug(slug)
        especies.append(Especie(dex_number=dex, slug=slug, name_en=nome, name_pt=nome))
    return especies
