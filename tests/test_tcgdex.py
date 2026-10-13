"""Cliente HTTP. Sem rede: httpx.MockTransport responde no lugar da API."""

import httpx
import pytest

from ingest.tcgdex import TCGdex, image_url


def cliente(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestImageUrl:
    def test_sufixo_obrigatorio(self):
        """A URL crua do TCGdex devolve HTML, não imagem. Medido:
        .../swsh7/67 responde text/html com 295 bytes."""
        assert (
            image_url("https://assets.tcgdex.net/en/swsh/swsh7/67")
            == "https://assets.tcgdex.net/en/swsh/swsh7/67/high.png"
        )

    def test_qualidade_e_formato_configuraveis(self):
        assert image_url("http://x/1", quality="low", fmt="webp") == "http://x/1/low.webp"

    def test_none_passa_direto(self):
        assert image_url(None) is None


class TestGet:
    async def test_404_devolve_none_e_nao_levanta(self):
        """404 em pt não é falha: é a resposta 'não existe em português',
        que é exatamente o dado que o projeto precisa registrar."""
        chamadas = []

        def handler(request):
            chamadas.append(request.url.path)
            return httpx.Response(404)

        async with TCGdex(client=cliente(handler)) as api:
            assert await api.card("pt", "base1-4") is None
        assert len(chamadas) == 1  # não tenta de novo

    async def test_repete_em_429_e_devolve_o_resultado(self):
        tentativas = []

        def handler(request):
            tentativas.append(1)
            if len(tentativas) < 3:
                return httpx.Response(429)
            return httpx.Response(200, json={"id": "swsh7-67"})

        api = TCGdex(client=cliente(handler), max_retries=4)
        api._sem._value = 1
        # Backoff sem espera real.
        import ingest.tcgdex as mod

        original = mod.asyncio.sleep

        async def sem_espera(_s):
            return None

        mod.asyncio.sleep = sem_espera
        try:
            assert await api.card("en", "swsh7-67") == {"id": "swsh7-67"}
        finally:
            mod.asyncio.sleep = original
        assert len(tentativas) == 3

    async def test_desiste_depois_do_limite(self):
        def handler(request):
            return httpx.Response(503)

        api = TCGdex(client=cliente(handler), max_retries=2)
        import ingest.tcgdex as mod

        original = mod.asyncio.sleep

        async def sem_espera(_s):
            return None

        mod.asyncio.sleep = sem_espera
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await api.card("en", "x-1")
        finally:
            mod.asyncio.sleep = original

    async def test_erro_de_cliente_nao_e_repetido(self):
        """400 é erro de uso, não instabilidade. Repetir só gasta a API."""
        tentativas = []

        def handler(request):
            tentativas.append(1)
            return httpx.Response(400)

        async with TCGdex(client=cliente(handler)) as api:
            with pytest.raises(httpx.HTTPStatusError):
                await api.card("en", "x-1")
        assert len(tentativas) == 1

    async def test_filtro_por_dex_id_vai_na_query(self):
        vistos = []

        def handler(request):
            vistos.append(str(request.url))
            return httpx.Response(200, json=[])

        async with TCGdex(client=cliente(handler)) as api:
            await api.cards_by_dex("en", 302)
        assert "dexId=302" in vistos[0]

    async def test_lista_vazia_quando_a_api_devolve_404(self):
        async with TCGdex(client=cliente(lambda r: httpx.Response(404))) as api:
            assert await api.sets("pt") == []
            assert await api.cards_by_dex("pt", 999) == []
