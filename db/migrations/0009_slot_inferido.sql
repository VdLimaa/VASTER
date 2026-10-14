-- Slot que nasceu de regra de era, não da API, precisa ser distinguível em
-- SQL — não só pelo texto de notes. Quando o TCGdex preencher o dado que
-- falta, a limpeza é um delete com where created_by = 'inferred'.
alter table card_variant drop constraint card_variant_created_by_check;
alter table card_variant add constraint card_variant_created_by_check
  check (created_by in ('generator', 'manual', 'inferred'));
