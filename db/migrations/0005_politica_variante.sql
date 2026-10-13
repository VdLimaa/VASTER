-- Regras por era: o que a API não diz. Tabela de política, não código,
-- porque cada regra nova é dado de curadoria e precisa ser auditável.
--
-- Resolução: filtra as linhas que casam com (serie, kind, language, raridade,
-- data do set), ordena por priority desc e a primeira decide. Sem linha, libera.
-- allowed=false veta o slot. annotate=true cria o slot com a razão em notes.

create table variant_policy (
  id               bigserial primary key,
  serie            text,                   -- null = toda série
  kind             variant_kind not null,
  language         lang,                   -- null = todo idioma
  rarity_regex     text,                   -- casa com rarity_en; null = qualquer
  min_set_release  date,                   -- só sets lançados a partir desta data
  max_set_release  date,                   -- só sets lançados até esta data
  allowed          boolean not null,
  annotate         boolean not null default false,
  reason           text not null,
  priority         int not null default 0,
  created_at       timestamptz not null default now()
);

create index on variant_policy (kind, priority desc);

insert into variant_policy (kind, max_set_release, allowed, reason, priority) values
  ('reverse_holo', '2002-05-23', false,
   'Reverse holo só existe a partir de Legendary Collection (2002-05-24). '
   'Antes disso o slot não deve nascer. Medido na API: base1 (1999) tem 0 de '
   '102 cartas com reverse, lc (2002-05-24) tem 110 de 110.',
   100);

insert into variant_policy (kind, rarity_regex, allowed, reason, priority) values
  ('reverse_holo',
   '(?i)(ultra rare|full art|rainbow|secret|hyper rare|gold|illustration rare'
   '|shiny rare|radiant|amazing rare|prism)',
   false,
   'Ultra Rara, Full Art, Rainbow e as raridades secretas não têm reverse holo.',
   90);

insert into variant_policy (serie, kind, allowed, annotate, reason, priority) values
  ('ex', 'reverse_holo', true, true,
   'Na era EX a reverse holo traz o nome da coleção estampado na arte. '
   'Confira a estampa antes de confirmar o slot.',
   50);
