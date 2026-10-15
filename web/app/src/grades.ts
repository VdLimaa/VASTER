// As grades que o fichário de verdade tem, colunas × linhas.
// Em arquivo próprio para o Fast Refresh funcionar: um módulo que exporta
// componente e constante junto perde a recarga instantânea.

export const GRADES = [
  { valor: "2x2", colunas: 2, linhas: 2 },
  { valor: "3x3", colunas: 3, linhas: 3 },
  { valor: "4x3", colunas: 4, linhas: 3 },
  { valor: "3x4", colunas: 3, linhas: 4 },
  { valor: "4x4", colunas: 4, linhas: 4 },
  { valor: "5x4", colunas: 5, linhas: 4 },
] as const;

export type Grade = (typeof GRADES)[number];

/** Quantas aberturas o fichário tem: a capa ocupa sozinha a primeira. */
export function totalAberturas(slots: number, grade: Grade): number {
  const porPagina = grade.colunas * grade.linhas;
  const paginas = Math.ceil(slots / porPagina);
  return paginas <= 1 ? 1 : 1 + Math.ceil((paginas - 1) / 2);
}
