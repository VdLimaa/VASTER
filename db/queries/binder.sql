-- O binder: qualquer recorte de masterset.
--
-- Serve tanto "todo o Sableye" quanto "só os Pokémon de Kanto da coleção 151,
-- em full art, em português". Os filtros são todos opcionais e se combinam.
--
-- As espécies entram por subconsulta, não por join: uma Tag Team tem duas
-- espécies, e um join faria a carta aparecer duas vezes no fichário.
--
-- Parâmetros (null = sem filtro):
--   %(user_id)s          usuário, para trazer o status da coleção
--   %(set_id)s           tcgdex_id da coleção
--   %(region)s           região da espécie: kanto, johto, hoenn...
--   %(species)s          slug da espécie
--   %(serie)s            era/série: 'Scarlet & Violet'
--   %(rarities)s         raridades: {"Illustration rare"}
--   %(ano_de)s           ano de lançamento da coleção, mínimo
--   %(ano_ate)s          ano de lançamento da coleção, máximo
--   %(kinds)s            tipos de slot: {full_art,alt_art}
--   %(languages)s        idiomas: {pt}
--   %(status)s           status na coleção: {owned,wanted}
--   %(include_absent)s   inclui slots marcados como inexistentes
--   %(include_digital)s  inclui Pokémon TCG Pocket

select
  v.id                          as variant_id,
  cs.tcgdex_id                  as set_id,
  coalesce(cs.name_pt, cs.name_en) as set_name,
  cs.serie_name                 as serie_name,
  cs.release_date               as set_release,
  cs.count_official             as set_count_official,
  cs.region                     as catalogo,
  c.tcgdex_id                   as card_id,
  c.number                      as number,
  c.number_sort                 as number_sort,
  coalesce(c.name_pt, c.name_en, c.name_ja) as card_name,
  c.name_en                     as card_name_en,
  coalesce(c.rarity_pt, c.rarity_en) as rarity,
  c.rarity_en                   as rarity_en,
  v.kind                        as kind,
  v.language                    as language,
  v.exists_state                as exists_state,
  v.created_by                  as created_by,
  v.notes                       as notes,
  v.source_url                  as source_url,
  case v.language
    when 'pt' then coalesce(c.image_url_pt, c.image_url)
    when 'ja' then c.image_url_ja
    else c.image_url
  end                           as image_url,
  case v.language
    when 'pt' then c.image_url_pt is not null
    when 'ja' then c.image_url_ja is not null
    else c.image_url is not null
  end                           as has_scan,
  case v.language
    when 'pt' then c.has_pt
    when 'ja' then c.has_ja
    else true
  end                           as no_catalogo,
  (select array_agg(s2.slug order by s2.dex_number)
     from card_species csp2 join species s2 on s2.id = csp2.species_id
    where csp2.card_id = c.id) as especies,
  (select array_agg(distinct s2.region)
     from card_species csp2 join species s2 on s2.id = csp2.species_id
    where csp2.card_id = c.id and s2.region is not null) as regioes,
  ci.status                     as status,
  ci.quantity                   as quantity,
  ci.paid_brl                   as paid_brl
from card_variant v
join card c      on c.id = v.card_id
join card_set cs on cs.id = c.set_id
left join collection_item ci
       on ci.variant_id = v.id and ci.user_id = %(user_id)s
where (%(set_id)s::text is null or cs.tcgdex_id = %(set_id)s)
  and (%(region)s::text is null or exists (
        select 1 from card_species csp join species s on s.id = csp.species_id
        where csp.card_id = c.id and s.region = %(region)s))
  and (%(species)s::text is null or exists (
        select 1 from card_species csp join species s on s.id = csp.species_id
        where csp.card_id = c.id and s.slug = %(species)s))
  and (%(serie)s::text is null or cs.serie_name = %(serie)s)
  -- A raridade sai do mesmo coalesce que a tela mostra: filtrar por uma
  -- coluna e exibir outra daria chip que não bate com o que está na carta.
  and (%(rarities)s::text[] is null
       or coalesce(c.rarity_pt, c.rarity_en) = any (%(rarities)s::text[]))
  -- Coleção sem data fica de fora de qualquer recorte por ano: não dá para
  -- afirmar que ela está dentro nem fora.
  and (%(ano_de)s::int is null
       or extract(year from cs.release_date) >= %(ano_de)s)
  and (%(ano_ate)s::int is null
       or extract(year from cs.release_date) <= %(ano_ate)s)
  and (%(kinds)s::variant_kind[] is null or v.kind = any (%(kinds)s::variant_kind[]))
  and (%(languages)s::lang[] is null or v.language = any (%(languages)s::lang[]))
  and (%(status)s::slot_status[] is null or ci.status = any (%(status)s::slot_status[]))
  and (%(include_absent)s or v.exists_state <> 'absent')
  and (%(include_digital)s or not cs.is_digital)
order by cs.release_date nulls last, cs.tcgdex_id,
         c.number_sort nulls last, c.number, v.language, v.kind;
