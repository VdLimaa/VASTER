// Tipos e chamadas da API do Masterset BR.
// Nenhuma rota consulta serviço externo: o backend lê só o Postgres.

export type Idioma = "pt" | "en" | "ja";

/** Os filtros da tela. É o mesmo conjunto que `api/consultas.py:Recorte`
 *  espera — as quatro rotas de recorte leem todos eles.
 *
 *  Duas palavras que confundem se trocadas: **tipo** é fogo, água, planta,
 *  como todo mundo usa; **variante** é normal, reverse holo, full art, que é
 *  o que gera slot. */
export interface Recorte {
  idioma: Idioma;
  colecao: string | null;
  regiao: string | null;
  especie: string | null;
  forma: string | null;
  era: string | null;
  variante: string | null;
  raridade: string | null;
  categoria: string | null;
  subtipo: string | null;
  tipo: string | null;
  sufixo: string | null;
  estagio: string | null;
  anoDe: number | null;
  anoAte: number | null;
}

export const RECORTE_VAZIO: Omit<Recorte, "idioma"> = {
  colecao: null,
  regiao: null,
  especie: null,
  forma: null,
  era: null,
  variante: null,
  raridade: null,
  categoria: null,
  subtipo: null,
  tipo: null,
  sufixo: null,
  estagio: null,
  anoDe: null,
  anoAte: null,
};

/** Sem nenhum destes a API recusa: seria o catálogo inteiro. */
export function temEscopo(r: Recorte): boolean {
  return Boolean(
    r.colecao ||
      r.regiao ||
      r.especie ||
      r.era ||
      r.forma ||
      r.subtipo ||
      (r.categoria && r.categoria !== "Pokemon"),
  );
}

function params(r: Recorte): URLSearchParams {
  const q = new URLSearchParams({ idioma: r.idioma });
  const simples: [keyof Recorte, string][] = [
    ["colecao", "colecao"],
    ["regiao", "regiao"],
    ["especie", "especie"],
    ["forma", "forma"],
    ["era", "era"],
    ["variante", "variante"],
    ["raridade", "raridade"],
    ["categoria", "categoria"],
    ["subtipo", "subtipo"],
    ["tipo", "tipo"],
    ["sufixo", "sufixo"],
    ["estagio", "estagio"],
  ];
  for (const [campo, nome] of simples) {
    const v = r[campo];
    if (v) q.set(nome, String(v));
  }
  if (r.anoDe != null) q.set("ano_de", String(r.anoDe));
  if (r.anoAte != null) q.set("ano_ate", String(r.anoAte));
  return q;
}

export interface Opcao {
  valor: string;
  nome: string;
  slots?: number;
  desde?: number | null;
}

/** As dez listas que a rota de facetas devolve, cada uma contada ignorando
 *  o próprio filtro. */
export interface Facetas {
  eras: Opcao[];
  anos: Opcao[];
  raridades: Opcao[];
  variantes: Opcao[];
  categorias: Opcao[];
  subtipos: Opcao[];
  tipos: Opcao[];
  sufixos: Opcao[];
  estagios: Opcao[];
  formas: Opcao[];
  regioes: Opcao[];
}

export const FACETAS_VAZIAS: Facetas = {
  eras: [],
  anos: [],
  raridades: [],
  variantes: [],
  categorias: [],
  subtipos: [],
  tipos: [],
  sufixos: [],
  estagios: [],
  formas: [],
  regioes: [],
};

/** Uma linha da Pokédex: o bicho, o sprite, e o recorte que escolhê-lo
 *  aplica — que muda de forma para forma. */
export interface EspecieDex {
  valor: string;
  nome: string;
  dex: number;
  nome_ja: string | null;
  regiao: string | null;
  regiao_nome: string | null;
  sprite: string | null;
  slots: number;
  recorte: { especie: string; forma: string | null; estagio: string | null };
}

