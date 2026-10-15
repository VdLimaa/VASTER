// O que o colecionador marcou, guardado no aparelho — sem login, como no
// fichário de verdade. Toda leitura e escrita é protegida: em aba privada o
// localStorage pode lançar, e a tela tem que continuar funcionando.

export type Marca = "owned" | "wanted";

const CHAVE = "vaster.binder.v1";

export function carregar(): Record<string, Marca> {
  try {
    const cru = localStorage.getItem(CHAVE);
    return cru ? (JSON.parse(cru) as Record<string, Marca>) : {};
  } catch {
    return {};
  }
}

export function salvar(marcas: Record<string, Marca>): void {
  try {
    localStorage.setItem(CHAVE, JSON.stringify(marcas));
  } catch {
    /* aba privada ou armazenamento bloqueado: segue sem persistir */
  }
}

export function alternar(
  marcas: Record<string, Marca>,
  id: number,
  valor: Marca | null,
): Record<string, Marca> {
  const prox = { ...marcas };
  if (valor === null || prox[id] === valor) delete prox[id];
  else prox[id] = valor;
  return prox;
}
