// Tipos e chamadas da API do Masterset BR.
// Nenhuma rota consulta serviço externo: o backend lê só o Postgres.

export type Idioma = "pt" | "en" | "ja";

/** Os filtros da tela. É o mesmo conjunto que `api/consultas.py:Recorte`
 *  espera — as três rotas de recorte leem todos eles. */
export interface Recorte {
  idioma: Idioma;
  colecao: string | null;
  regiao: string | null;
  especie: string | null;
  era: string | null;
  tipo: string | null;
  raridade: string | null;
  anoDe: number | null;
  anoAte: number | null;
}

export const RECORTE_VAZIO: Omit<Recorte, "idioma"> = {
  colecao: null,
  regiao: null,
  especie: null,
  era: null,
  tipo: null,
  raridade: null,
  anoDe: null,
  anoAte: null,
};

/** Sem nenhum destes a API recusa: seria o catálogo inteiro. */
export function temEscopo(r: Recorte): boolean {
  return Boolean(r.colecao || r.regiao || r.especie || r.era);
}

function params(r: Recorte): URLSearchParams {
  const q = new URLSearchParams({ idioma: r.idioma });
  if (r.colecao) q.set("colecao", r.colecao);
  if (r.regiao) q.set("regiao", r.regiao);
  if (r.especie) q.set("especie", r.especie);
  if (r.era) q.set("era", r.era);
  if (r.tipo) q.set("tipo", r.tipo);
  if (r.raridade) q.set("raridade", r.raridade);
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

export interface Facetas {
  eras: Opcao[];
  anos: Opcao[];
  raridades: Opcao[];
  tipos: Opcao[];
  regioes: Opcao[];
}

export const FACETAS_VAZIAS: Facetas = {
  eras: [],
  anos: [],
  raridades: [],
  tipos: [],
  regioes: [],
};

export interface Especie {
  valor: string;
  nome: string;
  dex: number;
  nome_ja: string | null;
  regiao: string | null;
  regiao_nome: string | null;
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
  especies: (busca: string, regiao?: string | null) => {
    const q = new URLSearchParams({ limite: "12" });
    if (busca) q.set("busca", busca);
    if (regiao) q.set("regiao", regiao);
    return pegar<Especie[]>("/api/especies?" + q);
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
