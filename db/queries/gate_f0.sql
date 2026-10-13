-- Gate da F0: "Sableye traz todas as coleções conhecidas, sem duplicata e com
-- a Tag Team ligada às duas espécies."
--
-- is_digital separa o Pokémon TCG Pocket: são cartas de app, não impressas,
-- e não entram num masterset físico.
--
-- Parâmetro: %(slug)s

select cs.serie, cs.region, cs.tcgdex_id as set_id,
       coalesce(cs.name_pt, cs.name_en) as set_name,
       cs.release_date, cs.is_digital, cs.pt_release, cs.pt_card_count,
       count(*) as cartas
from species s
join card_species csp on csp.species_id = s.id
join card c           on c.id = csp.card_id
join card_set cs      on cs.id = c.set_id
where s.slug = %(slug)s
group by cs.serie, cs.region, cs.tcgdex_id, cs.name_pt, cs.name_en, cs.release_date,
         cs.is_digital, cs.pt_release, cs.pt_card_count
order by cs.is_digital, cs.region, cs.release_date nulls last, cs.tcgdex_id;
