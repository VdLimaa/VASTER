"""Cliente do TCGdex.

O que a API entrega de fato, medido em 2026-10-13 e registrado em
docs/achados-tcgdex.md:

* /{lang}/sets                 resumo dos sets (sem serie, sem releaseDate)
* /{lang}/sets/{id}            set completo + lista de cartas (sem variants)
* /{lang}/cards/{id}           carta completa: variants, variants_detailed,
                               rarity, category, dexId, illustrator
* /{lang}/cards                todas as cartas em resumo (1 request, ~2,4 MB em en)
* /{lang}/cards?dexId=N        cartas de uma espécie, Tag Team incluída
* /{lang}/series e /series/{id} séries com releaseDate e seus sets

A lista de cartas dentro de um set NÃO traz variants, então gerar slot exige
um GET por carta. É por isso que 'cards' e 'details' são comandos separados:
o primeiro é barato e o segundo é retomável.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

# Erros que valem nova tentativa. 404 não entra: em pt significa "não existe
# em português", que é informação, não falha.
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


class TCGdex:
    def __init__(
        self,
        base: str = "https://api.tcgdex.net/v2",
        *,
        concurrency: int = 6,
        timeout: float = 30.0,
        max_retries: int = 4,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base = base.rstrip("/")
        self.max_retries = max_retries
        self._sem = asyncio.Semaphore(concurrency)
        self._own_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "vaster-masterset-br/0.1 (catalog ingest; "
                    "+https://github.com/VdLimaa/VASTER)"
                )
            },
            limits=httpx.Limits(max_connections=concurrency * 2),
        )

    async def __aenter__(self) -> TCGdex:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._own_client:
            await self._client.aclose()

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any | None:
        """Devolve o JSON, ou None em 404. Faz backoff em 429 e 5xx."""
        url = f"{self.base}/{path.lstrip('/')}"
        atraso = 1.0
        ultimo: Exception | None = None
        for tentativa in range(self.max_retries):
            async with self._sem:
                try:
                    r = await self._client.get(url, params=params)
                except (httpx.TransportError, httpx.HTTPError) as exc:
                    ultimo = exc
                else:
                    if r.status_code == 404:
                        return None
                    if r.status_code not in RETRY_STATUS:
                        r.raise_for_status()
                        return r.json()
                    ultimo = httpx.HTTPStatusError(
                        f"{r.status_code} em {url}", request=r.request, response=r
                    )
            if tentativa < self.max_retries - 1:
                await asyncio.sleep(atraso)
                atraso *= 2
        assert ultimo is not None
        raise ultimo

    # --- catálogo -----------------------------------------------------------

    async def sets(self, lang: str) -> list[dict]:
        return await self._get(f"{lang}/sets") or []

    async def set_detail(self, lang: str, set_id: str) -> dict | None:
        return await self._get(f"{lang}/sets/{set_id}")

    async def series(self, lang: str) -> list[dict]:
        return await self._get(f"{lang}/series") or []

    async def serie_detail(self, lang: str, serie_id: str) -> dict | None:
        return await self._get(f"{lang}/series/{serie_id}")

    async def card(self, lang: str, card_id: str) -> dict | None:
        return await self._get(f"{lang}/cards/{card_id}")

    async def all_cards(self, lang: str) -> list[dict]:
        """Resumo de todas as cartas do idioma em uma requisição.
        É assim que se mede a cobertura PT sem varrer set por set."""
        return await self._get(f"{lang}/cards") or []

    async def cards_by_dex(self, lang: str, dex_number: int) -> list[dict]:
        """Cartas de uma espécie. Pega 'Mega Sableye & Tyranitar GX' em
        dexId=302 e em dexId=248, que é exatamente o vínculo N:N."""
        return await self._get(f"{lang}/cards", params={"dexId": dex_number}) or []


def image_url(base: str | None, *, quality: str = "high", fmt: str = "png") -> str | None:
    """A URL de imagem do TCGdex vem sem extensão e precisa de sufixo:
    .../swsh7/67 devolve HTML; .../swsh7/67/high.png devolve o PNG."""
    if not base:
        return None
    return f"{base.rstrip('/')}/{quality}.{fmt}"
