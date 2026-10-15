-- As espécies, para o campo de busca do masterset por Pokémon.
--
-- Casa por slug, por nome em inglês, por nome japonês e pelo número da Pokédex
-- — colecionador procura tanto por "charizard" quanto por "6".
--
-- Parâmetros:
--   %(busca)s   texto livre (null = todas)
--   %(region)s  região da espécie (null = todas)
--   %(limite)s  quantas devolver

select s.slug, s.dex_number, s.name_en, s.name_ja, s.region, s.generation
from species s
where (%(region)s::text is null or s.region = %(region)s)
  and (
    %(busca)s::text is null
    or s.slug      ilike '%%' || %(busca)s || '%%'
    or s.name_en   ilike '%%' || %(busca)s || '%%'
    or s.name_ja   like  '%%' || %(busca)s || '%%'
    or s.dex_number::text = %(busca)s
  )
order by
  -- quem começa com o que foi digitado vem primeiro: quem busca "char"
  -- quer Charmander antes de Rotom Wash
  (s.slug ilike %(busca)s || '%%') desc nulls last,
  s.dex_number
limit %(limite)s;
