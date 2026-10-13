# VASTER — Masterset BR

Dado o nome de uma espécie, devolve todos os slots de variante que compõem o
masterset dela, com status de coleção, preço em BRL e export para impressão.

Arquitetura e roadmap: [docs/arquitetura.md](docs/arquitetura.md).
O que a API do TCGdex realmente entrega, medido:
[docs/achados-tcgdex.md](docs/achados-tcgdex.md) — leia antes de mexer na
ingestão.

**Estado: F0 fechada.** Schema aplicado, ingestão funcionando contra a API ao
vivo e o gate do Sableye passando com dado real. A F1 (admin de curadoria) é o
próximo passo.

## Subir

```bash
docker compose up -d db
cp .env.example .env

uv venv && source .venv/bin/activate
uv pip install -e '.[dev]'

python -m ingest migrate
```

## Fechar o gate do Sableye

```bash
python -m ingest species                    # 1.025 espécies da PokéAPI
python -m ingest sets                       # 220 sets, ~5 s
python -m ingest cards                      # 23.736 cartas em 2 requisições, ~8 s
python -m ingest details --species sableye  # variants e dexId, 35 requisições
python -m ingest links   --species sableye  # preenche card_species
python -m ingest slots   --species sableye  # gera os 94 slots
python -m ingest gate    --species sableye  # verifica o gate da F0
```

O `gate` sai com código 1 se falhar, então serve em CI. Resultado esperado: 27
coleções físicas, 0 duplicatas, 4 cartas `Mega Sableye & Tyranitar GX` ligadas
a `sableye` e `tyranitar`.

Para ver o masterset:

```bash
python -m ingest masterset --species sableye
python -m ingest masterset --species sableye --lang pt      # só português
python -m ingest masterset --species sableye --lang pt,en   # os dois
python -m ingest masterset --species sableye --json         # payload da rota da F2
python -m ingest coverage                                   # cobertura PT por era
```

`--lang` usa o parâmetro `languages` de `db/queries/masterset.sql`, que é o
mesmo que a rota `GET /species/{slug}/masterset` vai expor. O idioma é atributo
do slot, não do app: o mesmo colecionador mistura PT e EN no mesmo fichário.

## Comandos

| Comando | O que faz | Custo |
| --- | --- | --- |
| `migrate` | aplica `db/migrations/*.sql` em ordem | — |
| `species` | popula `species` da PokéAPI | 1 requisição |
| `sets` | sets, séries, datas e overlay de nome em PT | ~245 requisições |
| `cards` | todas as cartas dos dois idiomas | 2 requisições |
| `details` | `variants`, `rarity`, `category`, `dexId` | 1 por carta |
| `links` | preenche `card_species` a partir do `dexId` | — |
| `slots` | gera `card_variant` aplicando a política por era | — |
| `refresh` | recalcula a materialized view `price_current` | — |
| `coverage` | relatório de cobertura PT por era | — |
| `gate` | verifica o gate da F0 de uma espécie | — |
| `masterset` | imprime o masterset de uma espécie | — |

`details` e `slots` aceitam `--species`, `--set` ou `--all`.

## Três coisas que não se mexe

**A curadoria nunca é sobrescrita.** Toda escrita em `card_variant` é
`on conflict do nothing`. Rodar `slots` de novo sobre uma espécie já curada
devolve `0 novos`. Há teste para isso e dá para conferir na mão: altere um
slot, rode `slots` outra vez, o slot continua como você deixou.

**Promover slot exige prova.** A constraint `card_variant_prova_obrigatoria`
rejeita `confirmed` ou `absent` sem `source_url`. `unlikely` passa sem URL, que
é o nível de confiança de relato de fórum. Toda promoção também gera linha em
`curation_event`, para outra pessoa poder auditar — é a mitigação do risco
"você é o único curador".

**Ausência na API não é prova de inexistência.** `pt_release` sobe para `'yes'`
quando o set aparece em `/pt/sets` e nunca desce para `'no'` sozinho. O TCGdex
não tem uma única carta em português antes de 2011, e o Brasil recebeu aquelas
coleções.

## Um slot é uma compra

Os slots saem só do objeto `variants` do TCGdex, que diz quais impressões
daquela carta existem. A raridade não cria slot — ela renomeia o slot base. Uma
Full Art tem `variants.normal = true` e *é* a Full Art: gerar `regular` +
`full_art` inventaria uma carta que não existe e furaria o "sem duplicata" do
gate.

As regras que a API não dá moram em `variant_policy`, tabela e não código,
porque cada regra é dado de curadoria e precisa ser auditável. Uma linha veta
(`allowed = false`) ou anota (`annotate = true`, e a razão vai para
`card_variant.notes`). As três que já existem:

| Regra | Efeito |
| --- | --- |
| Reverse holo em set anterior a 2002-05-24 | veta |
| Reverse holo em Ultra Rara, Full Art, Rainbow e secretas | veta |
| Reverse holo da era EX | anota: a RF traz o nome da coleção estampado |

## Auto-confirmação dos slots em português

Quando o TCGdex tem o scan em português de uma carta, o gerador promove **só o
slot principal em PT** para `confirmed`, com a URL do scan em `source_url` e
registro em `curation_event` com ator `generator:tcgdex-pt`.

Isso é a evidência de nível 3 da hierarquia do documento de arquitetura, feita
em lote em vez de uma por uma. Em Sableye são 21 dos 94 slots resolvidos sem
trabalho humano, e as 21 URLs foram conferidas uma a uma.

Não promove a reverse holo: ter o scan da carta em português não prova nada
sobre a RF em português. Para desligar, `slots --no-auto-confirm-pt`. Para
reverter o que já entrou:

```sql
update card_variant v set exists_state = 'unknown', source_url = null,
                          checked_at = null
from curation_event e
where e.variant_id = v.id and e.actor = 'generator:tcgdex-pt';
```

## Protótipo da tela

`web/prototipo/` é um HTML solto, sem build, para validar a interação antes de
escrever a tela em Next.js. Os chips de idioma, variante e situação funcionam, e
o scan troca junto com o idioma — que é o motivo de `card.image_url_pt` existir
separado de `card.image_url`.

```bash
python web/prototipo/gerar.py --species sableye
# abre web/prototipo/sableye.html no navegador
```

As imagens vêm por hotlink do CDN do TCGdex, `low.webp` na lista e `high.png` no
detalhe. Nenhum scan é guardado no repositório: imagem de carta é da TPCi.

Um slot em português sem `has_pt_scan` aparece marcado **sem scan PT** e cai na
imagem inglesa. É o sinal mais útil da tela para quem vai curar: significa que
ninguém tem foto da impressão brasileira daquela carta, e decidir o slot vai
exigir a carta na mão.

## Desenvolvimento

```bash
pytest          # 66 testes, sem rede
ruff check .
```

Os testes usam fixtures capturadas da API real, em `tests/fixtures/`, não
valores inventados. Dois casos foram escritos errado antes de bater com o dado
de verdade: `sm11-126` tem `reverse: false` e o Charizard do Base Set tem
`normal: false`, porque nunca existiu em versão não-holo.

Para rodar a ingestão sem Docker, aponte `VASTER_DB_DSN` para qualquer
Postgres 16.
