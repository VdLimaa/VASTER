# O que o TCGdex entrega de fato

Medido em 2026-10-13 contra a API ao vivo, durante a implementação da F0.
Cada número aqui saiu de uma requisição, não de leitura de documentação.
Reproduzir: `python -m ingest coverage` depois de `sets` e `cards`.

Este documento existe porque sete das premissas de
[arquitetura.md](arquitetura.md) não sobreviveram ao contato com a API. Nenhuma
delas invalida o projeto; duas melhoram bastante, uma muda o modelo e a sétima
é o que torna o catálogo inteiro viável.

A seção 11 registra um erro meu, não da API: uma regra que escrevi a partir de
uma amostra pequena demais e que o catálogo completo refutou.

## 1. `pt-br` não é o português do card game

A premissa era ingerir `pt-br`. Medição:

| Idioma | Sets | Cartas | O que é |
| --- | --- | --- | --- |
| `en` | 220 | 23.736 | catálogo completo |
| `pt` | 125 | 13.907 | **card game físico em português brasileiro** |
| `pt-br` | 11 | 1.124 | **Pokémon TCG Pocket**, o app |

Das 1.124 cartas em `pt-br`, 1.124 têm id de set do Pocket (`A1`, `A2`, `B2`,
`P-A`). Das 13.907 em `pt`, zero. A separação é limpa: o TCGdex usa `pt-br`
para o app e `pt` para a carta impressa.

Consequência: `TCGDEX_LANG_PT=pt`. Ingerir `pt-br` traria 1.124 cartas de app
e nenhuma carta de fichário.

Nota de nomenclatura: o `lang` do banco é `'pt'`, e o nome real de `swsh7` em
português é **Céus em Evolução**, não "Céus Evolutivos" como está no documento
de arquitetura. Nome de coleção vem da API, nunca digitado.

## 2. A cobertura em português começa em 2011

| Série | Lançada | Cartas EN | Cartas PT | % |
| --- | --- | ---: | ---: | ---: |
| Base | 1999-01-09 | 494 | 0 | 0% |
| Gym | 2000-08-14 | 264 | 0 | 0% |
| Neo | 2000-12-16 | 383 | 0 | 0% |
| Legendary Collection | 2002-05-24 | 110 | 0 | 0% |
| E-Card | 2002-08-01 | 542 | 0 | 0% |
| EX | 2003-07-01 | 1.727 | 0 | 0% |
| POP | 2003-10-01 | 193 | 0 | 0% |
| Trainer kits | 2004-07-01 | 475 | 0 | 0% |
| Diamond & Pearl | 2007-05-01 | 900 | 0 | 0% |
| Platinum | 2009-02-11 | 533 | 0 | 0% |
| HeartGold & SoulSilver | 2010-02-10 | 439 | 0 | 0% |
| Call of Legends | 2011-02-09 | 106 | 0 | 0% |
| **Black & White** | **2011-04-25** | **1.437** | **1.175** | **82%** |
| McDonald's Collection | 2011-06-17 | 166 | 0 | 0% |
| XY | 2013-10-12 | 1.932 | 1.593 | 82% |
| Sun & Moon | 2017-02-03 | 2.917 | 2.736 | 94% |
| Sword & Shield | 2019-11-15 | 3.675 | 3.640 | 99% |
| Scarlet & Violet | 2023-03-31 | 3.698 | 3.656 | 99% |
| Pokémon TCG Pocket | 2024-10-30 | 2.480 | 0 | 0% |
| Mega Evolution | 2025-09-25 | 1.264 | 1.107 | 88% |
| **Total** | | **23.736** | **13.907** | **59%** |

O documento de arquitetura previa que "a completude do `pt-br` cai muito nas
coleções antigas". A medição é mais dura que isso: não cai, **é zero**. Existe
um corte seco em Black & White (2011). Antes dele o TCGdex não tem uma única
carta em português, nas 5.705 cartas das eras Base até Call of Legends.

