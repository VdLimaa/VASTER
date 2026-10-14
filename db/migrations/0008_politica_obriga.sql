-- A política ganha duas capacidades: obrigar um slot e filtrar por coleção.
--
-- MOTIVO, medido em 2026-10-14 no catálogo inteiro. A flag 'reverse' do
-- TCGdex está ausente em eras inteiras. Percentual de cartas Common,
-- Uncommon, Rare e Rare Holo com reverse = true, por era:
--
--   Legendary Collection 100%   Diamond & Pearl  92%   Sword & Shield  96%
--   E-Card                99%   Platinum         96%   Scarlet&Violet 100%
--   EX                    53%   HeartGold        97%   Mega Evolution  88%
--   ---------------------------------------------------------------------
--   Black & White          0%   XY                0%   Sun & Moon       6%
--
-- Black & White, XY e Sun & Moon são três eras consecutivas, de 2011 a 2019,
-- em que a reverse holo é das mais comuns que existem. Zero é dado faltando,
-- não ausência real. Duas provas:
--
--   * POP (4%) e Trainer kits (0%) também dão zero, e ali é CORRETO — esses
--     produtos não têm reverse holo. O método distingue um caso do outro.
--   * 'sm3' Burning Shadows tem 116 de 117 preenchidas, na mesma era em que
--     todas as outras dão zero. Se a era não tivesse reverse, sm3 também não
--     teria.
--
-- São ~5.300 cartas sem o slot de RF, ~10.600 slots contando os dois idiomas.
-- Num masterset, slot faltando é pior que slot sobrando: o colecionador nunca
-- descobre que a carta existe. Por isso o slot inferido nasce 'unknown' com a
-- razão em notes — custa uma decisão de curadoria, e some com um delete desta
-- linha de política se o TCGdex preencher o dado depois.

alter table variant_policy add column obriga boolean not null default false;
alter table variant_policy add column set_regex text;

comment on column variant_policy.obriga is
  'true: gera o slot mesmo quando a API não lista a variante. Nasce unknown.';
comment on column variant_policy.set_regex is
  'casa com card_set.tcgdex_id; null = qualquer coleção';

-- Promos não têm reverse holo. Precisa vir antes da regra que obriga, por
-- isso a prioridade mais alta.
insert into variant_policy (kind, set_regex, allowed, reason, priority) values
  ('reverse_holo', '(?i)(^|-)(bwp|xyp|smp|swshp|svp|basep|np|dp-p|hgss-p)$', false,
   'Coleção de promos não tem reverse holo.', 200);

insert into variant_policy
  (serie, kind, rarity_regex, allowed, obriga, annotate, reason, priority)
select s, 'reverse_holo', '(?i)^(common|uncommon|rare|rare holo)$', true, true, true,
       'Slot inferido pela era: nesta coleção a reverse holo existe, mas o '
       'TCGdex não traz a flag. Medido em 2026-10-14 — a era ' || s ||
       ' tem praticamente zero cartas com reverse marcado, enquanto as eras '
       'vizinhas passam de 90%. Confirme antes de caçar a carta.',
       70
from unnest(array['bw', 'xy', 'sm']) as s;
