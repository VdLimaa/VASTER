-- ZONA 2: curadoria. Seu dado, editável, nunca sobrescrito pelo job.

create type variant_kind as enum (
  'regular','reverse_holo','holo','full_art','alt_art',
  'rainbow','gold','shiny','promo','first_edition'
);

-- 'pt' é o idioma do card game físico brasileiro no TCGdex.
-- 'pt-br' na API é Pokémon TCG Pocket; ver docs/achados-tcgdex.md.
create type lang as enum ('pt','en','ja');

create type existence as enum ('confirmed','unlikely','absent','unknown');

create table card_variant (
  id            bigserial primary key,
  card_id       bigint not null references card(id) on delete cascade,
  kind          variant_kind not null,
  language      lang not null,
  exists_state  existence not null default 'unknown',
  source_url    text,                       -- prova da curadoria
  checked_at    timestamptz,
  notes         text,
  -- variantId do TCGdex, quando o slot casa com uma entrada de
  -- variants_detailed. É o que liga o slot ao preço da API.
  api_variant_id text,
  -- quem criou o slot: o gerador ou uma pessoa
  created_by    text not null default 'generator'
                check (created_by in ('generator','manual')),
  created_at    timestamptz not null default now(),
  unique (card_id, kind, language)
);

create index on card_variant (card_id);
create index on card_variant (exists_state) where exists_state = 'unknown';

-- Promoção de slot sempre exige prova. Em 'unlikely' o relato de fórum basta,
-- mas confirmar ou negar sem URL não passa.
alter table card_variant add constraint card_variant_prova_obrigatoria
  check (exists_state in ('unknown','unlikely') or source_url is not null);

-- Trilha de auditoria: o risco "você é o único curador" só é mitigado se outra
-- pessoa conseguir reconstruir por que um slot virou confirmed.
create table curation_event (
  id          bigserial primary key,
  variant_id  bigint not null references card_variant(id) on delete cascade,
  from_state  existence,
  to_state    existence not null,
  source_url  text,
  actor       text not null default 'manual',
  notes       text,
  created_at  timestamptz not null default now()
);

create index on curation_event (variant_id, created_at desc);
