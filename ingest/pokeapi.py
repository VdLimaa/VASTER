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

from .formas import classificar_variedade, rotulo_forma, sprite_url
from .species import REGIAO_POR_GERACAO, Especie, Forma, nome_de_slug


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
        formas: dict[int, tuple[Forma, ...]] = {}
        if com_japones:
            nomes_ja, geracoes, formas = await _detalhes(client, base, basicas, concorrencia)
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
                sprite_url=sprite_url(dex),
                formas=formas.get(dex, ()),
            )
        )
    return especies


async def _detalhes(
    client: httpx.AsyncClient,
    base: str,
    basicas: list[tuple[int, str]],
    concorrencia: int,
) -> tuple[dict[int, str], dict[int, str], dict[int, tuple[Forma, ...]]]:
    """Uma requisição por espécie, trazendo nome japonês, geração e formas.

    O nome japonês é o que alcança as 434 cartas japonesas que o TCGdex
    entrega sem dexId. A geração é o que permite recortar o masterset por
    região — 'só os de Kanto'. As formas (`varieties`) são a Pokédex de megas
    e de formas regionais. Vêm todas na mesma resposta, então as duas últimas
    saem de graça.
    """
    sem = asyncio.Semaphore(concorrencia)

    async def um(dex: int) -> tuple[int, str | None, str | None, tuple[Forma, ...]]:
        async with sem:
            try:
                r = await client.get(f"{base.rstrip('/')}/pokemon-species/{dex}")
                r.raise_for_status()
                corpo = r.json()
            except httpx.HTTPError:
                return dex, None, None, ()
        ja = None
        for n in corpo.get("names") or []:
            if (n.get("language") or {}).get("name") == "ja":
                ja = n.get("name")
                break
        geracao = (corpo.get("generation") or {}).get("name")
        return dex, ja, geracao, _formas(corpo)

    resultados = await asyncio.gather(*(um(dex) for dex, _ in basicas))
    nomes = {dex: ja for dex, ja, _, _ in resultados if ja}
    geracoes = {dex: g for dex, _, g, _ in resultados if g}
    formas = {dex: f for dex, _, _, f in resultados if f}
    return nomes, geracoes, formas


def _formas(corpo: dict) -> tuple[Forma, ...]:
    """As variedades não-padrão da espécie.

    A padrão fica de fora: ela é a própria espécie, e a tela já a oferece como
    'Normal'. O id do sprite sai da URL da variedade — assim a Pokédex ganha
    imagem sem uma requisição a mais por forma.
    """
    saida = []
    for v in corpo.get("varieties") or []:
        if v.get("is_default"):
            continue
        pokemon = v.get("pokemon") or {}
        slug = pokemon.get("name")
        if not slug:
            continue
        try:
            pid = int(str(pokemon.get("url", "")).rstrip("/").rsplit("/", 1)[-1])
        except ValueError:
            continue
        kind, regiao = classificar_variedade(slug)
        saida.append(
            Forma(
                slug=slug,
                kind=kind,
                regiao=regiao,
                name_en=rotulo_forma(nome_de_slug(corpo.get("name", "")), slug, kind, regiao),
                sprite_url=sprite_url(pid),
            )
        )
    return tuple(saida)
