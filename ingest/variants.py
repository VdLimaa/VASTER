"""Geração de slots de variante.

Princípio: um slot é uma compra. Se duas linhas descrevem a mesma carta
física, o masterset mentiu — e o gate da F0 exige "sem duplicata".

Por isso os slots saem SÓ do objeto variants do TCGdex, que diz quais
impressões daquela carta existem. A raridade não cria slot: ela renomeia o
slot base. Uma Full Art tem variants.normal = true e é a própria Full Art,
então gerar 'regular' + 'full_art' inventaria uma carta que não existe.

Sobre a tabela de política: ela nega (allowed=false) ou anota
(annotate=true). Negar é o caso da reverse holo antes de Legendary
Collection; anotar é o caso da RF da era EX, que traz o nome da coleção
estampado e precisa de conferência visual antes de virar 'confirmed'.

Negar NÃO descarta o slot: cria com exists_state='unlikely' e a razão em
notes. O motivo é que kinds_da_carta só produz variante que a API afirma
existir, então toda negação é uma DISCORDÂNCIA entre a API e a regra — e
sumir com ela em silêncio esconde justamente o caso que alguém precisa
olhar. 'unlikely' é o estado que o documento reserva para evidência fraca,
e é o único que não exige source_url. No catálogo ocidental inteiro isso dá
22 slots: 18 de reverse holo em set anterior a 2002 e 4 em raridade que não
tem RF.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

# Raridade -> tipo do slot base. Primeiro casamento ganha, então a ordem
# importa: 'Rainbow Rare' antes de 'Rare', 'Special Illustration' antes de
# 'Illustration'.
# Conferido contra as 42 raridades que /en/rarities lista. O TCGdex NÃO usa a
# palavra "rainbow": a rainbow rare se chama "Hyper rare" lá, e "Secret Rare"
# é a dourada. Mapear hyper para gold rotulava 82 cartas rainbow como gold.
#
# Ficam de fora, caindo em 'regular' de propósito: Rare Holo LV.X, Rare PRIME,
# LEGEND, ACE SPEC Rare, Radiant Rare, Amazing Rare, Pikachu Rare, Black White
# Rare, Futuristic Rare e Classic Collection. São tipos de carta, não
# impressões alternativas da mesma carta — o slot é a impressão base dela, e a
# raridade aparece em coluna própria no masterset. 'Ultra Rare' também fica:
# cobre GX, V e EX, que nem sempre são full art.
RARIDADE_PARA_KIND: tuple[tuple[str, str], ...] = (
    (r"hyper\s*rare|rainbow", "rainbow"),
    (r"full\s*art", "full_art"),
    (r"(secret|gold)", "gold"),
    (r"illustration\s*rare", "alt_art"),
    (r"shiny|shining", "shiny"),
)

# Flag do TCGdex -> tipo do slot. A ordem define qual slot é o principal.
FLAG_PARA_KIND: tuple[tuple[str, str], ...] = (
    ("normal", "regular"),
    ("holo", "holo"),
    ("reverse", "reverse_holo"),
    ("firstEdition", "first_edition"),
    ("wPromo", "promo"),
)

# Quais idiomas uma coleção daquela região chega a imprimir. Uma carta
# japonesa não é o slot 'ja' de uma carta inglesa: é outra carta, em outra
# coleção, e o único idioma possível dela é o japonês.
IDIOMAS_POR_REGIAO: dict[str, tuple[str, ...]] = {
    "west": ("en", "pt"),
    "jp": ("ja",),
}

# Onde o scan daquele idioma mora em card, para a promoção em lote.
SCAN_POR_IDIOMA = {"pt": "image_url_pt", "ja": "image_url_ja"}

KIND_PARA_FLAG = {
    "regular": "normal",
    "holo": "holo",
    "reverse_holo": "reverse",
    "first_edition": "firstEdition",
    "promo": "wPromo",
}


@dataclass(frozen=True)
class Politica:
    id: int
    kind: str
    allowed: bool
    reason: str
    priority: int
    serie: str | None = None
    region: str | None = None
    set_regex: str | None = None
    obriga: bool = False
    language: str | None = None
    rarity_regex: str | None = None
    min_set_release: dt.date | None = None
    max_set_release: dt.date | None = None
    annotate: bool = False

    def casa(
        self,
        *,
        serie: str | None,
        kind: str,
        language: str,
        rarity_en: str | None,
        set_release: dt.date | None,
        region: str = "west",
        set_id: str | None = None,
    ) -> bool:
        if self.kind != kind:
            return False
        # Regra por data não se aplica a set sem data: ausência de data não é
        # prova de nada, e vetar por ela esconderia slot legítimo.
        return all(
            (
                self.region is None or self.region == region,
                self.serie is None or self.serie == serie,
                self.set_regex is None
                or bool(re.search(self.set_regex, set_id or "")),
                self.language is None or self.language == language,
                self.rarity_regex is None
                or bool(re.search(self.rarity_regex, rarity_en or "")),
                self.min_set_release is None
                or (set_release is not None and set_release >= self.min_set_release),
                self.max_set_release is None
                or (set_release is not None and set_release <= self.max_set_release),
            )
        )


@dataclass
class Decisao:
    allowed: bool
    reason: str | None = None
    anotar: str | None = None
    politica_id: int | None = None
    obriga: bool = False


def decidir(
    politicas: list[Politica],
    *,
    serie: str | None,
    kind: str,
    language: str,
    rarity_en: str | None,
    set_release: dt.date | None,
    region: str = "west",
    set_id: str | None = None,
) -> Decisao:
    """Mais específica primeiro: ordena por priority desc e a primeira que
    casa decide. Sem regra, libera."""
    candidatas = [
        p
        for p in politicas
        if p.casa(
            serie=serie,
            kind=kind,
            language=language,
            rarity_en=rarity_en,
            set_release=set_release,
            region=region,
            set_id=set_id,
        )
    ]
    if not candidatas:
        return Decisao(allowed=True)
    p = sorted(candidatas, key=lambda x: (-x.priority, x.id))[0]
    return Decisao(
        allowed=p.allowed,
        reason=p.reason,
        anotar=p.reason if (p.allowed and p.annotate) else None,
        politica_id=p.id,
        obriga=p.obriga,
    )


@dataclass
class Slot:
    kind: str
    language: str
    exists_state: str = "unknown"
    source_url: str | None = None
    notes: str | None = None
    api_variant_id: str | None = None
    principal: bool = False
    # Slot que a API não lista e uma regra de era mandou criar.
    inferido: bool = False


@dataclass
class Carta:
    """O que a geração precisa saber. Espelha as colunas de card e card_set."""

    tcgdex_id: str
    rarity_en: str | None
    api_variants: dict | None
    api_variants_detailed: list | None = None
    has_pt: bool = False
    has_ja: bool = False
    image_url_pt: str | None = None
    image_url_ja: str | None = None
    region: str = "west"
    set_tcgdex_id: str | None = None
    serie: str | None = None
    set_release: dt.date | None = None
    set_pt_release: str = "unknown"
    vetos: list[str] = field(default_factory=list)

    def tem_catalogo(self, idioma: str) -> bool:
        """O TCGdex tem esta carta naquele idioma."""
        return {"pt": self.has_pt, "ja": self.has_ja}.get(idioma, False)

    def scan(self, idioma: str) -> str | None:
        return {"pt": self.image_url_pt, "ja": self.image_url_ja}.get(idioma)


def kind_base(rarity_en: str | None) -> str:
    """O slot base de uma Full Art é 'full_art', não 'regular'."""
    r = (rarity_en or "").lower()
    for padrao, kind in RARIDADE_PARA_KIND:
        if re.search(padrao, r):
            return kind
    return "regular"


def kinds_da_carta(carta: Carta) -> list[str]:
    """Tipos de slot que a carta tem, pela ordem de FLAG_PARA_KIND.
    O primeiro da lista é a impressão principal."""
    base = kind_base(carta.rarity_en)
    variants = carta.api_variants or {}
    kinds: list[str] = []
    for flag, kind in FLAG_PARA_KIND:
        if not variants.get(flag):
            continue
        # Numa impressão especial, 'normal' e 'holo' descrevem a mesma carta.
        if kind in ("regular", "holo") and base != "regular":
            kind = base
        if kind not in kinds:
            kinds.append(kind)
    if not kinds:
        # Sem nenhuma flag o TCGdex não sabe; ainda assim a carta existe.
        kinds = [base]
    return kinds


def _variant_id(carta: Carta, kind: str) -> str | None:
    flag = KIND_PARA_FLAG.get(kind, "normal")
    for entrada in carta.api_variants_detailed or []:
        if isinstance(entrada, dict) and entrada.get("type") == flag:
            vid = entrada.get("variantId")
            return str(vid) if vid else None
    return None


def gerar_slots(
    carta: Carta,
    politicas: list[Politica],
    *,
    idiomas: tuple[str, ...] = ("en", "pt", "ja"),
    auto_confirmar: bool = True,
    base_api: str = "https://api.tcgdex.net/v2",
    lang_pt: str = "pt",
) -> list[Slot]:
    """Slots da carta, um por (kind, idioma), já filtrados pela política.

    Os idiomas pedidos são cruzados com os que a região da coleção imprime:
    pedir 'pt' numa coleção japonesa não gera nada, e é assim que deve ser.

    auto_confirmar promove só o slot principal, e só no idioma em que o
    TCGdex tem a carta. Isso é a evidência de nível 3 do documento ("scan em
    base pública"), aplicada em lote em vez de uma por uma — é o que impede a
    fila de curadoria de nascer com milhares de itens óbvios. A URL fica em
    source_url, então dá para auditar e reverter com um update.
    """
    kinds = kinds_da_carta(carta)
    inferidos = _kinds_obrigados(carta, politicas, kinds)
    kinds = kinds + inferidos
    slots: list[Slot] = []
    possiveis = IDIOMAS_POR_REGIAO.get(carta.region, ("en",))

    for idioma in idiomas:
        if idioma not in possiveis:
            continue
        # Set que o Brasil não recebeu não gera slot em português.
        if idioma == "pt" and carta.set_pt_release == "no":
            continue
        for posicao, kind in enumerate(kinds):
            d = decidir(
                politicas,
                serie=carta.serie,
                kind=kind,
                language=idioma,
                rarity_en=carta.rarity_en,
                set_release=carta.set_release,
                region=carta.region,
                set_id=carta.set_tcgdex_id,
            )
            principal = posicao == 0

            if not d.allowed:
                carta.vetos.append(f"{kind}/{idioma}: {d.reason}")
                slots.append(
                    Slot(
                        kind=kind,
                        language=idioma,
                        exists_state="unlikely",
                        notes=(
                            f"A API do TCGdex diz que esta variante existe, mas "
                            f"a política discorda: {d.reason} Confira antes de "
                            f"caçar a carta."
                        ),
                        api_variant_id=_variant_id(carta, kind),
                        principal=principal,
                    )
                )
                continue

            estado, fonte = "unknown", None
            if auto_confirmar and principal and carta.tem_catalogo(idioma):
                estado = "confirmed"
                lang_api = lang_pt if idioma == "pt" else idioma
                fonte = carta.scan(idioma) or (
                    f"{base_api}/{lang_api}/cards/{carta.tcgdex_id}"
                )

            slots.append(
                Slot(
                    kind=kind,
                    language=idioma,
                    exists_state=estado,
                    source_url=fonte,
                    notes=d.anotar,
                    api_variant_id=_variant_id(carta, kind),
                    principal=principal,
                    inferido=kind in inferidos,
                )
            )
    return slots


def _kinds_obrigados(
    carta: Carta, politicas: list[Politica], ja_tem: list[str]
) -> list[str]:
    """Tipos que uma regra de era manda criar mesmo sem a API listar.

    Existe porque a flag 'reverse' do TCGdex está ausente em eras inteiras —
    Black & White, XY e Sun & Moon dão praticamente zero, enquanto as eras
    vizinhas passam de 90%. Ver db/migrations/0008_politica_obriga.sql para a
    medição. Num masterset, slot faltando é pior que slot sobrando: o
    colecionador nunca descobre que a carta existe.

    Nasce 'unknown' com a razão em notes, e sai todo junto com um delete da
    linha de política quando a fonte preencher o dado.
    """
    extras: list[str] = []
    for p in politicas:
        if not p.obriga or p.kind in ja_tem or p.kind in extras:
            continue
        d = decidir(
            politicas,
            serie=carta.serie,
            kind=p.kind,
            language="en",
            rarity_en=carta.rarity_en,
            set_release=carta.set_release,
            region=carta.region,
            set_id=carta.set_tcgdex_id,
        )
        # Só entra se a regra que ganhou a disputa for de fato a que obriga:
        # uma negação de prioridade maior, como a de promos, tem a palavra.
        if d.allowed and d.obriga:
            extras.append(p.kind)
    return extras
