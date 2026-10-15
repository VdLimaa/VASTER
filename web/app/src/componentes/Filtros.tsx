import type { Colecao, Facetas, Idioma, Opcao, Recorte } from "../api";
import { GRADES, type Grade } from "../grades";
import { MODOS, type Modo } from "../modos";
import { Pokedex } from "./Pokedex";

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

/** Select com contagem. Era, ano, raridade, sufixo e estágio têm valores
 *  demais para chip — o catálogo inteiro tem 32 raridades. */
function Escolha({
  itens, atual, aoEscolher, rotuloNulo,
}: {
  itens: Opcao[];
  atual: string | null;
  aoEscolher: (v: string | null) => void;
  rotuloNulo: string;
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
          {i.slots != null ? ` (${i.slots})` : ""}
        </option>
      ))}
    </select>
  );
}

export function Filtros({
  idiomas, facetas, colecoes, estado, modo, aoTrocarModo, aoMudar, aoEscolherEspecie,
  nomeEspecie, limpezas, busca, aoBuscar, aoLimpar,
}: {
  idiomas: Opcao[];
  facetas: Facetas;
  colecoes: Colecao[];
  estado: Recorte & { grade: Grade };
  modo: Modo;
  aoTrocarModo: (m: Modo) => void;
  aoMudar: (p: Partial<Recorte & { grade: Grade }>) => void;
  aoEscolherEspecie: (p: Partial<Recorte>, nome: string) => void;
  nomeEspecie: string | null;
  limpezas: number;
  busca: string;
  aoBuscar: (v: string) => void;
  aoLimpar: () => void;
}) {
  return (
    <div className="filtros nao-imprime">
      <div className="modos">
        {MODOS.map((m) => (
          <button
            key={m.valor}
            type="button"
            className="modo"
            aria-pressed={modo === m.valor}
            onClick={() => aoTrocarModo(m.valor)}
          >
            <b>{m.nome}</b>
            <span>{m.nota}</span>
          </button>
        ))}
      </div>

      {modo === "pokemon" && (
        <>
          {nomeEspecie && (
            <div className="grupo">
              <span className="rotulo">Escolhido</span>
              <button
                type="button"
                className="chip"
                aria-pressed="true"
                onClick={() => aoEscolherEspecie({ especie: null, forma: null, estagio: null }, "")}
              >
                {nomeEspecie} <span aria-hidden="true">×</span>
              </button>
              {facetas.formas.length > 1 && (
                <>
                  <span className="rotulo">Forma</span>
                  <Chips
                    itens={facetas.formas}
                    atual={estado.forma}
                    aoEscolher={(v) => aoMudar({ forma: v })}
                    comNulo
                    rotuloNulo="Todas as formas"
                  />
                </>
              )}
            </div>
          )}
          <Pokedex
            key={limpezas}
            idioma={estado.idioma}
            escolhida={estado.especie}
            regioes={facetas.regioes}
            aoEscolher={aoEscolherEspecie}
          />
        </>
      )}

      {modo === "regiao" && (
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
      )}

      {modo === "carta" && (
        <>
          <div className="grupo">
            <span className="rotulo">Categoria</span>
            <Chips
              itens={facetas.categorias}
              atual={estado.categoria}
              aoEscolher={(v) => aoMudar({ categoria: v, subtipo: null })}
              comNulo
              rotuloNulo="Todas"
            />
          </div>
          {facetas.subtipos.length > 0 && (
            <div className="grupo">
              <span className="rotulo">Treinador</span>
              <Chips
                itens={facetas.subtipos}
                atual={estado.subtipo}
                aoEscolher={(v) => aoMudar({ subtipo: v, categoria: v ? "Trainer" : estado.categoria })}
                comNulo
                rotuloNulo="Todos"
              />
            </div>
          )}
        </>
      )}

      <div className="grupo">
        <span className="rotulo">Idioma</span>
        <Chips
          itens={idiomas}
          atual={estado.idioma}
          aoEscolher={(v) => v && aoMudar({ idioma: v as Idioma })}
        />
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
        <button type="button" className="chip limpar" onClick={aoLimpar}>
          Limpar recorte
        </button>
      </div>

      {facetas.tipos.length > 0 && (
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
      )}

      <div className="grupo">
        <span className="rotulo">Variante</span>
        <Chips
          itens={facetas.variantes}
          atual={estado.variante}
          aoEscolher={(v) => aoMudar({ variante: v })}
          comNulo
          rotuloNulo="Todas"
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
        <span className="rotulo">Carta</span>
        <Escolha
          itens={facetas.raridades}
          atual={estado.raridade}
          aoEscolher={(v) => aoMudar({ raridade: v })}
          rotuloNulo="Todas as raridades"
        />
        <Escolha
          itens={facetas.sufixos}
          atual={estado.sufixo}
          aoEscolher={(v) => aoMudar({ sufixo: v })}
          rotuloNulo="ex, GX, V, VMAX…"
        />
        <Escolha
          itens={facetas.estagios}
          atual={estado.estagio}
          aoEscolher={(v) => aoMudar({ estagio: v })}
          rotuloNulo="Qualquer estágio"
        />
      </div>

      {modo === "colecao" && (
        <>
          <div className="grupo">
            <span className="rotulo">Coleção</span>
            <input
              type="search"
              value={busca}
              placeholder="Buscar coleção (ex: 151, Céus em Evolução…)"
              onChange={(e) => aoBuscar(e.target.value)}
              autoComplete="off"
            />
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
        </>
      )}
    </div>
  );
}