E o Brasil recebeu essas coleções. O próprio TCGdex sabe: `base1` aparece em
`/pt/sets` com o nome **Coleção Básica** e zero cartas. São 33 sets nessa
situação — nome em português, catálogo vazio:

```
A1 A1a A2 A2a A2b A3 A4a B1a B2 B2a P-A base1 base2 base3 bw11 cel25cc
col1 dp1 dp2 dp3 dv1 ex1 ex7 ex8 ex9 ex10 g1 hgss1 hgss2 hgss3 hgss4 sm115 sma
```

Tirando os 11 do Pocket, sobram 22 sets físicos que são a fila de curadoria de
prioridade máxima. É exatamente a tese da zona de curadoria, agora com número:
**5.705 cartas sem resposta em português**, e é ali que o colecionador
brasileiro de carta antiga vive.

Consequência de schema: `card_set.pt_card_count` guarda essa contagem, e
`pt_release` sobe para `'yes'` quando o set aparece em `/pt/sets` mas **nunca
desce para `'no'`** por ausência. Ausência na API não é prova de inexistência.

## 3. `GET /sets/{id}` não traz `variants`

A lista de cartas dentro de um set tem só `id`, `localId`, `name` e `image`.
Gerar slot exige `variants`, que só existe em `GET /cards/{id}`.

Em compensação existe `GET /{lang}/cards`, que devolve **todas** as cartas do
idioma em uma requisição (2,4 MB em `en`). Então:

| Passo | Requisições | Para quê |
| --- | --- | --- |
| `cards` | 2 | 23.736 cartas: nome, número, imagem, cobertura PT |
| `details` | 1 por carta | `variants`, `rarity`, `category`, `dexId` |

Separar os dois é o que deixa a ingestão retomável e permite fechar o gate do
Sableye com 35 requisições em vez de 23.736. O passo 2 do documento de
arquitetura, "para cada set, `GET /en/sets/{id}` → upsert das cartas,
guardando `variants`", não funciona como escrito.

## 4. A carta já vem com `dexId` — e com preço

Dois campos que o documento não previa:

**`dexId`** resolve a espécie sem parsing de nome:

```
GET /en/cards/sm11-126
{ "name": "Mega Sableye & Tyranitar GX", "dexId": [248, 302], ... }
```

O caso mais difícil do gate da F0 vem resolvido da API. O parsing de nome
contra a PokéAPI continua implementado, como fallback para carta sem `dexId`.
E existe `GET /cards?dexId=302`, que devolve as 35 cartas de Sableye direto —
é assim que `card_species` é preenchida sem varrer o catálogo.

A resolução só roda em carta com `category` de Pokémon. Sem esse corte,
`Clefairy Doll` (Item do Base Set) entraria no masterset de Clefairy. Atenção:
`category` vem traduzido — `"Pokemon"` em `en`, `"Pokémon"` em `pt` — então a
comparação é normalizada.

**`variants_detailed`** traz, por variante, um `variantId` e preço de
Cardmarket e TCGplayer com data:

```json
{ "type": "normal", "variantId": "endfynwn4n10gzq",
  "pricing": { "cardmarket": { "updated": "2026-10-12T22:54:33Z", "unit": "EUR",
               "avg": 0.05, "low": 0.02, "trend": 0.07, "avg30": 0.05 } } }
```

Isso muda a F3. O documento previa chegar a TCGplayer e Cardmarket via
pokemontcg.io; a fonte vem junto do catálogo, já **por variante**, que é a
granularidade de `card_variant`. Dois ganhos: uma integração a menos, e o
preço já casa com o slot em vez de com a carta. Falta converter para BRL e
pesar contra o preço do Mercado Livre, que continua sendo a referência local.

`card_variant.api_variant_id` existe para guardar esse `variantId`.

## 5. A regra de reverse holo do documento está certa, e a API concorda

