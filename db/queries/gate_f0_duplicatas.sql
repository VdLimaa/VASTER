-- Gate da F0, parte 2: nenhuma carta repetida no masterset de uma espécie.
-- Deve devolver zero linhas.
select c.tcgdex_id, count(*) as vinculos
from species s
join card_species csp on csp.species_id = s.id
join card c           on c.id = csp.card_id
where s.slug = %(slug)s
group by c.tcgdex_id
having count(*) > 1;
