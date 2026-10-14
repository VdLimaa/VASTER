"""Para onde o curador vai quando o TCGdex não responde.

Nenhuma destas fontes é raspada. O que este módulo faz é montar a URL de
consulta certa para cada slot, para a tela de curadoria abrir num clique. É a
diferença entre coletar o dado de alguém e levar uma pessoa até ele.

A escolha de cada fonte foi medida em 2026-10-14, com robots.txt e termos de
uso lidos — ver docs/fontes-de-curadoria.md. Três ficaram de fora de propósito:

* LigaPokemon, que o documento de arquitetura já descartou: o robots.txt
  bloqueia as páginas de preço e o Crawl-delay é de 360s. Entra só como link.
* Scrydex, cujo CDN responde sem chave e cobre 73% das cartas japonesas sem
  scan — mas os termos proíbem "automated systems or excessive request
  patterns" e usar o serviço como "wholesale data source" sem autorização
  escrita. Entra só como link.
* WikiDex, cujo robots.txt bloqueia '/*?action=', que é justamente a API
  MediaWiki. Entra só como link para a página.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass

# Quem imprimiu carta Pokémon em português, por período. Levantado pela
# comunidade no Elite Fourum e usado aqui só para orientar a busca do curador:
# saber que 2005 é era Devir muda o termo que se procura.
ERAS_BR = (
    ("1999-01-01", "2003-12-31", "WotC",
     "Era WotC. Impressão em português existiu, mas é rara e mal documentada."),
    ("2004-01-01", "2011-06-30", "Devir",
     "Era Devir, a distribuidora no Brasil. É o buraco mais fundo do TCGdex."),
    ("2011-07-01", "2099-12-31", "Copag",
     "Era Copag, que imprime no Brasil desde 2011. Documentação melhor."),
)


@dataclass(frozen=True)
class Fonte:
    nome: str
    url: str
    para_que: str
    # 'auto' = dá para consultar por programa; 'manual' = só a pessoa abre.
    acesso: str
    nota: str = ""


def _q(texto: str) -> str:
    return urllib.parse.quote_plus(texto)


def era_br(release_date) -> tuple[str, str] | None:
    """Quem imprimia no Brasil quando este set saiu."""
    if release_date is None:
        return None
    iso = release_date.isoformat() if hasattr(release_date, "isoformat") else str(release_date)
    for inicio, fim, quem, nota in ERAS_BR:
        if inicio <= iso <= fim:
            return quem, nota
    return None


def para_slot(
    *,
    card_name: str,
    card_name_en: str | None,
    set_name: str,
    set_id: str,
    number: str,
    language: str,
    kind: str,
    region: str = "west",
) -> list[Fonte]:
    """As fontes que fazem sentido para este slot, na ordem em que o curador
    deve tentar."""
    nome = card_name_en or card_name
    fontes: list[Fonte] = []

    if language == "pt":
        fontes.append(Fonte(
            nome="Elite Fourum — lançamentos em português",
            url="https://www.elitefourum.com/t/lets-see-if-we-can-collectively-figure-out-"
                "all-the-portuguese-release-dates-once-and-for-all/61557",
            para_que="descobrir se a COLEÇÃO saiu em português e quando",
            acesso="auto",
            nota="pesquisa colaborativa, de 1999 a hoje. Vale no nível de coleção, "
                 "não de carta. Como é fórum, promove no máximo para 'unlikely' "
                 "sozinho; com fonte primária citada, serve de 'confirmed'.",
        ))
        fontes.append(Fonte(
            nome="LigaPokemon",
            url=f"https://www.ligapokemon.com.br/?view=cards/card&card={_q(nome + ' ' + number)}",
            para_que="anúncio brasileiro mostrando a impressão em português",
            acesso="manual",
            nota="o robots.txt bloqueia as páginas de preço e o Crawl-delay é 360s. "
                 "Abrir no navegador é uso normal; raspar não.",
        ))
        fontes.append(Fonte(
            nome="Mercado Livre",
            url=f"https://lista.mercadolivre.com.br/{_q(nome + ' ' + number + ' ' + set_name)}",
            para_que="anúncio com foto da carta em português",
            acesso="auto",
            nota="tem API oficial com OAuth, prevista para a F3. A foto do anúncio "
                 "costuma mostrar a impressão, que é a prova que falta.",
        ))
        fontes.append(Fonte(
            nome="Bulbapedia — a coleção em outros idiomas",
            url="https://bulbapedia.bulbagarden.net/wiki/"
                "List_of_Pok%C3%A9mon_Trading_Card_Game_expansions_in_other_languages",
            para_que="tabela por coleção com coluna de português brasileiro",
            acesso="manual",
            nota="Cloudflare bloqueia automação; no navegador abre normal.",
        ))

    if language == "ja" or region == "jp":
        fontes.append(Fonte(
            nome="Serebii — base de cartas japonesas",
            url=f"https://www.serebii.net/card/{_q(set_name.lower().replace(' ', ''))}/",
            para_que="scan e número da carta japonesa",
            acesso="auto",
            nota="robots.txt só bloqueia /hidden/ranch/ e /crossword/.",
        ))
        fontes.append(Fonte(
            nome="PriceCharting — coleções japonesas",
            url=f"https://www.pricecharting.com/search-products?q={_q(nome + ' ' + number)}"
                f"&type=prices",
            para_que="segunda fonte de scan japonês",
            acesso="auto",
        ))
        fontes.append(Fonte(
            nome="pokemon-card.com — base oficial japonesa",
            url=f"https://www.pokemon-card.com/card-search/index.php?keyword={_q(card_name)}",
            para_que="a fonte oficial e definitiva do catálogo japonês",
            acesso="manual",
            nota="a busca exige sessão; abrir no navegador funciona.",
        ))
        fontes.append(Fonte(
            nome="Scrydex (CDN)",
            url=f"https://images.scrydex.com/pokemon/{set_id.lower()}_ja-"
                f"{number.lstrip('0') or '0'}/large",
            para_que="scan japonês onde o TCGdex não tem",
            acesso="manual",
            nota="cobre 73% das japonesas sem scan (44 de 60 medidos; o resto "
                 "devolve o verso da carta como placeholder). Os termos proíbem "
                 "coleta automatizada sem autorização escrita, então é link, "
                 "não integração.",
        ))

    fontes.append(Fonte(
        nome="TCGdex — contribuir de volta",
        url="https://github.com/tcgdex/cards-database",
        para_que="corrigir a lacuna na fonte, não só no seu banco",
        acesso="auto",
        nota="é open source. A carta antiga tem name: {en, fr, de, it} e nenhuma "
             "chave 'pt' — por isso o corte de 2011. Cada curadoria sua pode "
             "virar um pull request.",
    ))
    return fontes
