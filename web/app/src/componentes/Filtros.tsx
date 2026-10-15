import type { Colecao, Idioma, Opcao } from "../api";
import { GRADES, type Grade } from "../grades";

function Chips({
  itens, atual, aoEscolher, comNulo, rotuloNulo,
}: {
  itens: Opcao[];
  atual: string | null;
  aoEscolher: (v: string | null) => void;
  comNulo?: boolean;
  rotuloNulo?: string;
}) {
  return (
    <>
      {comNulo && (
        <button
          type="button"
          className="chip"
          aria-pressed={atual === null}
          onClick={() => aoEscolher(null)}
        >
          {rotuloNulo ?? "Todos"}
        </button>
      )}
      {itens.map((i) => (
        <button
          key={i.valor}
          type="button"
          className="chip"
          aria-pressed={atual === i.valor}
          onClick={() => aoEscolher(atual === i.valor && comNulo ? null : i.valor)}
        >
          {i.nome}
          {(i.slots ?? i.especies) != null && (
            <span className="n">{i.slots ?? i.especies}</span>
          )}
        </button>
      ))}
    </>
  );
}

export function Filtros({
  idiomas, regioes, tipos, colecoes, estado, aoMudar, busca, aoBuscar, aoLimpar,
}: {
  idiomas: Opcao[];
  regioes: Opcao[];
  tipos: Opcao[];
  colecoes: Colecao[];
  estado: { idioma: Idioma; regiao: string | null; tipo: string | null; colecao: string | null; grade: Grade };
  aoMudar: (p: Partial<{ idioma: Idioma; regiao: string | null; tipo: string | null; colecao: string | null; grade: Grade }>) => void;
  busca: string;
  aoBuscar: (v: string) => void;
  aoLimpar: () => void;
}) {
  return (
    <div className="filtros nao-imprime">
      <div className="grupo">
        <span className="rotulo">Idioma</span>
        <Chips
          itens={idiomas}
          atual={estado.idioma}
          aoEscolher={(v) => v && aoMudar({ idioma: v as Idioma })}
        />
      </div>
      <div className="grupo">
        <span className="rotulo">Região</span>
        <Chips
          itens={regioes}
          atual={estado.regiao}
          aoEscolher={(v) => aoMudar({ regiao: v })}
          comNulo
          rotuloNulo="Todas as regiões"
        />
      </div>
      <div className="grupo">
        <span className="rotulo">Tipo</span>
        <Chips
          itens={tipos}
          atual={estado.tipo}
          aoEscolher={(v) => aoMudar({ tipo: v })}
          comNulo
          rotuloNulo="Todos os tipos"
        />
      </div>
      <div className="grupo">
        <span className="rotulo">Grade</span>
        {GRADES.map((g) => (
          <button
            key={g.valor}
            type="button"
            className="chip"
            aria-pressed={estado.grade.valor === g.valor}
            onClick={() => aoMudar({ grade: g })}
          >
            {g.valor}
          </button>
        ))}
      </div>
      <div className="grupo">
        <span className="rotulo">Coleção</span>
        <input
          type="search"
          value={busca}
          placeholder="Buscar coleção (ex: 151, Céus em Evolução…)"
          onChange={(e) => aoBuscar(e.target.value)}
          autoComplete="off"
        />
        <button type="button" className="chip" onClick={aoLimpar}>
          Limpar recorte
        </button>
      </div>
      <div className="colecoes">
        {colecoes.length === 0 ? (
          <div style={{ padding: 14, color: "var(--fg-mute)" }}>
            Nenhuma coleção nesse recorte.
          </div>
        ) : (
          colecoes.slice(0, 200).map((c) => (
            <button
              key={c.set_id}
              type="button"
              className="colecao"
              aria-pressed={c.set_id === estado.colecao}
              onClick={() =>
                aoMudar({ colecao: c.set_id === estado.colecao ? null : c.set_id })
              }
            >
              <span>
                <span className="nome">{c.set_name}</span>
                <br />
                <span className="meta">
                  {c.serie_name}
                  {c.release_date ? ` · ${c.release_date.slice(0, 4)}` : ""} · {c.set_id}
                </span>
              </span>
              <span className="cnt">
                {c.slots} slots
                <br />
                {c.cartas} cartas
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
