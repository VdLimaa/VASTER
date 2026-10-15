"""As regras de forma, contra nomes reais do catálogo.

Os casos saíram de uma consulta no banco cheio, não de invenção: 'Mega
Catcher' é a carta de treinador que o começo 'Mega ' pegaria por engano, e
'Kyogre Primitivo' é como o português escreve Primal.
"""

from __future__ import annotations

import pytest

from ingest.formas import classificar_variedade, forma_da_carta, rotulo_forma


@pytest.mark.parametrize(
    ("kw", "esperado"),
    [
        ({"name_en": "M Charizard EX", "categoria": "Pokemon"}, "mega"),
        ({"name_en": "M Beedrill-EX", "categoria": "Pokemon"}, "mega"),
        ({"name_en": "Mega Charizard X ex", "categoria": "Pokemon"}, "mega"),
        ({"name_en": None, "name_ja": "メガリザードンex", "categoria": "Pokemon"}, "mega"),
        # Carta de treinador que começa com 'Mega ' e não é forma nenhuma.
        ({"name_en": "Mega Catcher", "categoria": "Trainer"}, "normal"),
        # Mr. Mime começa com M e não é mega: a regra pede espaço ou hífen.
        ({"name_en": "Mr. Mime", "categoria": "Pokemon"}, "normal"),
        ({"name_en": "Alolan Exeggutor", "categoria": "Pokemon"}, "alola"),
        ({"name_en": None, "name_pt": "Exeggutor de Alola", "categoria": "Pokemon"}, "alola"),
        ({"name_en": None, "name_ja": "アローラ ゴローン", "categoria": "Pokemon"}, "alola"),
        ({"name_en": "Galarian Cursola V", "categoria": "Pokemon"}, "galar"),
        ({"name_en": "Hisuian Voltorb", "categoria": "Pokemon"}, "hisui"),
        ({"name_en": "Paldean Tauros", "categoria": "Pokemon"}, "paldea"),
        ({"name_en": "Primal Kyogre EX", "categoria": "Pokemon"}, "primal"),
        ({"name_en": None, "name_pt": "Kyogre Primitivo EX", "categoria": "Pokemon"}, "primal"),
        ({"name_en": "Charizard", "categoria": "Pokemon"}, "normal"),
        # O estágio é a segunda testemunha, para a coleção que nomear diferente.
        ({"name_en": "Alguma Coisa", "categoria": "Pokemon", "estagio": "MEGA"}, "mega"),
    ],
)
def test_forma_da_carta(kw: dict, esperado: str) -> None:
    assert forma_da_carta(**kw) == esperado


@pytest.mark.parametrize(
    ("slug", "esperado"),
    [
        ("charizard-mega-x", ("mega", None)),
        ("kyogre-primal", ("primal", None)),
        ("raichu-alola", ("regional", "alola")),
        ("tauros-paldea-combat", ("regional", "paldea")),
        ("charizard-gmax", ("gigantamax", None)),
        ("rotom-heat", ("outra", None)),
        # Pikachu de boné de Alola é forma de jogo, não forma regional.
        ("pikachu-alola-cap", ("outra", None)),
    ],
)
def test_classificar_variedade(slug: str, esperado: tuple[str, str | None]) -> None:
    assert classificar_variedade(slug) == esperado


def test_rotulo_nao_usa_o_slug() -> None:
    assert rotulo_forma("Charizard", "charizard-mega-x", "mega", None) == "Mega Charizard X"
    assert rotulo_forma("Raichu", "raichu-alola", "regional", "alola") == "Raichu de Alola"
    assert rotulo_forma("Charizard", "charizard-gmax", "gigantamax", None) == "Gigantamax Charizard"
