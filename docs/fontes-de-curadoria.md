# Fontes de curadoria

Para onde ir quando o TCGdex não responde. Medido em 2026-10-14, com
`robots.txt` e termos de uso lidos em cada caso.

O que o projeto precisa provar é estreito: **esta carta foi impressa em
português brasileiro?** São 19.348 slots em PT com `exists_state = 'unknown'`.
Em japonês o problema é outro: a carta existe, falta a foto — 8.899 sem scan.

## Não existe uma API que resolva

Testado, com resposta do próprio serviço:

| Fonte | Resposta |
| --- | --- |
| pokemontcg.io | `?q=language:portuguese` → `{"data":[],"count":0}`. O objeto carta não tem campo de idioma |
| pokemon-tcg-data (GitHub) | `cards/pt/`, `cards/pt-br/`, `cards/ja/`, `cards/es/`… todos 404. Só existe `cards/en/` |
| Scrydex | o FAQ diz: *"Chinese, Korean, Portuguese… are on our roadmap"* |
| TCGplayer | documentação própria: Pokémon não tem idioma português no catálogo |
| TCG Collector | português é atributo da **sua cópia**, não catálogo |
| Cardsrealm | o `pt-br` é a interface, não a impressão |

A explicação está no código-fonte do próprio TCGdex, que é open source. Em
`data/Base/Base Set/4.ts` (o Charizard):

```ts
name: { en: "Charizard", fr: "Dracaufeu", de: "Glurak", it: "Charizard" }
```

**Não existe a chave `pt`.** O campo existe no formato; ninguém preencheu para
as cartas antigas. O buraco de 2011 não é limitação de API — é catalogação que
nunca foi feita, em nenhuma base pública.

## O que dá para automatizar

| Fonte | Serve para | robots.txt |
| --- | --- | --- |
| [Elite Fourum t/61557](https://www.elitefourum.com/t/lets-see-if-we-can-collectively-figure-out-all-the-portuguese-release-dates-once-and-for-all/61557) | quais coleções saíram em PT e quando, 1999→hoje | permite ler tópico; bloqueia `/search` e `/uploads/` |
| [Serebii](https://www.serebii.net/card/) | scan e número de carta japonesa | só bloqueia `/hidden/ranch/` e `/crossword/` |
| [PriceCharting](https://www.pricecharting.com/) | segunda fonte de scan japonês | só bloqueia `/stripe-connect`, `/publish-offer`, `/buy` |
| [assets.pokemon.com](https://assets.pokemon.com/assets/cms2/img/cards/web/EX2/EX2_EN_10.png) | scan oficial, chega a 2003 | sem robots.txt (é CDN) — mas **só inglês**: PT e JA dão 404 |
| [github.com/tcgdex/cards-database](https://github.com/tcgdex/cards-database) | corrigir a lacuna na fonte | open source |

O Elite Fourum é a melhor fonte que existe para a pergunta central, e cobre
justamente o buraco pré-2011 com a cronologia editorial: **WotC 2000-2003,
Devir 2003-2011, Copag 2011+**. Mas é fórum: pela hierarquia do documento de
arquitetura, sozinho promove no máximo para `unlikely`. Com fonte primária
citada no post, serve de `confirmed`.

## O que fica fora, e por quê

| Fonte | Motivo |
| --- | --- |
| **LigaPokemon** | `robots.txt` bloqueia `?view=cards/pricehistory` e `?view=bzr/`, `Crawl-delay` 360s. Decisão já tomada no documento de arquitetura |
| **Scrydex (CDN)** | responde sem chave e cobre 73% das japonesas sem scan (44 de 60 medidos; o resto devolve o verso da carta como placeholder, md5 `14bc00fbe48a20c4…`). Mas os termos proíbem *"automated systems or excessive request patterns"* e usar o serviço como *"wholesale data source"* sem autorização escrita. `Allow: /` no robots não anula os termos |
| **TCG Album** | o `robots.txt` proíbe explicitamente agentes da Anthropic |
| **WikiDex** | o `robots.txt` bloqueia `/*?action=`, que é exatamente a API MediaWiki |

## O que o site recusa, e não há o que fazer

Estes respondem a navegador e recusam automação. O bloqueio é do site, não da
rede do projeto — liberar domínio não muda nada, e contornar desafio de bot é
burlar controle de acesso.

| Fonte | O que devolve |
| --- | --- |
| [Copag](https://www.copag.com.br/) | desafio Cloudflare |
| [Bulbapedia](https://bulbapedia.bulbagarden.net/wiki/List_of_Pok%C3%A9mon_Trading_Card_Game_expansions_in_other_languages) | desafio Cloudflare, inclusive no `/robots.txt` |
| [pokemon.com/br](https://www.pokemon.com/br/) | 403 |
| [OLX](https://www.olx.com.br/) | desafio Cloudflare |
| [pkmncards.com](https://pkmncards.com/) | 412 Precondition Failed (WAF) |

São consulta manual do curador. É uso normal de site e é como a F1 funciona: o
comando `python -m ingest fontes --card ex2-10 --lang pt` monta o link certo
para cada um.

## Credenciais, não bloqueio

| Fonte | O que falta |
| --- | --- |
| [Mercado Livre](https://developers.mercadolivre.com.br/) | app registrado e OAuth. O documento de arquitetura já prevê isso para a F3 |
| [Cardmarket](https://api.cardmarket.com/) | OAuth. `apiv2.cardmarket.com` responde; o host antigo devolve 410 |
| [CardTrader](https://api.cardtrader.com/) | token. Tem filtro de idioma oficial e é a melhor cobertura 1999-2003 |
| Scrydex | conta ou autorização escrita |

## Uma só precisa de liberação de rede

[web.archive.org](https://web.archive.org/) é o único host desta lista que o
**proxy do container** derruba — a conexão é resetada antes de chegar. É onde
está o site da Devir de 2003-2011 arquivado, que é a fonte primária da era onde
o TCGdex é zero em PT. Liberar esse domínio no ambiente é a única mudança de
acesso que muda alguma coisa.
