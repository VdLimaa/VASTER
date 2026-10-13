"""Geração de slots de variante.

Princípio: um slot é uma compra. Se duas linhas descrevem a mesma carta
física, o masterset mentiu — e o gate da F0 exige "sem duplicata".

Por isso os slots saem SÓ do objeto variants do TCGdex, que diz quais
impressões daquela carta existem. A raridade não cria slot: ela renomeia o
slot base. Uma Full Art tem variants.normal = true e é a própria Full Art,
então gerar 'regular' + 'full_art' inventaria uma carta que não existe.

Sobre a tabela de política: ela veta (allowed=false) ou anota
(annotate=true). Vetar é o caso da reverse holo antes de Legendary
Collection; anotar é o caso da RF da era EX, que traz o nome da coleção
estampado e precisa de conferência visual antes de virar 'confirmed'.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

# Raridade -> tipo do slot base. Primeiro casamento ganha, então a ordem
# importa: 'Rainbow Rare' antes de 'Rare', 'Special Illustration' antes de
# 'Illustration'.
RARIDADE_PARA_KIND: tuple[tuple[str, str], ...] = (
    (r"rainbow", "rainbow"),
    (r"full\s*art", "full_art"),
    (r"(secret|hyper\s*rare|gold)", "gold"),
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
    ) -> bool:
        if self.kind != kind:
            return False
        # Regra por data não se aplica a set sem data: ausência de data não é
        # prova de nada, e vetar por ela esconderia slot legítimo.
        return all(
            (
                self.serie is None or self.serie == serie,
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


def decidir(
    politicas: list[Politica],
    *,
    serie: str | None,
    kind: str,
    language: str,
    rarity_en: str | None,
    set_release: dt.date | None,
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


@dataclass
class Carta:
    """O que a geração precisa saber. Espelha as colunas de card e card_set."""

    tcgdex_id: str
    rarity_en: str | None
    api_variants: dict | None
    api_variants_detailed: list | None = None
    has_pt: bool = False
    image_url_pt: str | None = None
    serie: str | None = None
    set_release: dt.date | None = None
    set_pt_release: str = "unknown"
    vetos: list[str] = field(default_factory=list)


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
    idiomas: tuple[str, ...] = ("en", "pt"),
    auto_confirmar_pt: bool = True,
    base_api: str = "https://api.tcgdex.net/v2",
    lang_pt: str = "pt",
) -> list[Slot]:
    """Slots da carta, um por (kind, idioma), já filtrados pela política.

    auto_confirmar_pt promove só o slot principal em português, e só quando o
    TCGdex tem a carta em PT. Isso é a evidência de nível 3 do documento
    ("scan em base pública"), aplicada em lote em vez de uma por uma — e é o
    que impede a fila de curadoria de nascer com 13.900 itens óbvios.
    A URL fica em source_url, então dá para auditar e reverter com um update.
    """
    kinds = kinds_da_carta(carta)
    slots: list[Slot] = []

    for idioma in idiomas:
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
            )
            if not d.allowed:
                carta.vetos.append(f"{kind}/{idioma}: {d.reason}")
                continue

            principal = posicao == 0
            estado, fonte = "unknown", None
            if (
                auto_confirmar_pt
                and idioma == "pt"
                and principal
                and carta.has_pt
            ):
                estado = "confirmed"
                fonte = carta.image_url_pt or (
                    f"{base_api}/{lang_pt}/cards/{carta.tcgdex_id}"
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
                )
            )
    return slots
