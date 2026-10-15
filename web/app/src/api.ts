// Tipos e chamadas da API do Masterset BR.
// Nenhuma rota consulta serviço externo: o backend lê só o Postgres.

export type Idioma = "pt" | "en" | "ja";

export interface Opcao {
  valor: string;
  nome: string;
  slots?: number;
  especies?: number;
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
  regioes: () => pegar<Opcao[]>("/api/regioes"),
  tipos: (colecao?: string | null) =>
    pegar<Opcao[]>("/api/tipos" + (colecao ? `?colecao=${encodeURIComponent(colecao)}` : "")),
  colecoes: (p: { idioma: Idioma; regiao?: string | null; busca?: string }) => {
    const q = new URLSearchParams({ idioma: p.idioma });
    if (p.regiao) q.set("regiao", p.regiao);
    if (p.busca) q.set("busca", p.busca);
    return pegar<Colecao[]>("/api/colecoes?" + q);
  },
  binder: (p: {
    idioma: Idioma;
    colecao?: string | null;
    regiao?: string | null;
    tipo?: string | null;
  }) => {
    const q = new URLSearchParams({ idioma: p.idioma });
    if (p.colecao) q.set("colecao", p.colecao);
    if (p.regiao) q.set("regiao", p.regiao);
    if (p.tipo) q.set("tipo", p.tipo);
    return pegar<Binder>("/api/binder?" + q);
  },
};

// O CDN do TCGdex serve a mesma carta em /low.webp (16 KB) e /high.png
// (330 KB). A grade usa a leve; a carta aberta usa a cheia.
export function leve(url: string | null): string | null {
  return url ? url.replace(/\/high\.png$/, "/low.webp") : null;
}
