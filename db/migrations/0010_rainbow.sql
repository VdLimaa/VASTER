-- Correção de rótulo encontrada ao conferir /en/rarities, que lista as 42
-- raridades que o TCGdex usa.
--
-- O TCGdex NÃO usa a palavra "rainbow". A rainbow rare se chama 'Hyper rare'
-- lá, e 'Secret Rare' é a dourada — são raridades distintas na API. O regex
-- do gerador casava hyper junto de secret e mandava as duas para 'gold',
-- então 82 cartas rainbow apareciam rotuladas como gold no masterset.
--
-- Relabela em vez de recriar: o slot é o mesmo, só o nome estava errado. Isso
-- preserva qualquer curadoria já feita nele, e evita que a próxima execução de
-- 'slots' crie um slot 'rainbow' ao lado do 'gold' e duplique a carta.
update card_variant v set kind = 'rainbow'
from card c
where c.id = v.card_id
  and v.kind = 'gold'
  and c.rarity_en ~* 'hyper\s*rare';
