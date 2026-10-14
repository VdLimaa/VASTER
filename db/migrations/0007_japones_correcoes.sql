-- Duas correções que só apareceram ao rodar o catálogo inteiro.

-- 1. A regra "japonês não tem reverse holo" estava ERRADA.
--
-- Ela veio de uma amostra de 54 cartas em três coleções (S6K, SM7b, PCG1),
-- todas expansões regulares, onde nenhuma tinha a flag reverse. O catálogo
-- completo refutou: 1.008 cartas japonesas em 11 coleções têm reverse, e as
-- 11 são todas high-class pack e coleção especial —
--   S8b  VMAXクライマックス (2021-12)   S12a VSTARユニバース
--   S9a  バトルリージョン               SV2a ポケモンカード151
--   S10a ダークファンタズマ             SV4a レイジングサーフ
--   S11a 白熱のアルカナ                 SV8a テラスタルフェスex
--   SV11B ブラックボルト / SV11W ホワイトフレア / M2a MEGAドリームex
-- — que de fato trazem versão espelhada desde VMAX Climax, em 2021.
--
-- A API acerta carta a carta e a regra generalizava. Sai a regra; os slots que
-- ela marcou como 'unlikely' voltam para 'unknown'.
delete from variant_policy where region = 'jp' and kind = 'reverse_holo';

update card_variant set exists_state = 'unknown', notes = null
where created_by = 'generator'
  and exists_state = 'unlikely'
  and source_url is null
  and notes like '%não imprime reverse holo%';

-- 2. Nome japonês da espécie.
--
-- 434 cartas japonesas de Pokémon não têm dexId, e o casamento por nome não
-- alcançava nenhuma delas porque species só guarda nome em alfabeto latino.
-- Sem isso, essas cartas ficam fora de todo masterset.
alter table species add column name_ja text;
create index on species (name_ja);
