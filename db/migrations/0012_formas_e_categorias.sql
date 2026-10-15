-- Mais eixos de recorte: o que a carta É, e qual forma do Pokémon ela mostra.
--
-- Tudo o que o GraphQL do TCGdex já devolvia e a ingestão descartava: estágio,
-- sufixo (EX, GX, V, VMAX), subtipo de treinador (Item, Apoiador, Estádio,
-- Ferramenta), tipo de energia da carta e marca de regulamento. Uma requisição
-- traz o catálogo ocidental inteiro, então não custa nada e vira seis filtros.
--
-- `forma` é diferente: a API NÃO tem. O dexId de 'M Charizard EX' é 6, igual
-- ao do Charizard comum, e 'Exeggutor de Alola' é 103 igual ao de Kanto. A
-- forma só existe no nome da carta, e por isso é inferida — ver ingest/formas.py.

alter table card
  add column if not exists stage_en        text,
  add column if not exists suffix_en       text,
  add column if not exists trainer_type_en text,
  add column if not exists energy_type_en  text,
  add column if not exists types_en        text[],
  add column if not exists regulation_mark text,
  add column if not exists forma           text;

create index if not exists card_forma_idx     on card (forma) where forma is not null;
create index if not exists card_categoria_idx on card (category_en);
create index if not exists card_types_idx     on card using gin (types_en);

-- O sprite da Pokédex. Hotlink do repositório da PokéAPI, como as cartas são
-- hotlink do CDN do TCGdex: nada de imagem rehospedada neste projeto.
alter table species add column if not exists sprite_url text;

-- As formas de cada espécie, como a PokéAPI as lista em `varieties`. É a
-- Pokédex de megas e a de formas regionais — a lista de ESCOLHAS da tela.
-- Não confundir com card.forma, que é o que cada carta mostra.
create table if not exists species_form (
  id          serial primary key,
  species_id  int  not null references species(id) on delete cascade,
  slug        text not null unique,        -- charizard-mega-x, raichu-alola
  kind        text not null,               -- mega | primal | regional | gigantamax | outra
  regiao      text,                        -- alola, galar, hisui, paldea
  name_en     text,
  sprite_url  text
);

create index if not exists species_form_kind_idx    on species_form (kind);
create index if not exists species_form_species_idx on species_form (species_id);
