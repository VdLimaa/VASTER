import type { Colecao, Especie, Facetas, Idioma, Opcao, Recorte } from "../api";
import { GRADES, type Grade } from "../grades";
import { BuscaEspecie } from "./BuscaEspecie";

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
          {i.slots != null && <span className="n">{i.slots}</span>}
        </button>
      ))}
    </>
  );
}

/** Select com contagem no rótulo. Era, ano e raridade têm valores demais
 *  para chip — a 151 sozinha tem 8 raridades, o catálogo inteiro tem 32. */
function Escolha({
  itens, atual, aoEscolher, rotuloNulo, sufixo,
}: {
  itens: Opcao[];
  atual: string | null;
  aoEscolher: (v: string | null) => void;
  rotuloNulo: string;
  sufixo?: string;
}) {
  return (
    <select
      value={atual ?? ""}
      onChange={(e) => aoEscolher(e.target.value || null)}
      disabled={itens.length === 0}
    >
      <option value="">{rotuloNulo}</option>
      {itens.map((i) => (
        <option key={i.valor} value={i.valor}>
          {i.nome}
          {i.slots != null ? ` (${i.slots}${sufixo ?? ""})` : ""}
        </option>
      ))}
    </select>
  );
}

export function Filtros({
  idiomas, facetas, colecoes, especie, estado, aoMudar, aoEscolherEspecie,
  busca, aoBuscar, aoLimpar,
}: {
  idiomas: Opcao[];
  facetas: Facetas;
  colecoes: Colecao[];
  especie: Especie | null;
  estado: Recorte & { grade: Grade };
  aoMudar: (p: Partial<Recorte & { grade: Grade }>) => void;
  aoEscolherEspecie: (e: Especie | null) => void;
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
        <span className="rotulo">Pokémon</span>
        <BuscaEspecie escolhida={especie} aoEscolher={aoEscolherEspecie} />
      </div>

      <div className="grupo">
        <span className="rotulo">Região</span>
        <Chips
          itens={facetas.regioes}
          atual={estado.regiao}
          aoEscolher={(v) => aoMudar({ regiao: v })}
          comNulo
          rotuloNulo="Todas as regiões"
        />
      </div>

      <div className="grupo">
        <span className="rotulo">Era e ano</span>
        <Escolha
          itens={facetas.eras}
          atual={estado.era}
          aoEscolher={(v) => aoMudar({ era: v })}
          rotuloNulo="Todas as eras"
        />
        <Escolha
          itens={facetas.anos}
          atual={estado.anoDe != null ? String(estado.anoDe) : null}
          aoEscolher={(v) => aoMudar({ anoDe: v ? Number(v) : null })}
          rotuloNulo="De qualquer ano"
        />
        <Escolha
          itens={facetas.anos}
          atual={estado.anoAte != null ? String(estado.anoAte) : null}
          aoEscolher={(v) => aoMudar({ anoAte: v ? Number(v) : null })}
          rotuloNulo="Até hoje"
        />
      </div>

      <div className="grupo">
        <span className="rotulo">Raridade</span>
        <Escolha
          itens={facetas.raridades}
          atual={estado.raridade}
          aoEscolher={(v) => aoMudar({ raridade: v })}
          rotuloNulo="Todas as raridades"
        />
      </div>

      <div className="grupo">
        <span className="rotulo">Tipo</span>
        <Chips
          itens={facetas.tipos}
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
                {c.slots} {c.slots === 1 ? "slot" : "slots"}
                <br />
                {c.cartas} {c.cartas === 1 ? "carta" : "cartas"}
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
