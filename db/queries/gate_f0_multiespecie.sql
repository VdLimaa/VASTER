-- Gate da F0, parte 3: cartas ligadas a mais de uma espécie (Tag Team, Mega
-- dupla). Para Sableye deve trazer as 'Mega Sableye & Tyranitar GX'
-- aparecendo também no masterset de Tyranitar.
select c.tcgdex_id, c.name_en,
       array_agg(s.slug order by s.dex_number) as especies,
       array_agg(distinct csp.resolved_by)     as resolvido_por
from card c
join card_species csp on csp.card_id = c.id
join species s        on s.id = csp.species_id
where c.id in (
  select csp2.card_id from card_species csp2
  join species s2 on s2.id = csp2.species_id
  where s2.slug = %(slug)s
)
group by c.tcgdex_id, c.name_en
having count(*) > 1
order by c.tcgdex_id;
