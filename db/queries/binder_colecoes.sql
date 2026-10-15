-- As coleções disponíveis para montar binder, com quantos slots cada uma tem
-- no recorte pedido. Alimenta a lista de "escolha o set do seu masterset".
--
-- Parâmetros: %(region)s, %(languages)s, %(include_digital)s (null = sem filtro)

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
group by cs.id, cs.tcgdex_id, cs.name_pt, cs.name_en, cs.serie_name,
         cs.release_date, cs.region, cs.symbol_url, cs.logo_url,
         cs.count_official, cs.pt_release
having count(v.id) > 0
order by cs.release_date desc nulls last, cs.tcgdex_id;
