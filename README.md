# VASTER — Masterset BR

Dado o nome de uma espécie, devolve todos os slots de variante que compõem o
masterset dela, com status de coleção, preço em BRL e export para impressão.

Arquitetura e roadmap: [docs/arquitetura.md](docs/arquitetura.md).
O que a API do TCGdex realmente entrega, medido:
[docs/achados-tcgdex.md](docs/achados-tcgdex.md) — leia antes de mexer na
ingestão.

**Estado: F0 fechada, catálogo completo.** 404 coleções, 36.517 cartas,
**as 1.025 espécies com masterset nos três idiomas**, 89.292 slots. Do banco
vazio ao catálogo inteiro em cerca de 7 minutos. A F1 (admin de curadoria) é o
próximo passo.

## Subir

```powershell
scripts\subir.bat                    # Windows
```

```bash
scripts/subir.sh                     # Linux e macOS
```

Confere Python e Node, sobe o Postgres, instala, enche o catálogo, compila a
tela e abre a aplicação em http://127.0.0.1:8000. Passo a passo, atalhos e o
caminho na mão: [Rodar em localhost](#rodar-em-localhost). Para só *ver* a
tela, sem instalar banco nenhum:
[Ver sem instalar nada](#ver-sem-instalar-nada).

## Montar o catálogo inteiro

```bash
python -m ingest species             # 1.025 espécies + nome japonês (~17 s)
python -m ingest sets                # 404 coleções (220 oeste + 184 Japão)
python -m ingest cards               # 36.517 cartas em 3 requisições
python -m ingest details --all --bulk   # variants de tudo (~6 min)
python -m ingest links --all            # 30.672 vínculos carta↔espécie
python -m ingest slots --all            # 89.292 slots
```

`details --all --bulk` é o passo que torna isso viável. O catálogo ocidental
inteiro sai de **uma requisição GraphQL** em 5 segundos, no lugar de ~37.000
requisições REST. O japonês não tem equivalente — o GraphQL do TCGdex não tem
filtro de idioma — e custa 12.781 requisições, uns 6 minutos, gravadas em lotes
de 400 para a execução ser retomável.

## Acompanhar coleção nova

```bash
python -m ingest update
```

Pega só o que entrou desde a última execução, em ~50 s, e diz o que mudou pelo
nome. Todos os passos são idempotentes, e o caro — `details` carta a carta no
catálogo japonês — só toca carta sem `details_at`, então uma coleção japonesa
nova custa ~100 requisições em vez de 12.781. É o comando que o scheduler da F2
vai chamar; até lá, um `cron` semanal resolve.

Testado apagando a coleção `M6` do banco e rodando `update`: ela voltou sozinha
com as 113 cartas, 87 vínculos de espécie e 113 slots, e o relatório disse
`coleção nova: M6 [jp] ストームエメラルダ (2026-07-31)`.

**Com que atraso o TCGdex recebe lançamento novo?** Medido em 2026-10-14:

| Coleção | Lançada | Dias | Em inglês | Em português | Com scan PT |
| --- | --- | ---: | ---: | ---: | ---: |
| `30th` Celebração de 30 Anos | 2026-09-16 | 28 | 158/158 | 2 | 2 |
| `30th-c` Coleção Clássica | 2026-09-16 | 28 | 30/30 | 30 | 0 |
| `me05` Escuridão Absoluta | 2026-07-17 | 89 | 120/120 | 120 | 120 |
| `me04` Caos Ascendente | 2026-05-22 | 145 | 122/122 | 122 | 122 |

O inglês entra praticamente junto com o lançamento. O português chega depois, em
semanas a poucos meses. Scan japonês de coleção recente não chega: `M6` (75
dias), `M5` (145), `M4` (215) e `M3` (264) estão todos com zero scans.

Depois disso, qualquer espécie responde:

```bash
python -m ingest gate      --species pikachu    # 635 slots em 139 coleções
python -m ingest masterset --species charizard --lang ja
python web/prototipo/gerar.py --species mewtwo
```

`sets`, `cards`, `details` e `slots` aceitam `--region west|jp|all`, padrão
`all`. `species` aceita `--sem-ja` para pular as 1.025 requisições dos nomes
japoneses — mas sem eles 434 cartas japonesas sem `dexId` ficam fora de todo
masterset.

O `gate` sai com código 1 se falhar, então serve em CI. Para Sableye: 27
coleções físicas do oeste, 13 japonesas, 0 duplicatas e 8 cartas
`Mega Sableye & Tyranitar GX` — 4 ocidentais e 4 japonesas — ligadas a
`sableye` e `tyranitar`.

Para ver o masterset:

```bash
python -m ingest masterset --species sableye
python -m ingest masterset --species sableye --lang pt      # só português
python -m ingest masterset --species sableye --lang pt,en   # ocidentais
python -m ingest masterset --species sableye --lang ja      # só japonesas
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
| `species` | popula `species` da PokéAPI, com nome japonês | 1.026 requisições |
| `sets` | sets, séries, datas e overlay de nome em PT | ~430 requisições |
| `cards` | todas as cartas dos três idiomas | 3 requisições |
| `details --bulk` | o mesmo via GraphQL, só no oeste | **1 requisição** |
| `details` | `variants`, `rarity`, `category`, `dexId` | 1 por carta |
| `links` | preenche `card_species` a partir do `dexId` | — |
| `slots` | gera `card_variant` aplicando a política por era | — |
| `update` | só o delta desde a última execução | ~50 s |
| `refresh` | recalcula a materialized view `price_current` | — |
| `saude` | contagens do catálogo, uma por linha | — |
| `ping` | espera o Postgres aceitar conexão (`--espera 90`) | — |
| `snapshot` | grava os recortes prontos em `web/app/public/demo.json` | — |
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
| Reverse holo em coleção de promos | nega |
| Reverse holo em set anterior a 2002-05-24 | nega |
| Reverse holo em Ultra Rara, Full Art, Rainbow e secretas | nega |
| Reverse holo em Black & White, XY e Sun & Moon | **obriga** |
| Reverse holo da era EX | anota: a RF traz o nome da coleção estampado |

**Obrigar existe porque a API falha.** A flag `reverse` do TCGdex está ausente
em três eras consecutivas: Black & White 0%, XY 0% e Sun & Moon 6%, contra
92-100% nas eras vizinhas. Não é ausência real — `sm3` Burning Shadows, da
mesma era, tem 116 de 117 preenchidas. São 8.828 slots que faltavam no
masterset, e num masterset slot faltando é pior que slot sobrando: o
colecionador nunca descobre que a carta existe. Medição completa em
`docs/achados-tcgdex.md`, seção 15.

Slot obrigado nasce `unknown` com `created_by = 'inferred'` e a razão em
`notes`, nunca `confirmed` — inferência é hipótese, não prova.

**Negar não é descartar.** `kinds_da_carta` só produz variante que a API afirma
existir, então toda negação é uma discordância entre a API e a regra — e sumir
com ela em silêncio esconde justamente o caso que alguém precisa olhar. O slot
negado nasce `unlikely` com a razão em `notes`. No catálogo inteiro são 22.

Uma regra já foi removida por estar errada: eu afirmei que o japonês não tem
reverse holo a partir de uma amostra de 54 cartas, e o catálogo completo mostrou
1.008 cartas japonesas com reverse, todas em high-class packs. Está em
`docs/achados-tcgdex.md`, seção 11. A lição virou critério: regra por era só
entra quando a amostra cobre a variação que ela pretende descrever.

## Japonês é outro catálogo

Não é tradução. São 184 coleções com ids próprios (`PMCG1`, `VS1`, `S6K`), e
id de carta inglesa dá 404 em `ja`. O nome da carta também é japonês, e para
casar espécie por nome o `species.name_ja` é obrigatório: sem ele, 434 cartas
japonesas sem `dexId` ficam fora de todo masterset. Quatro ids colidem entre os dois catálogos
sendo coleções **diferentes** — `neo1` é *Neo Genesis* em inglês e
金、銀、新世界へ... em japonês — então a chave de `card_set` e de `card` é
`(tcgdex_id, region)`.

Uma carta japonesa não é o slot `ja` de uma carta inglesa: é outra carta, em
outra coleção. Idioma continua sendo atributo do slot, mas *quais* idiomas um
slot pode ter vem de `card_set.region`:

| Região | Idiomas |
| --- | --- |
| `west` | `en`, `pt` |
| `jp` | `ja` |

Japonês não tem reverse holo — medido, 0 em 54 cartas amostradas de três eras —
e isso é uma linha de `variant_policy` com `region = 'jp'`.

## Auto-confirmação em lote

Quando o TCGdex tem a carta naquele idioma, o gerador promove **só o slot
principal** para `confirmed`, com a URL do scan em `source_url` e registro em
`curation_event` com ator `generator:tcgdex-<idioma>`.

Isso é a evidência de nível 3 da hierarquia do documento de arquitetura, feita
em lote em vez de uma por uma. Em Sableye são 42 dos 115 slots resolvidos sem
trabalho humano: 21 em português e 21 em japonês.

Não promove a reverse holo: ter o scan da carta em português não prova nada
sobre a RF em português. Para desligar, `slots --no-auto-confirm`. Para
reverter o que já entrou:

```sql
update card_variant v set exists_state = 'unknown', source_url = null,
                          checked_at = null
from curation_event e
where e.variant_id = v.id and e.actor like 'generator:tcgdex-%';
```

## Sem foto não é a mesma coisa que fora do catálogo

A consulta do masterset devolve dois sinais por slot, e a tela mostra cada um
com a sua etiqueta:

| Sinal | Significado |
| --- | --- |
| `no_catalogo = false` | o TCGdex não tem registro nenhum da carta naquele idioma |
| `no_catalogo = true, has_scan = false` | a carta está no catálogo, mas ninguém publicou foto |

Para a curadoria a diferença é tudo. **Sem foto** é um slot que já dá para
confirmar, porque o registro é a evidência. **Fora do catálogo** é um slot que
ninguém decide sem a carta na mão — e não prova que a carta não existe, já que
o TCGdex não tem uma única carta em português antes de 2011.

## Rodar em localhost

Um comando faz tudo — confere Python e Node, sobe o Postgres, instala, enche o
catálogo, compila a tela e sobe a aplicação:

```powershell
scripts\subir.bat                    # Windows
```

```bash
scripts/subir.sh                     # Linux e macOS
```

Os dois aceitam os mesmos atalhos:

| Atalho | Para quê |
| --- | --- |
| `-Rapido` / `--rapido` | só o catálogo ocidental (inglês e português), ~1 min no lugar de ~7 |
| `-Dev` / `--dev` | dois processos, com recarga instantânea do frontend |
| `-SoTela` / `--so-tela` | pula a ingestão, para quando o banco já está cheio |
| `-Porta 9000` / `--porta 9000` | troca a porta da API |

O script é idempotente: rodar de novo com o banco cheio chama
`python -m ingest update`, que pega só o que entrou desde a última vez.

**No Windows**, `scripts\subir.bat` existe porque arquivo que saiu de um `.zip`
baixado vem marcado pelo Windows e o PowerShell recusa rodar. O `.bat` chama o
`.ps1` com `-ExecutionPolicy Bypass`, que resolve as duas coisas. Dá no mesmo
chamar direto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\subir.ps1 -Rapido
```

Precisa de **Python 3.12+**, **Node.js** e um **Postgres 16**. Se faltar, o
script diz qual e com que comando instalar. O Postgres sai do
`docker compose up -d db`; para usar um que você já tenha, aponte a variável e
o script respeita:

```powershell
$env:VASTER_DB_DSN = "postgresql://usuario:senha@localhost:5432/vaster"
```

### Na mão

```bash
docker compose up -d db
cp .env.example .env                 # opcional: os padrões já batem com o compose
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,api]'

python -m ingest migrate
python -m ingest species && python -m ingest sets && python -m ingest cards
python -m ingest details --all --bulk
python -m ingest links --all && python -m ingest slots --all
```

No Windows as três linhas que mudam são `.venv\Scripts\activate`,
`copy .env.example .env` e `py -m venv .venv`.

Leva ~7 minutos. Depois, `python -m ingest update` pega só o que entrou de novo.

Para subir a aplicação, **um processo**:

```bash
cd web/app && npm install && npm run build && cd ../..
uvicorn api.main:app --reload
```

Abre em http://127.0.0.1:8000 — o FastAPI serve a API e a tela compilada.

Para mexer no frontend, **dois processos** com recarga instantânea:

```bash
uvicorn api.main:app --reload          # terminal 1 — API em :8000
cd web/app && npm run dev              # terminal 2 — tela em :5173
```

O Vite repassa `/api` para o FastAPI, então basta abrir
http://127.0.0.1:5173.

**O `package.json` fica em `web/app`, não na raiz.** `npm run dev` na raiz
responde `ENOENT: no such file or directory, open .../package.json` — é o
diretório, não a instalação.

### Stack do frontend

React 19 + TypeScript + Vite, sem framework de UI e sem dependência além do
React — o CSS é próprio, com os mesmos tokens do resto do projeto.

O documento de arquitetura escolhe Next.js, por causa do SSR para a F5 (página
pública por espécie, SEO). Isto aqui é Vite porque a F5 está longe e um
processo a menos vale mais agora. Quando a F5 chegar, a migração é direta: os
componentes em `web/app/src/componentes/` não dependem do roteador.

### A tela

Monta o fichário de **qualquer recorte**, combinando sete filtros:

| Filtro | Exemplo |
| --- | --- |
| Idioma | português (padrão), inglês, japonês |
| **Pokémon** | busca por nome em inglês, por nome japonês ou pelo número: `charizard`, `リザードン`, `6` |
| Região | Kanto, Johto, Hoenn… — é da **espécie**, não da coleção, então um Pikachu numa coleção de Paldea continua sendo de Kanto |
| **Era** | Base, Neo, EX, Black & White, Scarlet & Violet… — e as japonesas, com os nomes delas |
| **Ano** | de 1996 a hoje, pela data de lançamento da coleção |
| **Raridade** | Comum, Incomum, Rara, Illustration rare, Ultra Rare, Secret Rare… |
| Tipo | Normal, Reverse holo (RF), Holo, Arte especial / full art, Rainbow e gold, Shiny, Promo, 1ª edição |
| Coleção | busca por nome ou id: `151`, `Céus em Evolução`, `sv03.5` |

**Raridade não é tipo.** "Illustration Rare" é a raridade impressa na carta;
"arte especial" é o tipo de slot. A mesma carta pode ser Ultra Rare *e* ter
reverse holo — são dois eixos, e por isso dois filtros que se combinam.

Dois recortes para ver o que isso dá:

* *Pokémon de Kanto da coleção 151, em full art, em português* — **21 slots**,
  todos confirmados pelo catálogo: Bulbasaur 169/165, Ivysaur, Charmander,
  Squirtle, Pikachu, Nidoking e as outras illustration rares.
* *todo Pikachu em português, de 1999 a 2005* — **38 slots**, e os 38 estão
  fora do catálogo, porque o TCGdex não tem carta em português antes de 2011.
  O fichário mostra o que falta provar, não só o que já está provado.

#### Os filtros se corrigem sozinhos

Cada filtro mostra só o que ainda existe no recorte, com a contagem junto:
escolher a era Base deixa a raridade com `Rara (7)` e mais nada, porque é só o
que sobrou. Chip que não filtra nada é pior que chip nenhum.

Com uma ressalva que importa: **cada lista é contada ignorando o próprio
filtro**. Escolher a era XY não faz as outras eras sumirem da lista — senão
trocar de era exigiria limpar o recorte antes. Isso é uma consulta só, com
contagem condicional por dimensão: `db/queries/facetas.sql`.

Cada slot tem **Tenho / Quero / Falta**, salvos no navegador — sem login, como
no fichário de verdade. "Tenho" mostra a carta colorida, "Falta" em cinza.

O fichário abre em **folha dupla**, como o de verdade: a capa sozinha na
primeira abertura, e daí em diante as páginas aos pares. A grade vai de
**2x2 a 5x4**, e o botão **Imprimir o fichário** troca a visão para todas as
páginas em sequência, uma por folha A4, sem os controles.

A impressão precisa de um cuidado que não é óbvio: `window.print()` é síncrono,
então trocar o estado dentro de `beforeprint` não dá tempo do React repintar — o
diálogo capturaria só a abertura visível. O caminho é marcar o estado, deixar
pintar, e só então abrir o diálogo. Conferido: na tela são capa + 1 página; no
instante da impressão são as 3 páginas com os 21 slots, sem a capa.

Esse mesmo HTML é o que o WeasyPrint vai consumir no PDF da F2 — a folha de
estilo de impressão já existe.

Os rótulos de tipo são os que o colecionador usa, não os do enum: ninguém
procura `alt_art`, procura *arte especial*. A tradução fica em
`api/consultas.py`; o enum continua sendo a verdade no banco.

### Rotas

| Rota | Devolve |
| --- | --- |
| `GET /api/saude` | contagens do catálogo |
| `GET /api/idiomas` | os três idiomas |
| `GET /api/especies?busca=` | espécies por nome, nome japonês ou número da Pokédex |
| `GET /api/facetas?<recorte>` | era, ano, raridade, tipo e região que existem no recorte, com contagem |
| `GET /api/colecoes?<recorte>&busca=` | coleções com slots no recorte |
| `GET /api/binder?<recorte>` | os slots, com resumo de progresso |

`<recorte>` é o mesmo conjunto de parâmetros nas três últimas:
`idioma`, `colecao`, `regiao`, `especie`, `era`, `ano_de`, `ano_ate`,
`raridade`, `tipo`. Em Python é uma dataclass só — `consultas.Recorte` — que
vira dependência do FastAPI. Filtro novo entra num lugar e as três rotas
enxergam.

`/api/binder` exige **coleção, região, espécie ou era**. Sem nenhum dos quatro
seriam os 89 mil slots do catálogo, o que derruba a tela e não serve para
ninguém.

## Ver sem instalar nada

A tela abre sozinha, sem Postgres, sem Python e sem ingestão:

```bash
cd web/app && npm install && npm run dev
```

Quando a API não responde, a tela cai no `web/app/public/demo.json` e entra em
**modo demonstração**: no lugar dos filtros, oito recortes já calculados, com
um aviso dizendo que é isso que está no ar. Fichário, grade, marcas e
impressão funcionam igual — o que muda é só de onde vem o dado.

| Recorte | Mostra |
| --- | --- |
| Charizard · masterset | a premissa do projeto: 135 slots em 53 coleções |
| 151 · Kanto · arte especial | o recorte que motivou o projeto: 21 slots |
| 151 · masterset inteiro | 362 slots, a coleção toda em português |
| Escuridão Absoluta | coleção recente, 100% catalogada e com scan |
| 30 Anos · Coleção Clássica | as 30 estão no catálogo e **nenhuma tem foto** |
| Base Set (1999) | **todo slot fora do catálogo** — é o que a curadoria resolve |
| 151 · em inglês | a mesma coleção no catálogo inglês |
| 151 · em japonês | `SV2a`, que é outra coleção, não uma tradução |

O console mostra um `502` em `/api/saude` — é a tela perguntando se a API está
no ar antes de cair no arquivo. Em modo demonstração é esperado.

O arquivo sai de `python -m ingest snapshot` e está versionado, então vale
para quem baixou o `.zip` e para hospedagem estática — a Vercel não tem
Postgres. Regerar depois de mexer no catálogo:

```bash
python -m ingest snapshot            # ~1,1 MB em web/app/public/demo.json
```

Os recortes moram em `api/snapshot.py` e o payload de cada um sai da **mesma
função** que a rota `/api/binder` usa, então os dois não têm como divergir.

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

Os slots marcados **fora do catálogo** e **sem foto** são o que a tela tem de
mais útil para quem vai curar. Ver a seção acima sobre a diferença entre os
dois.

## Desenvolvimento

```bash
pytest          # 95 testes, sem rede e sem banco
ruff check .

VASTER_TEST_DSN=postgresql://vaster:vaster@localhost:5432/vaster pytest
#               106 testes: os 11 que faltam conferem o SQL contra o Postgres

cd web/app && npx tsc -b && npx oxlint
```

Os testes usam fixtures capturadas da API real, em `tests/fixtures/`, não
valores inventados. Dois casos foram escritos errado antes de bater com o dado
de verdade: `sm11-126` tem `reverse: false` e o Charizard do Base Set tem
`normal: false`, porque nunca existiu em versão não-holo.

Para rodar a ingestão sem Docker, aponte `VASTER_DB_DSN` para qualquer
Postgres 16.
