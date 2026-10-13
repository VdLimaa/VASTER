# O que o TCGdex entrega de fato

Medido em 2026-10-13 contra a API ao vivo, durante a implementação da F0.
Cada número aqui saiu de uma requisição, não de leitura de documentação.
Reproduzir: `python -m ingest coverage` depois de `sets` e `cards`.

Este documento existe porque cinco das premissas de
[arquitetura.md](arquitetura.md) não sobreviveram ao contato com a API. Nenhuma
delas invalida o projeto; duas melhoram bastante.

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
