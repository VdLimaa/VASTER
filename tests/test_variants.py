"""Geração de slots e regras por era.

Os valores de variants nestes testes vêm das fixtures capturadas da API, não
de suposição: 'Charizard do Base Set' tem firstEdition=True, holo=True e
normal=False, e a Tag Team tem reverse=False.
"""

import datetime as dt

import pytest

from ingest.variants import (
    IDIOMAS_POR_REGIAO,
    Carta,
    Politica,
    decidir,
    gerar_slots,
    kind_base,
    kinds_da_carta,
)

POLITICAS = [
    Politica(
        id=1,
        kind="reverse_holo",
        max_set_release=dt.date(2002, 5, 23),
        allowed=False,
        reason="Reverse holo só existe a partir de Legendary Collection (2002-05-24).",
        priority=100,
    ),
    Politica(
        id=2,
        kind="reverse_holo",
        rarity_regex=r"(?i)(ultra rare|full art|rainbow|secret)",
        allowed=False,
        reason="Ultra Rara, Full Art e Rainbow não têm reverse holo.",
        priority=90,
    ),
    Politica(
        id=4,
        region="jp",
        kind="reverse_holo",
        allowed=False,
        reason="O card game japonês não imprime reverse holo.",
        priority=110,
    ),
    Politica(
        id=3,
        serie="ex",
        kind="reverse_holo",
        allowed=True,
        annotate=True,
        reason="Na era EX a RF traz o nome da coleção estampado na arte.",
        priority=50,
    ),
]


def carta_de_fixture(fx, **extra) -> Carta:
    return Carta(
        tcgdex_id=fx["id"],
        rarity_en=fx.get("rarity"),
        api_variants=fx.get("variants"),
        api_variants_detailed=fx.get("variants_detailed"),
        **extra,
    )


class TestPolitica:
    def test_veta_reverse_antes_de_legendary_collection(self):
        d = decidir(
            POLITICAS, serie="base", kind="reverse_holo", language="en",
            rarity_en="Rare", set_release=dt.date(1999, 1, 9),
        )
        assert not d.allowed

    def test_libera_reverse_no_dia_de_legendary_collection(self):
        """Legendary Collection saiu em 2002-05-24 e o corte é 05-23.
        Medido na API: lc tem 110/110 cartas com reverse, base1 tem 0/102."""
        d = decidir(
            POLITICAS, serie="lc", kind="reverse_holo", language="en",
            rarity_en="Rare", set_release=dt.date(2002, 5, 24),
        )
        assert d.allowed

    def test_veta_reverse_em_ultra_rara(self):
        d = decidir(
            POLITICAS, serie="sm", kind="reverse_holo", language="en",
            rarity_en="Ultra Rare", set_release=dt.date(2019, 8, 2),
        )
        assert not d.allowed

    def test_set_sem_data_nao_e_vetado_por_regra_de_data(self):
        """Ausência de data não é prova de nada. Vetar por ela esconderia
        slot legítimo de promo sem data no catálogo."""
        d = decidir(
            POLITICAS, serie="xyp", kind="reverse_holo", language="en",
            rarity_en="Promo", set_release=None,
        )
        assert d.allowed

    def test_regra_mais_especifica_ganha_por_prioridade(self):
        d = decidir(
            POLITICAS, serie="ex", kind="reverse_holo", language="en",
            rarity_en="Rare", set_release=dt.date(2003, 9, 18),
        )
        assert d.allowed
        assert d.anotar is not None
        assert "estampado" in d.anotar

    def test_sem_regra_libera(self):
        d = decidir(
            POLITICAS, serie="swsh", kind="regular", language="pt",
            rarity_en="Common", set_release=dt.date(2021, 8, 27),
        )
        assert d.allowed
        assert d.anotar is None


