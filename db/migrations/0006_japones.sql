-- Japonês não é tradução, é outro catálogo.
--
-- Medido em 2026-10-13 contra a API (ver docs/achados-tcgdex.md):
--   * /ja/sets tem 184 coleções com ids próprios (PMCG1, VS1, web1, S6K)
--   * id de carta inglesa dá 404 em /ja: swsh7-67, sm11-126 e base1-4
--   * 4 ids colidem entre os catálogos sendo coleções DIFERENTES: neo1 é
--     'Neo Genesis' (111 cartas) em inglês e '金、銀、新世界へ...' (96) em
--     japonês. Com unique(tcgdex_id) a ingestão do japonês sobrescreveria a
--     coleção inglesa, então a chave passa a ser (tcgdex_id, region)
--   * carta japonesa não tem nome em inglês no TCGdex, só o japonês
--   * japonês não tem reverse holo: 0 em 54 cartas amostradas de três eras
--
-- A consequência de modelo: uma carta japonesa não é o slot 'ja' de uma carta
-- inglesa, é outra carta, em outra coleção. O que o enum lang descreve
-- continua valendo — idioma é atributo do slot — mas quais idiomas um slot
-- pode ter passa a depender da região da coleção.

alter table card_set add column region text not null default 'west'
  check (region in ('west', 'jp'));

alter table card_set drop constraint card_set_tcgdex_id_key;
alter table card_set add constraint card_set_tcgdex_id_region_key
  unique (tcgdex_id, region);

alter table card add column region text not null default 'west'
  check (region in ('west', 'jp'));

alter table card drop constraint card_tcgdex_id_key;
alter table card add constraint card_tcgdex_id_region_key
  unique (tcgdex_id, region);

-- Nome e scan em japonês. rarity continua em rarity_en de propósito: a API
-- devolve a raridade em inglês ('Common') mesmo no catálogo japonês.
--
-- name_en deixa de ser obrigatório: /en/cards/SM7b-016 e /en/cards/S6K-028
-- devolvem 404, então uma carta japonesa não tem nome em inglês para guardar.
alter table card alter column name_en drop not null;

alter table card add column name_ja      text;
alter table card add column image_url_ja text;
alter table card add column has_ja       boolean not null default false;

create index on card_set (region);
create index on card (region);

-- A política passa a poder falar por região. Sem isso, uma regra escrita para
-- a era 'e' do oeste casaria com a série 'e' japonesa, que é outra coisa.
alter table variant_policy add column region text
  check (region in ('west', 'jp'));

insert into variant_policy (region, kind, allowed, reason, priority) values
  ('jp', 'reverse_holo', false,
   'O card game japonês não imprime reverse holo. Medido: 0 de 54 cartas '
   'amostradas em S6K, SM7b e PMCG1 têm a flag reverse.',
   110);
