-- ZONA 1: catálogo. Reescrito pelo job de ingestão, read-only para o app.
--
-- Desvios em relação a docs/arquitetura.md, todos justificados em
-- docs/achados-tcgdex.md:
--   * is_digital      — a série 'tcgp' (Pokémon TCG Pocket) são 2.480 cartas de
--                       app, não impressas. Masterset físico as exclui.
--   * image_url_pt    — o scan muda por idioma: a carta PT traz o nome e a
--                       coleção em português. Duas URLs, não uma.
--   * api_variants_detailed — o TCGdex devolve variants_detailed com variantId
--                       e preço Cardmarket/TCGplayer por variante. É a fonte da F3.
--   * serie_name      — evita um join só para exibir a era.

-- Controle das migrations. 'if not exists' porque o runner em ingest/db.py
-- cria esta tabela antes de ler o que já foi aplicado, e aplicar as
-- migrations na mão com psql também tem que funcionar.
create table if not exists schema_migration (
  filename   text primary key,
  applied_at timestamptz not null default now()
);

create table card_set (
  id             bigserial primary key,
  tcgdex_id      text unique not null,      -- 'swsh7'
  serie          text not null,             -- 'swsh'
  serie_name     text,                      -- 'Sword & Shield'
  serie_released date,                      -- lançamento da série, base das regras de era
  name_en        text not null,
  name_pt        text,
  release_date   date,
  count_official int,                       -- numeração impressa (ex. 203)
  count_total    int,                       -- com secretas
  symbol_url     text,
  logo_url       text,
  is_digital     boolean not null default false,
  pt_release     text not null default 'unknown'
                 check (pt_release in ('unknown','yes','no')),
  -- quantas cartas deste set o TCGdex tem em PT. 0 com pt_release='yes' é
  -- exatamente a fila de curadoria: o Brasil recebeu, a API não tem o dado.
  pt_card_count  int not null default 0,
  ingested_at    timestamptz not null default now()
);

create index on card_set (serie);
create index on card_set (release_date);

create table card (
  id            bigserial primary key,
  tcgdex_id     text unique not null,       -- 'swsh7-67', igual em todos os idiomas
  set_id        bigint not null references card_set(id) on delete cascade,
  number        text not null,              -- texto: '184', 'XY92', 'SV07'
  number_sort   int,                        -- para ordenar
  name_en       text not null,
  name_pt       text,
  rarity_en     text,
  rarity_pt     text,
  category_en   text,                       -- 'Pokemon' | 'Trainer' | 'Energy'
  illustrator   text,
  image_url     text,                       -- scan EN, sem sufixo de qualidade
  image_url_pt  text,                       -- scan PT, quando existe
  api_variants  jsonb,                      -- variants cru do TCGdex
  api_variants_detailed jsonb,              -- variants_detailed cru (variantId + preço)
  api_dex_id    int[],                      -- dexId cru, antes da resolução de espécie
  has_pt        boolean not null default false,
  details_at    timestamptz,                -- quando o GET /cards/{id} rodou
  unique (set_id, number)
);

create index on card (set_id);
create index on card (lower(name_en));
create index on card using gin (api_dex_id) where api_dex_id is not null;

create table species (
  id         bigserial primary key,
  dex_number int not null unique,           -- 302
  slug       text not null unique,          -- 'sableye'
  name_en    text not null,
  name_pt    text not null
);

-- N:N: uma carta pode ter duas espécies (Tag Team, Mega dupla)
-- resolved_by registra quem decidiu o vínculo, para a curadoria poder auditar.
create table card_species (
  card_id     bigint not null references card(id) on delete cascade,
  species_id  bigint not null references species(id) on delete cascade,
  resolved_by text not null default 'dex_id'
              check (resolved_by in ('dex_id','name_match','manual')),
  resolved_at timestamptz not null default now(),
  primary key (card_id, species_id)
);

create index on card_species (species_id);
