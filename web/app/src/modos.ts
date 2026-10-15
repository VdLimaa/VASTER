/** As quatro portas de entrada da tela. Fica fora do componente porque
 *  exportar constante junto com componente quebra o Fast Refresh — e este é
 *  justamente um arquivo que se mexe toda hora. */
export type Modo = "pokemon" | "colecao" | "regiao" | "carta";

export const MODOS: { valor: Modo; nome: string; nota: string }[] = [
  { valor: "pokemon", nome: "Por Pokémon", nota: "o masterset de um bicho, em todas as coleções" },
  { valor: "colecao", nome: "Por coleção", nota: "tudo o que compõe uma coleção" },
  { valor: "regiao", nome: "Por região", nota: "os Pokémon de Kanto, de Johto…" },
  { valor: "carta", nome: "Por tipo de carta", nota: "treinador, item, apoiador, energia" },
];
