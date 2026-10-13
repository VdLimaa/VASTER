-- A consulta do masterset: species → card_species → card → card_variant,
-- com left join em collection_item e price_current.
--
-- Parâmetros:
--   %(slug)s            slug da espécie ('sableye')
--   %(user_id)s         usuário para o status; null traz tudo sem status
--   %(include_absent)s  true inclui slots exists_state='absent'
--   %(include_digital)s true inclui Pokémon TCG Pocket (cartas de app)
--   %(languages)s       array de idiomas ('{pt,en}'), null traz todos

select
  s.slug                        as species_slug,
  cs.serie                      as serie,
  cs.serie_name                 as serie_name,
  cs.release_date               as set_release,
  cs.tcgdex_id                  as set_id,
  coalesce(cs.name_pt, cs.name_en) as set_name,
  cs.count_official             as set_count_official,
  c.tcgdex_id                   as card_id,
  c.number                      as number,
  coalesce(c.name_pt, c.name_en) as card_name,
  c.name_en                     as card_name_en,
  coalesce(c.rarity_pt, c.rarity_en) as rarity,
  v.id                          as variant_id,
  v.kind                        as kind,
  v.language                    as language,
  v.exists_state                as exists_state,
  v.source_url                  as source_url,
  v.notes                       as notes,
  case v.language
    when 'pt' then coalesce(c.image_url_pt, c.image_url)
    else c.image_url
  end                           as image_url,
  -- false num slot em PT significa que ninguém tem foto da impressão
  -- brasileira. A imagem cai na inglesa, e a tela precisa dizer isso.
  (c.image_url_pt is not null)  as has_pt_scan,
  ci.status                     as status,
  ci.quantity                   as quantity,
  ci.condition                  as condition,
  ci.paid_brl                   as paid_brl,
  pc.median_brl                 as median_brl,
  pc.min_brl                    as min_brl,
  pc.max_brl                    as max_brl,
  pc.sample_size                as sample_size,
  pc.last_seen                  as price_last_seen
from species s
join card_species csp on csp.species_id = s.id
join card c           on c.id = csp.card_id
join card_set cs      on cs.id = c.set_id
join card_variant v   on v.card_id = c.id
left join collection_item ci
       on ci.variant_id = v.id
      and ci.user_id = %(user_id)s
left join price_current pc on pc.variant_id = v.id
where s.slug = %(slug)s
  and (%(include_absent)s or v.exists_state <> 'absent')
  and (%(include_digital)s or not cs.is_digital)
  -- O cast nos dois lados é obrigatório: sem ele o Postgres não infere o
  -- tipo do parâmetro em 'is null' e recusa a consulta com AmbiguousParameter.
  and (%(languages)s::lang[] is null or v.language = any (%(languages)s::lang[]))
order by cs.release_date nulls last, cs.tcgdex_id, c.number_sort nulls last,
         c.number, v.language, v.kind;
