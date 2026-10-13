-- ZONA 4: preço. Append-only, sempre datado.

create type price_source as enum
  ('mercadolivre','manual','tcgplayer','cardmarket','liga','comunidade');

create table price_observation (
  id          bigserial primary key,
  variant_id  bigint not null references card_variant(id) on delete cascade,
  source      price_source not null,
  price_brl   numeric(10,2) not null check (price_brl > 0),
  raw_amount  numeric(10,2),               -- valor na moeda original
  raw_ccy     char(3),
  fx_rate     numeric(10,4),
  listing_url text,
  -- 'tcgdex' quando o número chegou via variants_detailed em vez da
  -- API da própria casa. Confiança é a da origem, a rota muda a frescura.
  via         text,
  -- dedupe de coleta: o mesmo anúncio relido no mesmo dia não vira amostra nova
  dedupe_key  text,
  observed_at timestamptz not null default now()
);

create index on price_observation (variant_id, observed_at desc);
create unique index price_observation_dedupe
  on price_observation (variant_id, source, dedupe_key)
  where dedupe_key is not null;

-- Mediana dos últimos 90 dias. Recalculada no job, nunca em request.
create materialized view price_current as
select variant_id,
       percentile_cont(0.5) within group (order by price_brl) as median_brl,
       min(price_brl) as min_brl,
       max(price_brl) as max_brl,
       count(*) as sample_size,
       max(observed_at) as last_seen
from price_observation
where observed_at > now() - interval '90 days'
group by variant_id;

-- Obrigatório para REFRESH MATERIALIZED VIEW CONCURRENTLY: sem isso o refresh
-- trava a leitura do app enquanto roda.
create unique index price_current_variant on price_current (variant_id);