class TestKindBase:
    @pytest.mark.parametrize(
        ("raridade", "esperado"),
        [
            ("Common", "regular"),
            ("Rare", "regular"),
            ("Rare Holo", "regular"),
            ("Ultra Rare", "regular"),
            ("Full Art", "full_art"),
            ("Rainbow Rare", "rainbow"),
            ("Secret Rare", "gold"),
            ("Hyper Rare", "gold"),
            ("Illustration Rare", "alt_art"),
            ("Special Illustration Rare", "alt_art"),
            ("Shiny Rare", "shiny"),
            (None, "regular"),
        ],
    )
    def test_raridade_define_o_slot_base(self, raridade, esperado):
        assert kind_base(raridade) == esperado


class TestKindsDaCarta:
    def test_sableye_comum_tem_regular_e_reverse(self, carta_sableye_swsh7):
        assert kinds_da_carta(carta_de_fixture(carta_sableye_swsh7)) == [
            "regular",
            "reverse_holo",
        ]

    def test_charizard_base_set_e_holo_e_primeira_edicao(self, carta_base_set):
        """normal=False: esta carta nunca existiu em versão não-holo."""
        assert kinds_da_carta(carta_de_fixture(carta_base_set)) == [
            "holo",
            "first_edition",
        ]

    def test_impressao_especial_nao_gera_slot_duplicado(self):
        """Uma Full Art tem variants.normal=True e É a Full Art. Gerar
        'regular' + 'full_art' inventaria uma carta que não existe."""
        carta = Carta(
            tcgdex_id="x-1",
            rarity_en="Full Art",
            api_variants={"normal": True, "holo": True, "reverse": False,
                          "firstEdition": False, "wPromo": False},
        )
        assert kinds_da_carta(carta) == ["full_art"]

    def test_carta_sem_nenhuma_flag_ainda_gera_o_slot_base(self):
        carta = Carta(tcgdex_id="x-2", rarity_en="Common", api_variants={})
        assert kinds_da_carta(carta) == ["regular"]


