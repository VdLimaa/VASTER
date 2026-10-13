import json
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def carregar(nome: str):
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


@pytest.fixture
def carta_sableye_swsh7():
    """Sableye comum de Céus em Evolução: normal + reverse, com scan PT."""
    return carregar("card-en-swsh7-67.json")


@pytest.fixture
def carta_sableye_swsh7_pt():
    return carregar("card-pt-swsh7-67.json")


@pytest.fixture
def carta_tag_team():
    """Mega Sableye & Tyranitar GX: dexId com duas espécies."""
    return carregar("card-en-sm11-126.json")


@pytest.fixture
def carta_base_set():
    """Charizard do Base Set: holo + 1st edition, sem reverse."""
    return carregar("card-en-base1-4.json")


@pytest.fixture
def carta_era_ex():
    return carregar("card-en-ex2-10.json")


@pytest.fixture
def cartas_dex302():
    """Retorno real de /en/cards?dexId=302."""
    return carregar("cards-dex302.json")
