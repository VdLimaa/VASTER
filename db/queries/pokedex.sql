-- A Pokédex de escolha: as espécies, com sprite, para montar o masterset de
-- um Pokémon.
--
-- Com %(forma_kind)s, vira a Pokédex **daquela forma** — a de megas, a de
-- formas regionais, a de Gigantamax. Aí o sprite e o nome são os da forma, e
-- só entram as espécies que têm essa forma.
--
-- A contagem de slots é um agregado único sobre card_variant, não uma
-- subconsulta por espécie: 1.025 subconsultas correlacionadas levariam
-- segundos.
--
-- Parâmetros:
--   %(region)s      região da espécie (null = todas)
--   %(forma_kind)s  mega, regional, gigantamax, primal (null = a espécie em si)
--   %(card_forma)s  o valor de card.forma da forma pedida (mega, primal); nas
--                   regionais o valor varia por espécie e sai de species_form
--   %(card_estagio)s para a Pokédex de Gigantamax: o TCG não nomeia a forma, a
--                   carta dela é a VMAX — ver ingest/formas.py
--   %(languages)s   idiomas dos slots contados
--   %(busca)s       texto livre (null = todas)

with por_forma as (
  -- Slots por espécie E por forma, de uma vez. Com isto a contagem da
  -- Pokédex de megas sai sem uma subconsulta por espécie.
  select csp.species_id, c.forma, c.stage_en, count(*) as n
  from card_species csp
  join card c         on c.id = csp.card_id
  join card_variant v on v.card_id = c.id
  join card_set cs    on cs.id = c.set_id
  where v.exists_state <> 'absent'
    and not cs.is_digital
    and (%(languages)s::lang[] is null or v.language = any (%(languages)s::lang[]))
  group by 1, 2, 3
)
select
  s.dex_number,
  s.slug,
  coalesce(f.name_en, s.name_en)      as nome,
  s.name_en,
  s.name_ja,
  s.region,
  coalesce(f.sprite_url, s.sprite_url) as sprite_url,
  f.slug                               as forma_slug,
  f.kind                               as forma_kind,
  f.regiao                             as forma_regiao,
  coalesce(t.n, 0)                     as slots
from species s
left join lateral (
  select sf.slug, sf.kind, sf.regiao, sf.name_en, sf.sprite_url
  from species_form sf
  where sf.species_id = s.id and sf.kind = %(forma_kind)s
  order by sf.slug
  limit 1
) f on %(forma_kind)s::text is not null
left join lateral (
  -- A forma regional muda por espécie (Alola para um, Galar para outro),
  -- então o filtro vem de species_form, não de um parâmetro.
  select coalesce(sum(pf.n), 0)::int as n
  from por_forma pf
  where pf.species_id = s.id
    and (%(card_forma)s::text is null or pf.forma = %(card_forma)s)
    and (f.regiao is null or pf.forma = f.regiao)
    and (%(card_estagio)s::text is null or pf.stage_en = %(card_estagio)s)
) t on true
where (%(region)s::text is null or s.region = %(region)s)
  and (%(forma_kind)s::text is null or f.slug is not null)
  and (
    %(busca)s::text is null
    or s.slug    ilike '%%' || %(busca)s || '%%'
    or s.name_en ilike '%%' || %(busca)s || '%%'
    or s.name_ja like  '%%' || %(busca)s || '%%'
    or s.dex_number::text = %(busca)s
  )
order by s.dex_number;
