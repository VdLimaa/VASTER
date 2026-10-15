import type { Slot as SlotDado } from "../api";
import type { Grade } from "../grades";
import type { Marca } from "../marcas";
import { Slot } from "./Slot";

function Pagina({
  slots, grade, numero, marcas, aoMarcar,
}: {
  slots: SlotDado[];
  grade: Grade;
  numero: number;
  marcas: Record<string, Marca>;
  aoMarcar: (id: number, valor: Marca | null) => void;
}) {
  return (
    <div className="pagina">
      <div
        className="grade"
        style={{ gridTemplateColumns: `repeat(${grade.colunas}, 1fr)` }}
      >
        {slots.map((s) => (
          <Slot
            key={s.variant_id}
            slot={s}
            marca={marcas[s.variant_id]}
            aoMarcar={(v) => aoMarcar(s.variant_id, v)}
          />
        ))}
      </div>
      <div className="rodape-pag">Pág. {numero}</div>
    </div>
  );
}

/**
 * O fichário em folha dupla, como o de verdade: a capa fica sozinha à
 * esquerda na abertura, e daí em diante as páginas vão aos pares. Por isso a
 * primeira abertura mostra capa + página 1, e as seguintes 2+3, 4+5...
 */
export function Fichario({
  slots, grade, abertura, marcas, aoMarcar, imprimindoTudo,
}: {
  slots: SlotDado[];
  grade: Grade;
  abertura: number;
  marcas: Record<string, Marca>;
  aoMarcar: (id: number, valor: Marca | null) => void;
  imprimindoTudo: boolean;
}) {
  const porPagina = grade.colunas * grade.linhas;
  const paginas: SlotDado[][] = [];
  for (let i = 0; i < slots.length; i += porPagina) {
    paginas.push(slots.slice(i, i + porPagina));
  }

  // Na impressão não há abertura: sai tudo em sequência, uma página por folha.
  if (imprimindoTudo) {
    return (
      <div className="folha" style={{ display: "block" }}>
        {paginas.map((p, i) => (
          <Pagina
            key={i}
            slots={p}
            grade={grade}
            numero={i + 1}
            marcas={marcas}
            aoMarcar={aoMarcar}
          />
        ))}
      </div>
    );
  }

  const esquerda = abertura === 0 ? null : paginas[abertura * 2 - 1];
  const direita = abertura === 0 ? paginas[0] : paginas[abertura * 2];

  return (
    <div className="folha">
      {esquerda ? (
        <Pagina
          slots={esquerda}
          grade={grade}
          numero={abertura * 2}
          marcas={marcas}
          aoMarcar={aoMarcar}
        />
      ) : (
        <div className="pagina capa">
          <div>
            <div className="marca">Masterset BR</div>
            <div style={{ fontSize: 12, marginTop: 6 }}>capa do fichário</div>
          </div>
        </div>
      )}
      {direita && (
        <Pagina
          slots={direita}
          grade={grade}
          numero={abertura === 0 ? 1 : abertura * 2 + 1}
          marcas={marcas}
          aoMarcar={aoMarcar}
        />
      )}
    </div>
  );
}

