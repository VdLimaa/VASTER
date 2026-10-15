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

from .species import REGIAO_POR_GERACAO, Especie, nome_de_slug


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
        geracoes: dict[int, str] = {}
        if com_japones:
            nomes_ja, geracoes = await _detalhes(client, base, basicas, concorrencia)
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
                generation=geracoes.get(dex),
                region=REGIAO_POR_GERACAO.get(geracoes.get(dex) or ""),
            )
        )
    return especies


async def _detalhes(
    client: httpx.AsyncClient,
    base: str,
    basicas: list[tuple[int, str]],
    concorrencia: int,
) -> tuple[dict[int, str], dict[int, str]]:
    """Uma requisição por espécie, trazendo nome japonês e geração juntos.

    O nome japonês é o que alcança as 434 cartas japonesas que o TCGdex
    entrega sem dexId. A geração é o que permite recortar o masterset por
    região — 'só os de Kanto'. Vêm na mesma resposta, então a segunda sai de
    graça.
    """
    sem = asyncio.Semaphore(concorrencia)

    async def um(dex: int) -> tuple[int, str | None, str | None]:
        async with sem:
            try:
                r = await client.get(f"{base.rstrip('/')}/pokemon-species/{dex}")
                r.raise_for_status()
                corpo = r.json()
            except httpx.HTTPError:
                return dex, None, None
        ja = None
        for n in corpo.get("names") or []:
            if (n.get("language") or {}).get("name") == "ja":
                ja = n.get("name")
                break
        geracao = (corpo.get("generation") or {}).get("name")
        return dex, ja, geracao

    resultados = await asyncio.gather(*(um(dex) for dex, _ in basicas))
    nomes = {dex: ja for dex, ja, _ in resultados if ja}
    geracoes = {dex: g for dex, _, g in resultados if g}
    return nomes, geracoes
