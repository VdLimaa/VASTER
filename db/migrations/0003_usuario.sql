-- ZONA 3: usuário. app_user não está em docs/arquitetura.md, que já referencia
-- app_user(id) em collection_item sem definir a tabela.

create table app_user (
  id            bigserial primary key,
  email         text unique not null,
  password_hash text,                       -- null enquanto só houver OAuth
  display_name  text,
  is_curator    boolean not null default false,
  created_at    timestamptz not null default now()
);

create type slot_status as enum ('owned','wanted','skip');

create table collection_item (
  id            bigserial primary key,
  user_id       bigint not null references app_user(id) on delete cascade,
  variant_id    bigint not null references card_variant(id) on delete cascade,
  status        slot_status not null,
  quantity      int not null default 1 check (quantity >= 0),
  condition     text,                       -- NM, LP, MP...
  paid_brl      numeric(10,2) check (paid_brl is null or paid_brl >= 0),
  acquired_at   date,
  notes         text,
  updated_at    timestamptz not null default now(),
  unique (user_id, variant_id)
);

create index on collection_item (user_id, status);
