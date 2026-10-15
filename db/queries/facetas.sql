-- Os valores que ainda existem no recorte, com quantos slots cada um.
--
-- Chip que não filtra nada é pior que chip nenhum, e chip que some quando
-- você clica nele é pior ainda. Por isso cada faceta é contada com todos os
-- outros filtros aplicados **menos o dela**: escolher 'XY' não faz as outras
-- eras sumirem da lista, e dá para trocar de era sem antes limpar o recorte.
--
-- É uma consulta só. As flags ok_* calculam, por slot, quais filtros de
-- refino ele atende; o `count(*) filter (where ...)` de cada faceta usa as
-- flags das outras. Seis requisições viram uma.
--
-- Escopo (vale para todas as facetas): idioma, coleção, espécie.
-- Refino (cada faceta ignora a si mesma): região, era, ano, raridade, tipo.
--
-- Parâmetros: os mesmos de binder.sql.

with base as (
  select
    v.id,
    c.id                             as card_id,
    cs.serie_name                    as era,
    extract(year from cs.release_date)::int as ano,
    coalesce(c.rarity_pt, c.rarity_en)      as raridade,
    v.kind::text                     as kind,
    (%(region)s::text is null or exists (
       select 1 from card_species csp join species s on s.id = csp.species_id
       where csp.card_id = c.id and s.region = %(region)s))      as ok_regiao,
    (%(serie)s::text is null or cs.serie_name = %(serie)s)       as ok_era,
    (%(ano_de)s::int is null or extract(year from cs.release_date) >= %(ano_de)s)
      and (%(ano_ate)s::int is null or extract(year from cs.release_date) <= %(ano_ate)s)
                                                                 as ok_ano,
    (%(rarities)s::text[] is null
       or coalesce(c.rarity_pt, c.rarity_en) = any (%(rarities)s::text[])) as ok_raridade,
    (%(kinds)s::variant_kind[] is null
       or v.kind = any (%(kinds)s::variant_kind[]))              as ok_tipo
  from card_variant v
  join card c      on c.id = v.card_id
  join card_set cs on cs.id = c.set_id
  where (%(set_id)s::text is null or cs.tcgdex_id = %(set_id)s)
    and (%(species)s::text is null or exists (
          select 1 from card_species csp join species s on s.id = csp.species_id
          where csp.card_id = c.id and s.slug = %(species)s))
    and (%(languages)s::lang[] is null or v.language = any (%(languages)s::lang[]))
    and (%(include_absent)s or v.exists_state <> 'absent')
    and (%(include_digital)s or not cs.is_digital)
)
-- `ordem` é o que cada dimensão usa para se ordenar na tela: era e ano são
-- linha do tempo, região segue a Pokédex, e o resto ordena por contagem.
select 'era' as dim, era as valor, count(*) as n, min(ano) as ordem
  from base where ok_regiao and ok_ano and ok_raridade and ok_tipo
   and era is not null
 group by 1, 2

union all
select 'ano', ano::text, count(*), min(ano)
  from base where ok_regiao and ok_era and ok_raridade and ok_tipo
   and ano is not null
 group by 1, 2

union all
select 'raridade', raridade, count(*), null::int
  from base where ok_regiao and ok_era and ok_ano and ok_tipo
   and raridade is not null
 group by 1, 2

union all
select 'tipo', kind, count(*), null::int
  from base where ok_regiao and ok_era and ok_ano and ok_raridade
 group by 1, 2

-- A região é da espécie, então uma carta com duas espécies de regiões
-- diferentes conta nas duas. Daí o distinct: o slot é um só.
union all
select 'regiao', s.region, count(distinct b.id), min(s.dex_number)
  from base b
  join card_species csp on csp.card_id = b.card_id
  join species s        on s.id = csp.species_id
 where b.ok_era and b.ok_ano and b.ok_raridade and b.ok_tipo
   and s.region is not null
 group by 1, 2

order by 1, 3 desc, 2;