export interface Pokedex {
  dex: string;
  abas: Opcao[];
  especies: EspecieDex[];
}

export interface Colecao {
  set_id: string;
  set_name: string;
  name_en: string | null;
  serie_name: string | null;
  release_date: string | null;
  catalogo: string;
  symbol_url: string | null;
  count_official: number | null;
  pt_release: string;
  slots: number;
  cartas: number;
  confirmados: number;
}

export interface Slot {
  variant_id: number;
  set_id: string;
  set_name: string;
  serie_name: string | null;
  set_release: string | null;
  set_count_official: number | null;
  card_id: string;
  number: string;
  card_name: string;
  card_name_en: string | null;
  rarity: string | null;
  kind: string;
  language: Idioma;
  exists_state: string;
  created_by: string;
  notes: string | null;
  source_url: string | null;
  image_url: string | null;
  has_scan: boolean;
  no_catalogo: boolean;
  especies: string[] | null;
  regioes: string[] | null;
  forma: string | null;
  categoria: string | null;
  subtipo: string | null;
  tipos: string[] | null;
  sufixo: string | null;
  estagio: string | null;
}

export interface Resumo {
  slots: number;
  cartas: number;
  colecoes: number;
  tenho: number;
  quero: number;
  falta: number;
  confirmados: number;
  inferidos: number;
  sem_foto: number;
  fora_do_catalogo: number;
}

export interface Binder {
  recorte: Record<string, unknown>;
  resumo: Resumo;
  slots: Slot[];
}

export interface Saude {
  ok: boolean;
  colecoes: number;
  cartas: number;
  slots: number;
  especies: number;
}

/** Um recorte já calculado, gravado por `python -m ingest snapshot`. */
export interface RecortePronto extends Binder {
  chave: string;
  nome: string;
  nota: string;
}

/** O snapshot estático: é o que a tela usa quando não há backend no ar. */
export interface Demo {
  gerado_em: string;
  saude: Omit<Saude, "ok">;
  idiomas: Opcao[];
  recortes: RecortePronto[];
}

async function pegar<T>(rota: string): Promise<T> {
  const r = await fetch(rota);
  if (!r.ok) {
    let detalhe = `${r.status}`;
    try {
      detalhe = ((await r.json()) as { detail?: string }).detail ?? detalhe;
    } catch {
      /* resposta sem corpo JSON */
    }
    throw new Error(detalhe);
  }
  return (await r.json()) as T;
}

export const api = {
  saude: () => pegar<Saude>("/api/saude"),
  idiomas: () => pegar<Opcao[]>("/api/idiomas"),
  // Lido do arquivo estático, não da API: é o caminho sem backend. BASE_URL
  // para a tela funcionar também servida de um subdiretório.
  demo: () => pegar<Demo>(`${import.meta.env.BASE_URL}demo.json`),
  facetas: (r: Recorte) => pegar<Facetas>("/api/facetas?" + params(r)),
  pokedex: (p: { dex: string; idioma: Idioma; regiao?: string | null; busca?: string }) => {
    const q = new URLSearchParams({ dex: p.dex, idioma: p.idioma });
    if (p.regiao) q.set("regiao", p.regiao);
    if (p.busca) q.set("busca", p.busca);
    return pegar<Pokedex>("/api/pokedex?" + q);
  },
  colecoes: (r: Recorte, busca?: string) => {
    const q = params(r);
    q.delete("colecao"); // a lista mostra as opções, não a escolhida
    if (busca) q.set("busca", busca);
    return pegar<Colecao[]>("/api/colecoes?" + q);
  },
  binder: (r: Recorte) => pegar<Binder>("/api/binder?" + params(r)),
};

// O CDN do TCGdex serve a mesma carta em /low.webp (16 KB) e /high.png
// (330 KB). A grade usa a leve; a carta aberta usa a cheia.
export function leve(url: string | null): string | null {
  return url ? url.replace(/\/high\.png$/, "/low.webp") : null;
}
