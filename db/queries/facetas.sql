-- Os valores que ainda existem no recorte, com quantos slots cada um.
--
-- Chip que não filtra nada é pior que chip nenhum, e chip que some quando
-- você clica nele é pior ainda. Por isso cada faceta é contada com todos os
-- outros filtros aplicados **menos o dela**: escolher 'XY' não faz as outras
-- eras sumirem da lista, e dá para trocar de era sem antes limpar o recorte.
--
-- O truque que mantém isso legível com dez dimensões é contar quantos filtros
-- de refino a linha NÃO atende (`faltas`). A faceta X mostra a linha quando
-- `faltas = 0` (atende tudo) ou quando a única falta é a dela própria.
--
-- É uma consulta só. Dez requisições viram uma.
--
-- Escopo (vale para todas as facetas): idioma, coleção, espécie.
-- Refino (cada faceta ignora a si mesma): região, era, ano, raridade,
-- variante, categoria, subtipo de treinador, tipo de energia, sufixo, estágio
-- e forma.
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
    c.category_en                    as categoria,
    c.trainer_type_en                as subtipo,
    c.types_en                       as tipos,
    c.suffix_en                      as sufixo,
    c.stage_en                       as estagio,
    c.forma                          as forma,
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
       or v.kind = any (%(kinds)s::variant_kind[]))              as ok_variante,
    (%(categoria)s::text is null or c.category_en = %(categoria)s)        as ok_categoria,
    (%(trainer_type)s::text is null or c.trainer_type_en = %(trainer_type)s) as ok_subtipo,
    (%(tipos)s::text[] is null or c.types_en && %(tipos)s::text[])        as ok_tipo,
    (%(sufixo)s::text is null or c.suffix_en = %(sufixo)s)                as ok_sufixo,
    (%(estagio)s::text is null or c.stage_en = %(estagio)s)               as ok_estagio,
    (%(forma)s::text is null or c.forma = %(forma)s)                      as ok_forma
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
),
contado as (
  select *,
    (not ok_regiao)::int + (not ok_era)::int + (not ok_ano)::int
      + (not ok_raridade)::int + (not ok_variante)::int + (not ok_categoria)::int
      + (not ok_subtipo)::int + (not ok_tipo)::int + (not ok_sufixo)::int
      + (not ok_estagio)::int + (not ok_forma)::int as faltas
  from base
)
-- `ordem` é o que cada dimensão usa para se ordenar na tela: era e ano são
-- linha do tempo, região segue a Pokédex, e o resto ordena por contagem.
select 'era' as dim, era as valor, count(*) as n, min(ano) as ordem
  from contado where (faltas = 0 or (faltas = 1 and not ok_era)) and era is not null
 group by 1, 2

union all
select 'ano', ano::text, count(*), min(ano)
  from contado where (faltas = 0 or (faltas = 1 and not ok_ano)) and ano is not null
 group by 1, 2

union all
select 'raridade', raridade, count(*), null::int
  from contado where (faltas = 0 or (faltas = 1 and not ok_raridade)) and raridade is not null
 group by 1, 2

union all
select 'variante', kind, count(*), null::int
  from contado where faltas = 0 or (faltas = 1 and not ok_variante)
 group by 1, 2

union all
select 'categoria', categoria, count(*), null::int
  from contado where (faltas = 0 or (faltas = 1 and not ok_categoria)) and categoria is not null
 group by 1, 2

union all
select 'subtipo', subtipo, count(*), null::int
  from contado where (faltas = 0 or (faltas = 1 and not ok_subtipo)) and subtipo is not null
 group by 1, 2

-- Uma carta pode ter dois tipos de energia, e aí conta nos dois.
union all
select 'tipo', t, count(distinct id), null::int
  from contado, unnest(tipos) t
 where faltas = 0 or (faltas = 1 and not ok_tipo)
 group by 1, 2

union all
select 'sufixo', sufixo, count(*), null::int
  from contado where (faltas = 0 or (faltas = 1 and not ok_sufixo)) and sufixo is not null
 group by 1, 2

union all
select 'estagio', estagio, count(*), null::int
  from contado where (faltas = 0 or (faltas = 1 and not ok_estagio)) and estagio is not null
 group by 1, 2

union all
select 'forma', forma, count(*), null::int
  from contado where (faltas = 0 or (faltas = 1 and not ok_forma)) and forma is not null
 group by 1, 2

-- A região é da espécie, então uma carta com duas espécies de regiões
-- diferentes conta nas duas. Daí o distinct: o slot é um só.
union all
select 'regiao', s.region, count(distinct b.id), min(s.dex_number)
  from contado b
  join card_species csp on csp.card_id = b.card_id
  join species s        on s.id = csp.species_id
 where (b.faltas = 0 or (b.faltas = 1 and not b.ok_regiao))
   and s.region is not null
 group by 1, 2

order by 1, 3 desc, 2;
