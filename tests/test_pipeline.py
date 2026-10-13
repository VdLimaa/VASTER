"""Funções puras do pipeline. O que toca banco é verificado pelo comando
'gate', que roda contra Postgres de verdade."""

import datetime as dt

from ingest.pipeline import SERIES_DIGITAIS, _data, _num_sort, _set_de_carta

SET_IDS = sorted(
    ["sv03", "sv03.5", "swsh7", "swshp", "base1", "sm11", "A3", "me02", "me02.5"],
    key=len,
    reverse=True,
)


class TestSetDeCarta:
    def test_caso_simples(self):
        assert _set_de_carta("swsh7-67", SET_IDS) == "swsh7"

    def test_prefixo_mais_longo_ganha(self):
        """'sv03.5-1' não pertence a 'sv03'. Casar pelo prefixo mais curto
        jogaria as cartas de Paldean Fates dentro de Obsidian Flames."""
        assert _set_de_carta("sv03.5-1", SET_IDS) == "sv03.5"
        assert _set_de_carta("sv03-1", SET_IDS) == "sv03"
        assert _set_de_carta("me02.5-261", SET_IDS) == "me02.5"

    def test_local_id_com_hifen(self):
        assert _set_de_carta("swshp-SWSH001", SET_IDS) == "swshp"

    def test_set_desconhecido(self):
        assert _set_de_carta("xyz9-1", SET_IDS) is None


class TestNumSort:
    def test_numero_puro(self):
        assert _num_sort("67") == 67

    def test_numero_com_prefixo(self):
        assert _num_sort("SWSH001") == 1
        assert _num_sort("XY92") == 92
        assert _num_sort("TG05") == 5

    def test_sem_digito(self):
        assert _num_sort("") is None
        assert _num_sort("Promo") is None


class TestData:
    def test_formatos_aceitos(self):
        assert _data("2021-08-27") == dt.date(2021, 8, 27)
        assert _data("2021-08") == dt.date(2021, 8, 1)
        assert _data("2021") == dt.date(2021, 1, 1)

    def test_vazio_ou_invalido(self):
        assert _data(None) is None
        assert _data("") is None
        assert _data("ontem") is None


class TestSeriesDigitais:
    def test_pocket_e_digital(self):
        """A série tcgp são 2.480 cartas de app. Masterset físico não as
        inclui, mas o catálogo guarda para não mentir sobre o que a API tem."""
        assert "tcgp" in SERIES_DIGITAIS
        assert "swsh" not in SERIES_DIGITAIS