A afirmação era: "Reverse holo só existe a partir de Legendary Collection
(2002)". Testado buscando o detalhe de todas as cartas dos dois sets:

| Set | Lançamento | Cartas | Com `reverse` |
| --- | --- | ---: | ---: |
| `base1` Base Set | 1999-01-09 | 102 | **0** |
| `lc` Legendary Collection | 2002-05-24 | 110 | **110** |

Corte limpo. A política em `variant_policy` usa `max_set_release =
'2002-05-23'`, e `lc` lançou em 24 — fica de fora do veto por um dia, de
propósito.

A conclusão prática é que, nesses dois sets, a política é rede de segurança e
não corretor: a API já responde certo. Ela continua valendo porque o veto por
raridade (Ultra Rara, Full Art e Rainbow não têm RF) e a anotação da era EX
não vêm de lugar nenhum.

## 6. Detalhes operacionais

**URL de imagem precisa de sufixo.** `assets.tcgdex.net/en/swsh/swsh7/67`
responde `text/html` com 295 bytes; `.../67/high.png` responde `image/png` com
327 KB. `ingest.tcgdex.image_url` monta o sufixo.

**A imagem muda por idioma.** `/pt/swsh/swsh7/67/high.png` é um scan
diferente, com nome e coleção em português. Por isso `card.image_url_pt`
existe separado de `card.image_url`.

**Id de set não é o que se imagina.** A era Scarlet & Violet é `sv01`...`sv10`,
não `sv1`. E existe `sv03` ao lado de `sv03.5`, então casar carta com set pelo
prefixo exige o prefixo mais longo primeiro — `sv03.5-1` não é de `sv03`.

**Header HTTP tem que ser ASCII.** `User-Agent` com acento levanta
`UnicodeEncodeError` no httpx antes de qualquer requisição sair.

**O Pocket está no catálogo.** São 2.480 cartas de app em 15 sets da série
`tcgp`, que não existem em papel. `card_set.is_digital` marca a série e o
masterset as exclui por padrão; Sableye tem 3 cartas no Pocket que não entram
num fichário.

## 7. O gate da F0, com dado real

```
python -m ingest gate --species sableye
```

| O que o gate pede | Resultado |
| --- | --- |
| Todas as coleções conhecidas | 27 coleções físicas, de `ex2` (2003) a `me02` (2025) |
| Sem duplicata | 0 |
| Tag Team ligada às duas espécies | 4 cartas `Mega Sableye & Tyranitar GX` em `sableye` e `tyranitar`, via `dex_id` |

Um ajuste de expectativa: o gate da F1 no documento fala em "os 35 slots de
Sableye". 35 é o número de **cartas**. Os slots são **94** — 47 em inglês e 47
em português, porque cada carta rende entre um e três slots. A conta de quanto
tempo leva curar uma espécie precisa usar 94, não 35.