class TestGerarSlots:
    def test_dois_idiomas_por_kind(self, carta_sableye_swsh7):
        carta = carta_de_fixture(
            carta_sableye_swsh7, serie="swsh", set_release=dt.date(2021, 8, 27),
            set_pt_release="yes",
        )
        slots = gerar_slots(carta, POLITICAS)
        assert {(s.kind, s.language) for s in slots} == {
            ("regular", "en"), ("reverse_holo", "en"),
            ("regular", "pt"), ("reverse_holo", "pt"),
        }

    def test_set_sem_lancamento_br_nao_gera_slot_pt(self, carta_sableye_swsh7):
        carta = carta_de_fixture(
            carta_sableye_swsh7, serie="swsh", set_release=dt.date(2021, 8, 27),
            set_pt_release="no",
        )
        assert all(s.language == "en" for s in gerar_slots(carta, POLITICAS))

    def test_veto_de_era_registra_o_motivo(self, carta_base_set):
        """A fixture do Base Set não tem reverse, então o veto é forçado aqui
        para provar que o registro acontece."""
        carta = Carta(
            tcgdex_id="base1-4",
            rarity_en="Rare",
            api_variants={"normal": False, "holo": True, "reverse": True,
                          "firstEdition": True, "wPromo": False},
            serie="base",
            set_release=dt.date(1999, 1, 9),
            set_pt_release="yes",
        )
        slots = gerar_slots(carta, POLITICAS)
        rf = [s for s in slots if s.kind == "reverse_holo"]
        # Não some: vira 'unlikely' com a razão, porque a API afirmava que
        # existia e a discordância é exatamente o que alguém precisa ver.
        assert len(rf) == 2  # en e pt
        assert all(s.exists_state == "unlikely" for s in rf)
        assert all("Legendary Collection" in (s.notes or "") for s in rf)
        assert all(s.source_url is None for s in rf)
        assert len(carta.vetos) == 2
        assert "Legendary Collection" in carta.vetos[0]

    def test_auto_confirma_so_o_slot_principal_em_pt(self, carta_sableye_swsh7):
        """Ter o scan em PT prova que a carta saiu em português. Não prova
        nada sobre a reverse holo em português."""
        carta = carta_de_fixture(
            carta_sableye_swsh7, serie="swsh", set_release=dt.date(2021, 8, 27),
            set_pt_release="yes", has_pt=True,
            image_url_pt="https://assets.tcgdex.net/pt/swsh/swsh7/67/high.png",
        )
        slots = gerar_slots(carta, POLITICAS)
        confirmados = [s for s in slots if s.exists_state == "confirmed"]
        assert len(confirmados) == 1
        assert (confirmados[0].kind, confirmados[0].language) == ("regular", "pt")
        assert confirmados[0].source_url.endswith("/pt/swsh/swsh7/67/high.png")

    def test_auto_confirm_desligado_deixa_tudo_unknown(self, carta_sableye_swsh7):
        carta = carta_de_fixture(
            carta_sableye_swsh7, serie="swsh", set_release=dt.date(2021, 8, 27),
            set_pt_release="yes", has_pt=True,
        )
        slots = gerar_slots(carta, POLITICAS, auto_confirmar=False)
        assert all(s.exists_state == "unknown" for s in slots)
        assert all(s.source_url is None for s in slots)

    def test_sem_scan_pt_nao_confirma(self, carta_era_ex):
        carta = carta_de_fixture(
            carta_era_ex, serie="ex", set_release=dt.date(2003, 9, 18),
            set_pt_release="yes", has_pt=False,
        )
        assert all(s.exists_state == "unknown" for s in gerar_slots(carta, POLITICAS))

    def test_variant_id_do_tcgdex_chega_ao_slot(self, carta_sableye_swsh7):
        """api_variant_id é o que vai ligar o slot ao preço de
        variants_detailed na F3."""
        carta = carta_de_fixture(
            carta_sableye_swsh7, serie="swsh", set_release=dt.date(2021, 8, 27),
        )
        slots = {s.kind: s for s in gerar_slots(carta, POLITICAS, idiomas=("en",))}
        assert slots["regular"].api_variant_id
        assert slots["reverse_holo"].api_variant_id
        assert slots["regular"].api_variant_id != slots["reverse_holo"].api_variant_id

    def test_nenhum_slot_repetido(self, carta_base_set):
        carta = carta_de_fixture(
            carta_base_set, serie="base", set_release=dt.date(1999, 1, 9),
            set_pt_release="yes",
        )
        slots = gerar_slots(carta, POLITICAS)
        chaves = [(s.kind, s.language) for s in slots]
        assert len(chaves) == len(set(chaves))


