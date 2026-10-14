"""Resolução de espécie.

Fonte primária: o campo dexId da carta no TCGdex. Confirmado em
'Mega Sableye & Tyranitar GX' (sm11-126), que devolve dexId [248, 302] —
exatamente o vínculo N:N que o masterset precisa.

Fallback: casamento por nome, usado só quando dexId vem vazio. Opera sobre
tokens, não sobre substring: 'Mew' não casa dentro de 'Mewtwo' porque
'mewtwo' é um token só. Isso elimina a classe inteira de falso positivo por
prefixo.

O japonês precisa de caminho próprio, por dois motivos:

* NFKD mais remoção de combining — que é o que normaliza o latino — DESTRÓI o
  japonês: 'バンギラス' vira 'ハンキラス', porque o dakuten é um combining.
  Então o japonês usa NFKC, que ainda por cima normaliza katakana de meia
  largura.
* Japonês não separa palavra com espaço, então casar por token não funciona.
  A varredura é por caractere, pegando sempre o nome mais longo que casa
  naquela posição. É o mesmo algoritmo do latino num alfabeto sem espaços, e
  resolve o mesmo problema: 'ミュウツー' (Mewtwo) ganha de 'ミュウ' (Mew).

Trainer e Energy nunca entram na resolução. Sem esse corte, 'Clefairy Doll'
(Item do Base Set) viraria carta de Clefairy.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Grafias que não saem de title-case do slug da PokéAPI.
NOMES_IRREGULARES = {
    "mr-mime": "Mr. Mime",
    "mr-rime": "Mr. Rime",
    "mime-jr": "Mime Jr.",
    "farfetchd": "Farfetch'd",
    "sirfetchd": "Sirfetch'd",
    "ho-oh": "Ho-Oh",
    "porygon-z": "Porygon-Z",
    "nidoran-f": "Nidoran♀",
    "nidoran-m": "Nidoran♂",
    "type-null": "Type: Null",
    "jangmo-o": "Jangmo-o",
    "hakamo-o": "Hakamo-o",
    "kommo-o": "Kommo-o",
    "tapu-koko": "Tapu Koko",
    "tapu-lele": "Tapu Lele",
    "tapu-bulu": "Tapu Bulu",
    "tapu-fini": "Tapu Fini",
    "flabebe": "Flabébé",
    "wo-chien": "Wo-Chien",
    "chien-pao": "Chien-Pao",
    "ting-lu": "Ting-Lu",
    "chi-yu": "Chi-Yu",
    "great-tusk": "Great Tusk",
    "iron-valiant": "Iron Valiant",
}

CATEGORIAS_POKEMON = frozenset({"pokemon", "pokémon"})

# Hiragana, katakana, kanji e o prolongador.
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

# Nome japonês com menos caracteres que isso não entra no índice: um
# caractere solto casaria dentro de qualquer nome e encheria o masterset.
MIN_TOKENS_JA = 2

_SIMBOLOS = {"♀": " f", "♂": " m"}


def normalizar(texto: str) -> list[str]:
    """Quebra um nome em tokens comparáveis entre idiomas e grafias.

    'Mr. Mime' e o slug 'mr-mime' caem os dois em ['mr', 'mime'].
    'Flabébé' e 'flabebe' caem em ['flabebe']. 'Nidoran♀' em ['nidoran', 'f'].
    """
    for simbolo, troca in _SIMBOLOS.items():
        texto = texto.replace(simbolo, troca)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.replace("'", "").replace("’", "")
    texto = re.sub(r"[^0-9a-zA-Z]+", " ", texto)
    return [t for t in texto.lower().split() if t]


def tem_cjk(texto: str) -> bool:
    return bool(CJK.search(texto or ""))


def normalizar_ja(texto: str) -> str:
    """NFKC, não NFKD: preserva o dakuten e junta katakana de meia largura.
    Devolve uma string, não tokens — japonês não separa palavra por espaço."""
    texto = unicodedata.normalize("NFKC", texto or "")
    return "".join(ch for ch in texto if not ch.isspace()).lower()


def nome_de_slug(slug: str) -> str:
    if slug in NOMES_IRREGULARES:
        return NOMES_IRREGULARES[slug]
    return " ".join(parte.capitalize() for parte in slug.split("-"))


def eh_pokemon(categoria: str | None) -> bool:
    """A categoria vem traduzida: 'Pokemon' em en, 'Pokémon' em pt.
    Por isso a comparação é normalizada e não por igualdade."""
    if not categoria:
        return False
    return categoria.strip().lower() in CATEGORIAS_POKEMON


@dataclass(frozen=True)
class Especie:
    dex_number: int
    slug: str
    name_en: str
    name_pt: str
    name_ja: str | None = None


class IndiceEspecies:
    """Casa nome de carta contra a lista de espécies.

    Em alfabeto latino, por sequência de tokens. Em japonês, por caractere.
    Nos dois casos do mais longo para o mais curto e sem sobreposição, que é o
    que impede 'Mew' de casar dentro de 'Mewtwo' e 'ミュウ' dentro de
    'ミュウツー'.
    """

    def __init__(self, especies: list[Especie]) -> None:
        self.por_dex = {e.dex_number: e for e in especies}
        self._por_tokens: dict[tuple[str, ...], Especie] = {}
        self._por_ja: dict[str, Especie] = {}
        for e in especies:
            for nome in {e.name_en, e.name_pt, e.slug}:
                tokens = tuple(normalizar(nome))
                if tokens:
                    # Em empate, o menor dex_number ganha. Determinístico.
                    anterior = self._por_tokens.get(tokens)
                    if anterior is None or e.dex_number < anterior.dex_number:
                        self._por_tokens[tokens] = e
            if e.name_ja:
                chave = normalizar_ja(e.name_ja)
                if len(chave) >= MIN_TOKENS_JA:
                    anterior = self._por_ja.get(chave)
                    if anterior is None or e.dex_number < anterior.dex_number:
                        self._por_ja[chave] = e
        self._maior = max((len(t) for t in self._por_tokens), default=1)
        self._maior_ja = max((len(k) for k in self._por_ja), default=1)

    def casar(self, nome_carta: str) -> list[Especie]:
        """Espécies citadas no nome, na ordem em que aparecem, sem repetir."""
        achados = self._casar_tokens(nome_carta)
        if not achados and tem_cjk(nome_carta):
            achados = self._casar_ja(nome_carta)
        return achados

    def _casar_tokens(self, nome_carta: str) -> list[Especie]:
        tokens = normalizar(nome_carta)
        achados: list[Especie] = []
        i = 0
        while i < len(tokens):
            for tamanho in range(min(self._maior, len(tokens) - i), 0, -1):
                especie = self._por_tokens.get(tuple(tokens[i : i + tamanho]))
                if especie is not None:
                    if especie not in achados:
                        achados.append(especie)
                    i += tamanho
                    break
            else:
                i += 1
        return achados

    def _casar_ja(self, nome_carta: str) -> list[Especie]:
        texto = normalizar_ja(nome_carta)
        achados: list[Especie] = []
        i = 0
        while i < len(texto):
            limite = min(self._maior_ja, len(texto) - i)
            for tamanho in range(limite, MIN_TOKENS_JA - 1, -1):
                especie = self._por_ja.get(texto[i : i + tamanho])
                if especie is not None:
                    if especie not in achados:
                        achados.append(especie)
                    i += tamanho
                    break
            else:
                i += 1
        return achados


def especies_da_carta(
    carta: dict, indice: IndiceEspecies
) -> tuple[list[Especie], str]:
    """Devolve as espécies da carta e qual resolvedor decidiu.

    dexId manda. Nome é fallback. Trainer e Energy devolvem lista vazia.
    """
    if not eh_pokemon(carta.get("category")):
        return [], "dex_id"

    dex_ids = carta.get("dexId") or []
    if dex_ids:
        achados = [indice.por_dex[d] for d in dex_ids if d in indice.por_dex]
        if achados:
            return achados, "dex_id"

    nome = carta.get("name") or ""
    return indice.casar(nome), "name_match"