Dos 94, 21 nasceram `confirmed` com prova: o TCGdex tem o scan em português
daquela carta. As 21 URLs foram verificadas uma a uma e todas respondem 200.
Isso é a evidência de nível 3 da hierarquia do documento ("scan em base
pública"), aplicada em lote. Sobram 73 slots para decisão humana, e os 12
`reverse_holo` em português são os que realmente precisam de carta na mão.

## 8. Japonês não é tradução: é outro catálogo

O documento de arquitetura trata idioma como atributo do slot, e o enum `lang`
já aceitava `'ja'`. Para o português isso está certo — é a mesma coleção
traduzida, com o mesmo `tcgdex_id`. Para o japonês não vale.

| | Oeste (`en`/`pt`) | Japão (`ja`) |
| --- | ---: | ---: |
| Coleções | 220 | 184 |
| Cartas | 23.736 | 12.781 |
| Ids de coleção | `swsh7`, `sv04.5`, `base1` | `PMCG1`, `VS1`, `web1`, `S6K` |
| Cartas com scan | ~100% | 3.882 (30%) |

Três medições que fecham a questão:

1. **Id de carta inglesa dá 404 em `ja`.** `swsh7-67`, `sm11-126` e `base1-4`
   não existem no catálogo japonês. Não há o que casar.
2. **Quatro ids colidem, e são coleções diferentes.** `neo1` é *Neo Genesis*
   (111 cartas, 2000-12-16) em inglês e 金、銀、新世界へ... (96 cartas,
   2000-02-04) em japonês. Com o `unique (tcgdex_id)` original, ingerir o
   japonês sobrescreveria a coleção inglesa. A chave passou a ser
   `(tcgdex_id, region)` em `card_set` e em `card`.
3. **Carta japonesa não tem nome em inglês.** `/en/cards/SM7b-016` e
   `/en/cards/S6K-028` devolvem 404. Por isso `card.name_en` deixou de ser
   obrigatório e existe `card.name_ja`.

A consequência de modelo: **uma carta japonesa não é o slot `ja` de uma carta
inglesa, é outra carta, em outra coleção.** O enum `lang` continua valendo —
idioma é atributo do slot — mas *quais* idiomas um slot pode ter passou a
depender de `card_set.region`:

| Região | Idiomas que a coleção imprime |
| --- | --- |
| `west` | `en`, `pt` |
| `jp` | `ja` |

Pedir `--langs pt` numa coleção japonesa não gera nada, e é assim que deve ser.

### Japonês não tem reverse holo

Amostra de 54 cartas em três coleções de eras diferentes:

| Coleção | Amostra | `reverse` | `holo` | `normal` |
| --- | ---: | ---: | ---: | ---: |
| `S6K` 漆黒のガイスト (2021) | 18 | **0** | 6 | 12 |
| `SM7b` フェアリーライズ (2018) | 18 | **0** | 4 | 14 |
| `PCG1` 拡張パック (2004) | 18 | **0** | 2 | 16 |

Virou linha em `variant_policy` com `region = 'jp'`, prioridade 110. A API já
responde certo, então a regra é rede de segurança — igual à do corte de 2002.

### A `variant_policy` passou a falar por região

Sem isso uma regra escrita para a era `e` do oeste casaria com a série `e`
japonesa, que é outra coisa. Regras sem região continuam valendo nas duas.

### Duas lacunas do catálogo japonês

**Scan.** Só 30% das cartas japonesas têm foto, contra praticamente 100% no
oeste. Em Sableye são 5 de 21. Coleções inteiras estão sem nenhuma: `MC`
(774 cartas), `SV` (288), `S8b` (285), `M2a` (250), `SM8b` (250).

**Nome.** 407 das 12.781 cartas (3%) têm o nome em alfabeto latino em vez do
japonês, às vezes em minúscula: `PCG2-070` e `PCG8-062` vêm como `'sableye'`,
`PCG5-002` como `'weepinbell'`. É lacuna de preenchimento do catálogo, não da
carta. O dado é guardado como a API devolve; a tela capitaliza a primeira letra
só para exibir. É um bom candidato a contribuição de volta ao TCGdex, que é
open source — a mesma mitigação que o documento de arquitetura já prevê para a
cobertura PT.

## 9. "Sem scan" e "fora do catálogo" são coisas diferentes

A primeira versão da tela chamava os dois de "sem scan em PT". São situações
distintas e as duas existem em volume:

| Situação | Cartas | O que significa |
| --- | ---: | --- |
| No catálogo PT, com foto | 12.746 | o TCGdex tem a carta em português e tem a imagem |
| No catálogo PT, sem foto | 1.161 | a carta saiu em português; ninguém publicou scan |
| Fora do catálogo PT | 9.829 | o TCGdex não tem registro nenhum dela em português |

Para a curadoria a diferença é tudo. "Sem foto" é um slot que já dá para
confirmar — o registro no catálogo é a evidência. "Fora do catálogo" é um slot
que ninguém pode decidir sem a carta na mão ou um anúncio, e **não prova que a
carta não existe em português**: o TCGdex não tem uma única carta em português
antes de 2011, e o Brasil recebeu aquelas coleções.

Em Sableye o recorte é nítido: dos 44 slots em português, 27 estão no catálogo
(todos com foto) e 17 estão fora dele. Nenhum é "no catálogo sem foto". No
japonês é o inverso: os 21 slots estão todos no catálogo, e 16 deles não têm
foto.

A consulta do masterset devolve os dois sinais separados, `has_scan` e
`no_catalogo`, e a tela mostra cada um com a sua etiqueta.

## 10. O GraphQL entrega o catálogo inteiro em uma requisição

O passo `details` é o caro: `variants` só existe no detalhe da carta, uma
requisição por carta. Para as 1.025 espécies isso seria ~37.000 requisições só
no oeste, uns 23 minutos.

O TCGdex tem um endpoint GraphQL em `POST /v2/graphql`. Esta consulta devolve
**todas as 23.736 cartas ocidentais com `variants`, `rarity`, `category`,
`dexId` e `illustrator`**, em 4,7 MB e 0,75 s:

```graphql
{ cards { id localId name rarity category dexId illustrator image
          variants { normal reverse holo firstEdition wPromo } } }
```

Medido: 23.736 cartas, 23.736 com `variants`, 19.926 com `dexId`, 23.017 com
`illustrator`. É o comando `details --all --bulk`, e levou 5 segundos contra os
23 minutos do caminho REST.

Três limites, confirmados por introspecção do schema:

1. **Só serve o inglês.** `CardsFilters` tem 17 campos — `category`, `dexId`,
   `rarity`, `illustrator` e outros — e **nenhum de idioma**. `Accept-Language`
   é ignorado, `/v2/ja/graphql` é 404, e id japonês (`S6K-028`) volta vazio. O
   catálogo japonês continua custando uma requisição por carta: 12.781, uns 6
   minutos.
2. **Não traz `variants_detailed`**, que é onde está o `variantId` e o preço
   por variante. Para a F3 o caminho REST continua necessário, mas aí já dá
   para escopar no recorte que interessa.
3. **Não traz `rarity_pt`**, que só vem do detalhe em português.

`{ cards { id } }` também devolve as 23.736 sem paginar — o argumento
`pagination` existe no schema mas rejeita o formato `{page, itemsPerPage}`.

## 11. Correção: minha regra de reverse holo japonês estava errada

Registrado porque o erro é instrutivo.

A seção 8 afirmou, com base em 54 cartas amostradas em três coleções (`S6K`,
`SM7b`, `PCG1`), que o card game japonês não imprime reverse holo. Ao rodar o
catálogo completo, **1.008 cartas japonesas têm a flag `reverse`** — e as 11
coleções onde isso acontece são todas high-class pack ou coleção especial:

| Coleção | Nome | Lançamento | Cartas com reverse |
| --- | --- | --- | ---: |
| `S8b` | VMAXクライマックス | 2021-12-03 | 110 |
| `S9a` | バトルリージョン | 2022-02-25 | 45 |
| `S10a` | ダークファンタズマ | 2022-05-13 | 49 |
| `S11a` | 白熱のアルカナ | 2022-09-02 | 46 |
| `S12a` | VSTARユニバース | 2022-12-02 | 89 |
| `SV2a` | ポケモンカード151 | 2023-06-16 | 153 |
| `SV4a` | レイジングサーフ | 2023-12-01 | 93 |
| `SV8a` | テラスタルフェスex | 2024-12-06 | 145 |
| `SV11B` / `SV11W` | ブラックボルト / ホワイトフレア | 2025-06-06 | 160 |
| `M2a` | MEGAドリームex | 2025-11-28 | 118 |

Essas coleções trazem versão espelhada desde VMAX Climax, em 2021. A amostra
pegou só expansões regulares, onde de fato não há. A API acerta carta a carta;
a regra é que generalizava.

A regra saiu em `0007_japones_correcoes.sql`, e os 1.008 slots que ela havia
marcado voltaram para `unknown`. O que fica: **regra por era só entra quando a
amostra cobre a variação que ela pretende descrever.** As outras duas regras
sobreviveram porque a API concorda com elas em 23.734 de 23.736 cartas.

## 12. Negar um slot não é descartá-lo

`kinds_da_carta` só produz variante que a API afirma existir. Então toda
negação da política é uma **discordância** entre a API e a regra — e sumir com
ela em silêncio esconde justamente o caso que alguém precisa olhar.

Slot negado passou a nascer com `exists_state = 'unlikely'` e a razão em
`notes`. É o estado que o documento de arquitetura reserva para evidência
fraca, e o único que a constraint deixa existir sem `source_url`.

No catálogo inteiro são 22 slots: 18 de reverse holo em set anterior a 2002
(promos `basep` e Southern Islands) e 4 em raridade que não tem RF (duas cartas
da Trainer Gallery de Brilliant Stars).

## 13. Nome japonês da espécie, e por que token não serve

434 cartas japonesas de Pokémon não têm `dexId`. Sem nome japonês na tabela
`species`, nenhuma delas entrava em masterset nenhum.

A PokéAPI tem o nome japonês no detalhe de cada espécie (`names[].language.name
== "ja"`), uma requisição por espécie: 1.025 ao todo, 17 segundos. Virou
`species.name_ja`.

Duas armadilhas no casamento:

1. **NFKD destrói o japonês.** A normalização do latino faz NFKD e remove os
   caracteres combining; em japonês o dakuten É um combining, então
   `バンギラス` (Tyranitar) vira `ハンキラス` e não casa com nada. O japonês usa
   NFKC, que preserva o dakuten e ainda normaliza katakana de meia largura.
2. **Japonês não separa palavra com espaço.** `メガヤミラミ&バンギラスGX` é um
   token só até o `&`, então casar por token não acha `ヤミラミ` lá dentro. A
   varredura é por caractere, sempre pegando o nome mais longo que casa naquela
   posição — o mesmo algoritmo do latino, num alfabeto sem espaços. É isso que
   faz `ミュウツー` (Mewtwo) ganhar de `ミュウ` (Mew), exatamente como
   'Mewtwo' ganha de 'Mew'.

Resultado: 433 das 434 resolvidas. A que sobra é `E4-070` 埋もれた化石
(Buried Fossil), carta de fóssil que legitimamente não nomeia espécie nenhuma.

## 14. O catálogo completo, medido

| | |
| --- | ---: |
| Coleções | 404 |
| Cartas | 36.517 |
| Espécies na PokéAPI | 1.025 |
| **Espécies com pelo menos uma carta** | **1.025** |
| Vínculos carta↔espécie | 30.672 |
| Slots de variante | 80.464 |

Resolução de espécie: 30.053 vínculos por `dexId`, 619 por casamento de nome.
Zero cartas Trainer ou Energy ganharam espécie — o corte por categoria segurou
em 36.517 cartas.

Slots por espécie: mínimo 6, mediana 55, média 66, máximo 635 (Pikachu).

| Idioma | Confirmados | A confirmar | Improváveis |
| --- | ---: | ---: | ---: |
| `pt` | 13.907 | 19.348 | 11 |
| `en` | 0 | 33.255 | 11 |
| `ja` | 12.781 | 1.151 | 0 |

Os confirmados são promoção em lote: o TCGdex tem a carta naquele idioma. O
inglês fica todo em `unknown` porque não há nada a provar — a carta do catálogo
ocidental É a inglesa — e isso é uma decisão a revisitar: faria sentido o slot
principal em inglês nascer confirmado também.

Tempo total, do banco vazio ao catálogo completo: cerca de **7 minutos**, dos
quais 6 são as 12.781 requisições do catálogo japonês.

## 15. A flag `reverse` do TCGdex falta em eras inteiras

O achado mais grave da investigação, e o que mais afeta o produto.

Percentual de cartas Common, Uncommon, Rare e Rare Holo com `variants.reverse
= true`, por era, no catálogo ocidental inteiro:

| Era | Desde | Alvo | Com RF | % |
| --- | --- | ---: | ---: | ---: |
| Legendary Collection | 2002-05-24 | 91 | 91 | 100% |
| E-Card | 2002-09-15 | 437 | 434 | 99% |
| EX | 2003-07-01 | 1.655 | 875 | 53% |
| POP | 2003-10-01 | 193 | 7 | 4% |
| Trainer kits | 2004-07-01 | 251 | 0 | 0% |
| Diamond & Pearl | 2007-05-01 | 869 | 801 | 92% |
| Platinum | 2009-02-11 | 433 | 415 | 96% |
| HeartGold & SoulSilver | 2010-02-10 | 320 | 309 | 97% |
| Call of Legends | 2011-02-09 | 73 | 65 | 89% |
| **Black & White** | **2011-04-25** | **1.345** | **5** | **0%** |
| **XY** | **2013-10-12** | **1.369** | **0** | **0%** |
| **Sun & Moon** | **2017-02-03** | **1.927** | **121** | **6%** |
| Sword & Shield | 2019-11-15 | 1.857 | 1.774 | 96% |
| Scarlet & Violet | 2023-03-31 | 2.158 | 2.158 | 100% |
| Mega Evolution | 2025-09-25 | 707 | 621 | 88% |

Black & White, XY e Sun & Moon são três eras consecutivas, de 2011 a 2019, em
que a reverse holo é das mais comuns que existem. Zero é dado faltando, não
ausência real. Duas provas independentes:

1. **POP (4%) e Trainer kits (0%) também dão zero, e ali está correto** —
   esses produtos realmente não têm reverse holo. O método distingue um caso
   do outro, então o zero de BW/XY/SM não é artefato da medição.
2. **`sm3` Burning Shadows tem 116 de 117 preenchidas**, na mesma era em que
   todas as outras coleções dão zero. Se a era não tivesse reverse holo, `sm3`
   também não teria.

Cruzamento com a pokemontcg.io reforça: numa amostra de 40 cartas que o TCGdex
diz não ter reverse, 14 tinham dado de preço na outra base e **5 delas têm
preço de `reverseHolofoil`** — todas Common/Uncommon de 2006 a 2015. Um Common
de Black & White sem reverse holo não é dúvida de domínio, é erro de dado.

### A consequência, e o que foi feito

Num masterset, **slot faltando é pior que slot sobrando**: slot a mais custa
uma decisão de curadoria, slot a menos faz o colecionador nunca descobrir que a
carta existe. São ~4.400 cartas sem o slot de RF.

A `variant_policy` ganhou duas capacidades em `0008_politica_obriga.sql`:

| Coluna | Efeito |
| --- | --- |
| `obriga` | gera o slot mesmo quando a API não lista a variante |
| `set_regex` | casa com `card_set.tcgdex_id`, para excluir coleções de promo |

Com três linhas de política — uma por era quebrada — foram criados **8.828
slots** que faltavam: Sun & Moon 3.612, XY 2.738, Black & White 2.478.

Todos nascem `unknown`, com `created_by = 'inferred'` e a razão em `notes`.
Nunca nascem `confirmed`, nem quando há scan em português: inferência é
hipótese, não prova. A tela mostra a etiqueta **inferido** e tem filtro próprio
para eles.

Se o TCGdex preencher o dado, a limpeza é um `delete from card_variant where
created_by = 'inferred'` seguido de um `slots --all`. E é mais um candidato a
contribuição de volta ao projeto, que é open source.

### O que ficou em aberto

A era EX está em 53% — nem claramente boa nem claramente quebrada. Não entrou
na regra porque não consigo distinguir, só pelo número, quais coleções da era
realmente têm RF e quais são dado faltando. Fica para a curadoria.
