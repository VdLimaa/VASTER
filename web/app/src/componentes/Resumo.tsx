import type { Resumo as ResumoDado, Slot } from "../api";
import type { Marca } from "../marcas";

export function Resumo({
  slots, marcas, resumo, aoImprimir,
}: {
  slots: Slot[];
  marcas: Record<string, Marca>;
  resumo: ResumoDado | null;
  aoImprimir: () => void;
}) {
  const total = slots.length;
  const tenho = slots.filter((s) => marcas[s.variant_id] === "owned").length;
  const quero = slots.filter((s) => marcas[s.variant_id] === "wanted").length;
  const pct = total ? Math.round((100 * tenho) / total) : 0;

  return (
    <aside className="resumo nao-imprime">
      <div>
        <div className="pct">{pct}%</div>
        <div className="barra">
          <i style={{ width: `${pct}%` }} />
        </div>
        <div style={{ fontSize: 12.5, color: "var(--fg-mute)", marginTop: 6 }}>
          {tenho} de {total} slots
          {resumo ? ` · ${resumo.cartas} cartas` : ""}
        </div>
      </div>
      <div className="tiles">
        <div className="tile ok">
          <b>{tenho}</b>
          <span>Tenho</span>
        </div>
        <div className="tile wait">
          <b>{quero}</b>
          <span>Quero</span>
        </div>
        <div className="tile">
          <b>{total - tenho}</b>
          <span>Falta</span>
        </div>
      </div>
      {resumo && (
        <div className="notas">
          {resumo.confirmados} confirmados pelo catálogo
          {resumo.inferidos > 0 && (
            <>
              <br />
              {resumo.inferidos} inferidos por regra de era
            </>
          )}
          {resumo.sem_foto > 0 && (
            <>
              <br />
              {resumo.sem_foto} sem foto
            </>
          )}
          {resumo.fora_do_catalogo > 0 && (
            <>
              <br />
              {resumo.fora_do_catalogo} fora do catálogo
            </>
          )}
        </div>
      )}
      {total > 0 && (
        <button type="button" className="botao" onClick={aoImprimir}>
          Imprimir o fichário
        </button>
      )}
    </aside>
  );
}
