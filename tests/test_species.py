"""A resolução de espécie é o que o gate da F0 cobra. Estes testes travam os
casos que quebram implementações ingênuas."""

from ingest.species import (
    Especie,
    IndiceEspecies,
    eh_pokemon,
    especies_da_carta,
    nome_de_slug,
    normalizar,
)

ESPECIES = [
    Especie(29, "nidoran-f", "Nidoran♀", "Nidoran♀"),
    Especie(122, "mr-mime", "Mr. Mime", "Mr. Mime"),
    Especie(150, "mewtwo", "Mewtwo", "Mewtwo"),
    Especie(151, "mew", "Mew", "Mew"),
    Especie(248, "tyranitar", "Tyranitar", "Tyranitar"),
    Especie(250, "ho-oh", "Ho-Oh", "Ho-Oh"),
    Especie(302, "sableye", "Sableye", "Sableye"),
    Especie(439, "mime-jr", "Mime Jr.", "Mime Jr."),
    Especie(474, "porygon-z", "Porygon-Z", "Porygon-Z"),
    Especie(772, "type-null", "Type: Null", "Type: Null"),
    Especie(785, "tapu-koko", "Tapu Koko", "Tapu Koko"),
    Especie(35, "clefairy", "Clefairy", "Clefairy"),
]


def indice() -> IndiceEspecies:
    return IndiceEspecies(ESPECIES)


class TestNormalizar:
    def test_pontuacao_e_acento_nao_separam_grafias(self):
        assert normalizar("Mr. Mime") == normalizar("mr-mime") == ["mr", "mime"]
        assert normalizar("Type: Null") == normalizar("type-null") == ["type", "null"]
        assert normalizar("Flabébé") == ["flabebe"]
        assert normalizar("Farfetch'd") == ["farfetchd"]

    def test_simbolo_de_genero_vira_token(self):
        assert normalizar("Nidoran♀") == normalizar("nidoran-f") == ["nidoran", "f"]


class TestCasamento:
    def test_mew_nao_casa_dentro_de_mewtwo(self):
        """O caso que mata quem compara por substring."""
        assert [e.slug for e in indice().casar("Mewtwo")] == ["mewtwo"]
        assert [e.slug for e in indice().casar("Mew")] == ["mew"]

    def test_tag_team_devolve_as_duas_especies(self):
        achados = indice().casar("Mega Sableye & Tyranitar GX")
        assert [e.slug for e in achados] == ["sableye", "tyranitar"]

    def test_prefixo_de_forma_nao_atrapalha(self):
        for nome in ("Dark Sableye", "Sableye V", "Sableye ex", "M Sableye EX"):
            assert [e.slug for e in indice().casar(nome)] == ["sableye"]

    def test_nome_de_treinador_nao_vira_especie_nova(self):
        assert [e.slug for e in indice().casar("Team Rocket's Mewtwo")] == ["mewtwo"]

    def test_especie_de_dois_tokens(self):
        assert [e.slug for e in indice().casar("Tapu Koko")] == ["tapu-koko"]

    def test_mime_jr_nao_casa_mr_mime(self):
        assert [e.slug for e in indice().casar("Mime Jr.")] == ["mime-jr"]
        assert [e.slug for e in indice().casar("Mr. Mime")] == ["mr-mime"]

    def test_sem_especie_devolve_vazio(self):
        assert indice().casar("Professor's Research") == []

    def test_nao_repete_especie_citada_duas_vezes(self):
        assert [e.slug for e in indice().casar("Sableye & Sableye")] == ["sableye"]


class TestCategoria:
    def test_categoria_traduzida_conta_como_pokemon(self):
        """Em pt a API devolve 'Pokémon' com acento. Comparar por igualdade
        com 'Pokemon' deixaria toda carta PT de fora."""
        assert eh_pokemon("Pokemon")
        assert eh_pokemon("Pokémon")
        assert not eh_pokemon("Trainer")
        assert not eh_pokemon("Energy")
        assert not eh_pokemon(None)


class TestEspeciesDaCarta:
    def test_dex_id_tem_prioridade(self, carta_tag_team):
        achados, resolvedor = especies_da_carta(carta_tag_team, indice())
        assert resolvedor == "dex_id"
        assert sorted(e.slug for e in achados) == ["sableye", "tyranitar"]

    def test_carta_pt_resolve_apesar_da_categoria_traduzida(self, carta_sableye_swsh7_pt):
        achados, _ = especies_da_carta(carta_sableye_swsh7_pt, indice())
        assert [e.slug for e in achados] == ["sableye"]

    def test_trainer_com_nome_de_pokemon_nao_vira_carta_da_especie(self):
        """'Clefairy Doll' é Item do Base Set. Sem o corte por categoria ela
        entraria no masterset de Clefairy."""
        carta = {"name": "Clefairy Doll", "category": "Trainer", "dexId": None}
        achados, _ = especies_da_carta(carta, indice())
        assert achados == []

    def test_fallback_por_nome_quando_dex_id_falta(self):
        carta = {"name": "Sableye", "category": "Pokemon", "dexId": None}
        achados, resolvedor = especies_da_carta(carta, indice())
        assert resolvedor == "name_match"
        assert [e.slug for e in achados] == ["sableye"]


class TestNomeDeSlug:
    def test_irregulares(self):
        assert nome_de_slug("mr-mime") == "Mr. Mime"
        assert nome_de_slug("ho-oh") == "Ho-Oh"
        assert nome_de_slug("type-null") == "Type: Null"
        assert nome_de_slug("nidoran-f") == "Nidoran♀"

    def test_regular(self):
        assert nome_de_slug("sableye") == "Sableye"
        assert nome_de_slug("great-tusk") == "Great Tusk"
