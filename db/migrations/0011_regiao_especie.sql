-- Região e geração da espécie, para o masterset poder ser recortado por
-- "Pokémon de Kanto".
--
-- Vem da PokéAPI, no campo generation do detalhe da espécie — a mesma
-- requisição que já busca name_ja, então não custa nada a mais. O mapeamento
-- de geração para região foi conferido em /api/v2/generation/{1..9} e soma
-- exatamente 1.025 espécies, que é o nosso total:
--
--   kanto 151 · johto 100 · hoenn 135 · sinnoh 107 · unova 156
--   kalos  72 · alola  88 · galar  96 · paldea 120
--
-- Região é da ESPÉCIE, não da carta: um Pikachu numa coleção de Paldea
-- continua sendo de Kanto. É assim que o colecionador pensa o recorte.

alter table species add column generation text;
alter table species add column region text;

create index on species (region);
create index on species (generation);
