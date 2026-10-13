-- Gate da F0, parte 2: nenhuma carta repetida no masterset de uma espécie.
-- Deve devolver zero linhas.
--
-- Agrupa por c.id, não por tcgdex_id: desde que o catálogo japonês entrou,
-- tcgdex_id só é único junto da região ('neo1-1' existe nos dois), e agrupar
-- pelo id do TCGdex acusaria duplicata onde há duas cartas diferentes.
select c.tcgdex_id, c.region, count(*) as vinculos
from species s
join card_species csp on csp.species_id = s.id
join card c           on c.id = csp.card_id
where s.slug = %(slug)s
group by c.id, c.tcgdex_id, c.region
having count(*) > 1;