class TestJapones:
    """O catálogo japonês é outro produto, não tradução. Uma carta japonesa é
    outra carta, em outra coleção, e o único idioma dela é o japonês."""

    def carta_jp(self, **extra) -> Carta:
        base = {
            "tcgdex_id": "S6K-028",
            "rarity_en": "Common",
            "api_variants": {"normal": True, "holo": False, "reverse": False,
                             "firstEdition": False, "wPromo": False},
            "region": "jp",
            "serie": "S",
            "set_release": dt.date(2021, 4, 23),
        }
        return Carta(**(base | extra))

    def test_regiao_define_os_idiomas_possiveis(self):
        assert IDIOMAS_POR_REGIAO["jp"] == ("ja",)
        assert IDIOMAS_POR_REGIAO["west"] == ("en", "pt")

    def test_coleccao_japonesa_nao_gera_slot_em_portugues(self):
        slots = gerar_slots(self.carta_jp(), POLITICAS, idiomas=("en", "pt", "ja"))
        assert {s.language for s in slots} == {"ja"}

    def test_pedir_so_portugues_numa_carta_japonesa_nao_gera_nada(self):
        assert gerar_slots(self.carta_jp(), POLITICAS, idiomas=("pt",)) == []

    def test_coleccao_do_oeste_nao_gera_slot_em_japones(self, carta_sableye_swsh7):
        carta = carta_de_fixture(
            carta_sableye_swsh7, serie="swsh", set_release=dt.date(2021, 8, 27),
            set_pt_release="yes", region="west",
        )
        slots = gerar_slots(carta, POLITICAS, idiomas=("en", "pt", "ja"))
        assert "ja" not in {s.language for s in slots}

    def test_japones_nao_tem_reverse_holo(self):
        """Medido: 0 de 54 cartas amostradas em S6K, SM7b e PMCG1 têm reverse.
        A política veta mesmo quando a API diz o contrário."""
        carta = self.carta_jp(
            api_variants={"normal": True, "holo": False, "reverse": True,
                          "firstEdition": False, "wPromo": False}
        )
        slots = gerar_slots(carta, POLITICAS)
        rf = [s for s in slots if s.kind == "reverse_holo"]
        assert len(rf) == 1 and rf[0].exists_state == "unlikely"
        assert any("japonês" in v for v in carta.vetos)

    def test_regra_do_oeste_nao_vaza_para_o_japao(self):
        """A série 'e' japonesa e a era 'ex' do oeste são coisas diferentes.
        Uma regra sem região continua valendo nos dois, e é por isso que a
        regra da era EX pede serie='ex' explicitamente."""
        d = decidir(
            POLITICAS, serie="ex", kind="reverse_holo", language="ja",
            rarity_en="Rare", set_release=dt.date(2003, 9, 18), region="jp",
        )
        assert not d.allowed
        assert "japonês" in d.reason

    def test_negacao_da_politica_nao_vira_confirmacao(self):
        """Slot negado nasce 'unlikely' mesmo com auto-confirmação ligada."""
        carta = self.carta_jp(
            has_ja=True,
            image_url_ja="https://x/1.png",
            api_variants={"normal": True, "holo": False, "reverse": True,
                          "firstEdition": False, "wPromo": False},
        )
        estados = {s.kind: s.exists_state for s in gerar_slots(carta, POLITICAS)}
        assert estados["regular"] == "confirmed"
        assert estados["reverse_holo"] == "unlikely"

    def test_carta_japonesa_nasce_confirmada_com_o_scan(self):
        """Estar no catálogo japonês já é a evidência: a carta é japonesa."""
        carta = self.carta_jp(
            has_ja=True,
            image_url_ja="https://assets.tcgdex.net/ja/s/S6K/028/high.png",
        )
        slots = gerar_slots(carta, POLITICAS)
        assert [(s.kind, s.language, s.exists_state) for s in slots] == [
            ("regular", "ja", "confirmed")
        ]
        assert slots[0].source_url.endswith("/ja/s/S6K/028/high.png")

    def test_sem_scan_a_prova_e_a_propria_carta_na_api(self):
        """70% do catálogo japonês não tem scan. O registro da carta ainda
        prova que ela existe, então a URL da API serve de fonte."""
        carta = self.carta_jp(has_ja=True, image_url_ja=None)
        slot = gerar_slots(carta, POLITICAS)[0]
        assert slot.exists_state == "confirmed"
        assert slot.source_url == "https://api.tcgdex.net/v2/ja/cards/S6K-028"


