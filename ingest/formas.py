"""Qual forma do Pokémon a carta mostra — e quais formas cada espécie tem.

O TCGdex não diz. O `dexId` de *M Charizard EX* é 6, o mesmo do Charizard
comum, e o de *Exeggutor de Alola* é 103, o mesmo do Exeggutor de Kanto. Para
o catálogo as três são a mesma espécie, o que está certo para o masterset da
espécie e errado para quem quer só as megas.

A forma só existe no **nome da carta**, em três idiomas. Então ela é inferida,
e inferência aqui é regra escrita e medida, não chute:

| Forma    | Inglês             | Português           | Japonês      |
| -------- | ------------------ | ------------------- | ------------ |
| mega     | `M `/`M-`/`Mega `  | igual               | `メガ`        |
| primal   | `Primal `          | igual               | `ゲンシ`       |
| alola    | `Alolan `          | ` de Alola`         | `アローラ`     |
| galar    | `Galarian `        | ` de Galar`         | `ガラル`      |
| hisui    | `Hisuian `         | ` de Hisui`         | `ヒスイ`      |
| paldea   | `Paldean `         | ` de Paldea`        | `パルデア`     |

Medido no catálogo inteiro: 277 nomes de mega em inglês, 143 em português,
189 em japonês; 181 de Alola, 156 de Galar, 83 de Hisui, 43 de Paldea.

**Duas ressalvas que ficam registradas:**

*Mega Catcher é carta de treinador.* O nome começa com "Mega " e não é forma
nenhuma. Por isso a regra de mega só vale para `category = 'Pokemon'`.

*X e Y nem sempre dá para separar.* As megas da era XY se chamam todas
"M Charizard EX", X e Y com o mesmo nome — só o número da carta distingue. As
da era Mega Evolution (2025) trazem "Mega Charizard X ex" no nome. Então a
forma é uma só, `mega`, e quem quer a X olha o nome da carta.
"""

from __future__ import annotations

import re

# Regional vem antes de mega: nenhuma carta é as duas, e 'Alolan' é mais
# específico que o 'M ' do começo.
REGRAS: tuple[tuple[str, re.Pattern[str], re.Pattern[str]], ...] = (
    ("alola", re.compile(r"\bAlolan\b|\bde Alola\b", re.I), re.compile(r"^アローラ")),
    ("galar", re.compile(r"\bGalarian\b|\bde Galar\b", re.I), re.compile(r"^ガラル")),
    ("hisui", re.compile(r"\bHisuian\b|\bde Hisui\b", re.I), re.compile(r"^ヒスイ")),
    ("paldea", re.compile(r"\bPaldean\b|\bde Paldea\b", re.I), re.compile(r"^パルデア")),
    ("primal", re.compile(r"^Primal\b|\bPrimitiv[oa]\b", re.I), re.compile(r"^ゲンシ")),
    ("mega", re.compile(r"^M[\s-]|^Mega\s", re.I), re.compile(r"^メガ")),
)

# 'de Alola' em português tem acento nenhum e espaço antes; o \b do regex
# latino já cobre. O japonês precisa de âncora no início porque 'アローラ'
# também aparece no meio de nome de treinador ('アローラのすがた' não existe
# em carta, mas nomes de ginásio sim).

ROTULO = {
    "mega": "Mega",
    "primal": "Primal",
    "alola": "de Alola",
    "galar": "de Galar",
    "hisui": "de Hisui",
    "paldea": "de Paldea",
    "normal": "Normal",
}


def forma_da_carta(
    *,
    name_en: str | None,
    name_pt: str | None = None,
    name_ja: str | None = None,
    categoria: str | None = None,
    estagio: str | None = None,
) -> str:
    """A forma que a carta mostra. 'normal' quando nenhuma regra casa.

    Só Pokémon tem forma: 'Mega Catcher' é item, e sem este corte entraria
    como mega.

    O estágio entra como segunda testemunha. Medido no catálogo ocidental:
    266 cartas têm mega no nome, 94 têm `stage = MEGA`, e as 6 que o estágio
    acusa e o nome não são as Primal Kyogre/Groudon — que o TCGdex arquiva
    como MEGA porque a Reversão Primitiva é mecânica de mega. Ou seja: hoje o
    nome cobre tudo o que o estágio cobre. O estágio fica como rede para a
    coleção nova que resolver nomear diferente.
    """
    if categoria and categoria.lower() != "pokemon":
        return "normal"
    latinos = [n for n in (name_en, name_pt) if n]
    for forma, latino, japones in REGRAS:
        if any(latino.search(n) for n in latinos):
            return forma
        if name_ja and japones.search(name_ja):
            return forma
    if estagio and estagio.upper() == "MEGA":
        return "mega"
    return "normal"


# --- a Pokédex de formas, vinda da PokéAPI -------------------------------
#
# `varieties` do /pokemon-species traz slugs como 'charizard-mega-x',
# 'raichu-alola', 'charizard-gmax', 'rotom-heat'. O sufixo diz o que é.

SUFIXO_REGIONAL = {"alola": "alola", "galar": "galar", "hisui": "hisui", "paldea": "paldea"}


def classificar_variedade(slug: str) -> tuple[str, str | None]:
    """(kind, região) a partir do slug da variedade da PokéAPI.

    'charizard-mega-x' -> ('mega', None); 'raichu-alola' -> ('regional',
    'alola'); 'charizard-gmax' -> ('gigantamax', None); o resto é 'outra',
    que a tela lista mas não filtra — ver o módulo acima.
    """
    partes = slug.split("-")
    # 'pikachu-alola-cap' é o Pikachu de boné de Alola, não um Pikachu de
    # Alola: forma de jogo, não forma regional. Sem este corte ele entraria na
    # Pokédex de regionais com zero carta.
    if partes[-1] == "cap":
        return "outra", None
    if "mega" in partes:
        return "mega", None
    if "primal" in partes:
        return "primal", None
    if "gmax" in partes:
        return "gigantamax", None
    for p in partes[1:]:
        if p in SUFIXO_REGIONAL:
            return "regional", SUFIXO_REGIONAL[p]
    return "outra", None


# O repositório de sprites da PokéAPI, que a própria API usa em
# `sprites.front_default`. Hotlink, nunca rehospedagem — a mesma regra das
# cartas, que vêm do CDN do TCGdex.
SPRITES = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"


def sprite_url(pokemon_id: int) -> str:
    return f"{SPRITES}/{pokemon_id}.png"


NOME_REGIONAL = {
    "alola": "de Alola",
    "galar": "de Galar",
    "hisui": "de Hisui",
    "paldea": "de Paldea",
}


def rotulo_forma(nome_especie: str, slug_forma: str, kind: str, regiao: str | None) -> str:
    """Como a forma aparece na tela: 'Mega Charizard X', 'Raichu de Alola'.

    O slug da PokéAPI não serve de rótulo — 'charizard-mega-x' vira
    'Charizard Mega X', que ninguém escreve assim.
    """
    resto = [
        p
        for p in slug_forma.split("-")[1:]
        if p not in ("mega", "primal", "gmax") and p != regiao
    ]
    extra = " ".join(p.upper() if len(p) == 1 else p.title() for p in resto)
    if kind == "mega":
        return f"Mega {nome_especie} {extra}".strip()
    if kind == "primal":
        return f"{nome_especie} Primal"
    if kind == "gigantamax":
        return f"Gigantamax {nome_especie}"
    if kind == "regional" and regiao:
        return f"{nome_especie} {NOME_REGIONAL[regiao]}"
    return f"{nome_especie} {extra}".strip()
