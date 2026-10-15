import { leve, type Slot as SlotDado } from "../api";
import type { Marca } from "../marcas";

const ROTULO_TIPO: Record<string, string> = {
  regular: "Normal", reverse_holo: "RF", holo: "Holo", alt_art: "Arte",
  full_art: "Full Art", rainbow: "Rainbow", gold: "Gold", shiny: "Shiny",
  promo: "Promo", first_edition: "1ª ed",
};
const ESPECIAIS = new Set(["alt_art", "full_art", "rainbow", "gold", "shiny"]);

/** A numeração como vem impressa: 169/165 nas secretas. */
function numeroImpresso(s: SlotDado): string {
  if (!s.set_count_official) return s.number;
  const total = String(s.set_count_official);
  return `${String(s.number).padStart(total.length, "0")}/${total}`;
}

export function Slot({
  slot, marca, aoMarcar,
}: {
  slot: SlotDado;
  marca: Marca | undefined;
  aoMarcar: (valor: Marca | null) => void;
}) {
  const img = leve(slot.image_url);
  const classeTag =
    slot.kind === "reverse_holo" ? "tag rf" : ESPECIAIS.has(slot.kind) ? "tag esp" : "tag";

  return (
    <div className="slot" data-marca={marca ?? ""}>
      <div className="arte">
        {img ? (
          <img src={img} alt="" loading="lazy" />
        ) : (
          <div className="vazio">
            sem foto
            {!slot.no_catalogo && (
              <>
                <br />
                fora do catálogo
              </>
            )}
          </div>
        )}
      </div>
      <span className="num">{numeroImpresso(slot)}</span>
      <span className="nome">{slot.card_name}</span>
      <div className="marcas">
        <span className={classeTag}>{ROTULO_TIPO[slot.kind] ?? slot.kind}</span>
        {slot.created_by === "inferred" && (
          <span
            className="tag inf"
            title="A API não lista esta variante. O slot veio de uma regra de era."
          >
            inferido
          </span>
        )}
      </div>
      <div className="acoes">
        <button type="button" className="b-ok" onClick={() => aoMarcar("owned")}>
          Tenho
        </button>
        <button type="button" className="b-want" onClick={() => aoMarcar("wanted")}>
          Quero
        </button>
        <button type="button" className="b-no" onClick={() => aoMarcar(null)}>
          Falta
        </button>
      </div>
    </div>
  );
}
