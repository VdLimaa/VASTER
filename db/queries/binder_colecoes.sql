-- As coleções disponíveis para montar binder, com quantos slots cada uma tem
-- no recorte pedido. Alimenta a lista de "escolha o set do seu masterset".
--
-- Os mesmos filtros do binder valem aqui: a lista mostra só coleção que
-- sobrevive ao recorte inteiro. Coleção com 0 slot no recorte não aparece.
--
-- Parâmetros: %(region)s, %(species)s, %(serie)s, %(rarities)s, %(ano_de)s,
-- %(ano_ate)s, %(kinds)s, %(languages)s, %(include_digital)s — null = sem filtro.

select cs.tcgdex_id as set_id,
       coalesce(cs.name_pt, cs.name_en) as set_name,
       cs.name_en, cs.serie_name, cs.release_date, cs.region as catalogo,
       cs.symbol_url, cs.logo_url, cs.count_official, cs.pt_release,
       count(v.id) as slots,
       count(distinct c.id) as cartas,
       count(v.id) filter (where v.exists_state = 'confirmed') as confirmados
from card_set cs
join card c on c.set_id = cs.id
join card_variant v on v.card_id = c.id
where (%(languages)s::lang[] is null or v.language = any (%(languages)s::lang[]))
  and (%(include_digital)s or not cs.is_digital)
  and v.exists_state <> 'absent'
  and (%(region)s::text is null or exists (
        select 1 from card_species csp join species s on s.id = csp.species_id
        where csp.card_id = c.id and s.region = %(region)s))
  and (%(species)s::text is null or exists (
        select 1 from card_species csp join species s on s.id = csp.species_id
        where csp.card_id = c.id and s.slug = %(species)s))
  and (%(serie)s::text is null or cs.serie_name = %(serie)s)
  and (%(rarities)s::text[] is null
       or coalesce(c.rarity_pt, c.rarity_en) = any (%(rarities)s::text[]))
  and (%(ano_de)s::int is null or extract(year from cs.release_date) >= %(ano_de)s)
  and (%(ano_ate)s::int is null or extract(year from cs.release_date) <= %(ano_ate)s)
  and (%(kinds)s::variant_kind[] is null or v.kind = any (%(kinds)s::variant_kind[]))
  and (%(forma)s::text is null or c.forma = %(forma)s)
  and (%(categoria)s::text is null or c.category_en = %(categoria)s)
  and (%(trainer_type)s::text is null or c.trainer_type_en = %(trainer_type)s)
  and (%(tipos)s::text[] is null or c.types_en && %(tipos)s::text[])
  and (%(sufixo)s::text is null or c.suffix_en = %(sufixo)s)
  and (%(estagio)s::text is null or c.stage_en = %(estagio)s)
group by cs.id, cs.tcgdex_id, cs.name_pt, cs.name_en, cs.serie_name,
         cs.release_date, cs.region, cs.symbol_url, cs.logo_url,
         cs.count_official, cs.pt_release
having count(v.id) > 0
order by cs.release_date desc nulls last, cs.tcgdex_id;