class TestSlotObrigado:
    """A flag 'reverse' do TCGdex está ausente em eras inteiras: Black & White,
    XY e Sun & Moon dão praticamente zero, enquanto Diamond & Pearl, Platinum,
    HeartGold, Sword & Shield e Scarlet & Violet passam de 90%. Num masterset,
    slot faltando é pior que slot sobrando — o colecionador nunca descobre que
    a carta existe."""

    POLITICAS_OBRIGA = [
        Politica(
            id=5, kind="reverse_holo", set_regex=r"(?i)(^|-)(bwp|xyp|smp)$",
            allowed=False, reason="Coleção de promos não tem reverse holo.",
            priority=200,
        ),
        Politica(
            id=2, kind="reverse_holo", rarity_regex=r"(?i)(ultra rare|full art)",
            allowed=False, reason="Raridade sem RF.", priority=90,
        ),
        Politica(
            id=6, serie="bw", kind="reverse_holo",
            rarity_regex=r"(?i)^(common|uncommon|rare|rare holo)$",
            allowed=True, obriga=True, annotate=True,
            reason="Slot inferido pela era.", priority=70,
        ),
    ]

    def carta(self, **extra) -> Carta:
        base = {
            "tcgdex_id": "bw1-1",
            "rarity_en": "Common",
            # A API diz que NÃO tem reverse. É justamente o dado que falta.
            "api_variants": {"normal": True, "holo": False, "reverse": False,
                             "firstEdition": False, "wPromo": False},
            "serie": "bw",
            "set_tcgdex_id": "bw1",
            "set_release": dt.date(2011, 4, 25),
        }
        return Carta(**(base | extra))

    def test_cria_o_slot_que_a_api_nao_lista(self):
        slots = gerar_slots(self.carta(), self.POLITICAS_OBRIGA, idiomas=("en",))
        rf = [s for s in slots if s.kind == "reverse_holo"]
        assert len(rf) == 1
        assert rf[0].inferido
        assert rf[0].exists_state == "unknown"
        assert "inferido" in (rf[0].notes or "").lower()

    def test_slot_inferido_nunca_nasce_confirmado(self):
        """Inferência é hipótese, não prova. Nem com scan em PT."""
        carta = self.carta(set_pt_release="yes", has_pt=True,
                           image_url_pt="https://x/pt.png")
        slots = gerar_slots(carta, self.POLITICAS_OBRIGA, idiomas=("pt",))
        por_kind = {s.kind: s for s in slots}
        assert por_kind["regular"].exists_state == "confirmed"
        assert por_kind["reverse_holo"].exists_state == "unknown"
        assert por_kind["reverse_holo"].inferido

    def test_promo_nao_ganha_slot_inferido(self):
        """A negação de prioridade 200 vence a regra que obriga."""
        carta = self.carta(tcgdex_id="bwp-BW01", set_tcgdex_id="bwp")
        slots = gerar_slots(carta, self.POLITICAS_OBRIGA, idiomas=("en",))
        assert not any(s.kind == "reverse_holo" for s in slots)

    def test_raridade_sem_rf_nao_ganha_slot_inferido(self):
        carta = self.carta(rarity_en="Ultra Rare")
        slots = gerar_slots(carta, self.POLITICAS_OBRIGA, idiomas=("en",))
        assert not any(s.kind == "reverse_holo" for s in slots)

    def test_era_de_dado_bom_nao_infere_nada(self):
        """Em Sword & Shield a API acerta; a regra não se aplica e o slot que
        existe vem da API, não da inferência."""
        carta = self.carta(
            tcgdex_id="swsh7-67", serie="swsh", set_tcgdex_id="swsh7",
            set_release=dt.date(2021, 8, 27),
            api_variants={"normal": True, "holo": False, "reverse": True,
                          "firstEdition": False, "wPromo": False},
        )
        slots = gerar_slots(carta, self.POLITICAS_OBRIGA, idiomas=("en",))
        rf = [s for s in slots if s.kind == "reverse_holo"]
        assert len(rf) == 1
        assert not rf[0].inferido

    def test_nao_duplica_quando_a_api_ja_lista(self):
        carta = self.carta(
            api_variants={"normal": True, "holo": False, "reverse": True,
                          "firstEdition": False, "wPromo": False}
        )
        slots = gerar_slots(carta, self.POLITICAS_OBRIGA, idiomas=("en", "pt"))
        chaves = [(s.kind, s.language) for s in slots]
        assert len(chaves) == len(set(chaves))
        assert not any(s.inferido for s in slots)
