"""Lista de espécies da PokéAPI.

Só os números da dex e os slugs vêm daqui. Nome de exibição sai do slug com
a tabela de irregulares em species.py, o que evita 1.025 requisições só para
descobrir maiúsculas.

name_pt recebe o mesmo valor de name_en de propósito: nome de Pokémon não é
traduzido no Brasil. Quem joga em português compra 'Sableye', não 'Olho-Vivo'.
A coluna existe para o dia em que isso deixar de ser verdade.

name_ja é outra história e vem do detalhe de cada espécie, uma requisição por
espécie. Sem ele, 434 cartas japonesas sem dexId ficam fora de todo masterset,
porque não há como casá-las por nome.
"""

from __future__ import annotations

import asyncio

import httpx

from .species import Especie, nome_de_slug


async def listar_especies(
    base: str = "https://pokeapi.co/api/v2",
    *,
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
    com_japones: bool = True,
    concorrencia: int = 6,
) -> list[Especie]:
    proprio = client is None
    client = client or httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    try:
        r = await client.get(f"{base.rstrip('/')}/pokemon-species", params={"limit": 2000})
        r.raise_for_status()
        dados = r.json()

        basicas = []
        for item in dados.get("results", []):
            slug = item["name"]
            try:
                dex = int(item["url"].rstrip("/").rsplit("/", 1)[-1])
            except ValueError:
                continue
            basicas.append((dex, slug))

        nomes_ja: dict[int, str] = {}
        if com_japones:
            nomes_ja = await _nomes_japoneses(client, base, basicas, concorrencia)
    finally:
        if proprio:
            await client.aclose()

    especies: list[Especie] = []
    for dex, slug in basicas:
        nome = nome_de_slug(slug)
        especies.append(
            Especie(
                dex_number=dex,
                slug=slug,
                name_en=nome,
                name_pt=nome,
                name_ja=nomes_ja.get(dex),
            )
        )
    return especies


async def _nomes_japoneses(
    client: httpx.AsyncClient,
    base: str,
    basicas: list[tuple[int, str]],
    concorrencia: int,
) -> dict[int, str]:
    """Uma requisição por espécie. É o preço de alcançar as cartas japonesas
    que o TCGdex entrega sem dexId."""
    sem = asyncio.Semaphore(concorrencia)

    async def um(dex: int) -> tuple[int, str | None]:
        async with sem:
            try:
                r = await client.get(f"{base.rstrip('/')}/pokemon-species/{dex}")
                r.raise_for_status()
                nomes = r.json().get("names") or []
            except httpx.HTTPError:
                return dex, None
        for n in nomes:
            if (n.get("language") or {}).get("name") == "ja":
                return dex, n.get("name")
        return dex, None

    resultados = await asyncio.gather(*(um(dex) for dex, _ in basicas))
    return {dex: nome for dex, nome in resultados if nome}
