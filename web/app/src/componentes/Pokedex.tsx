import { useEffect, useState } from "react";
import { api, type EspecieDex, type Idioma, type Opcao, type Recorte } from "../api";

/**
 * A Pokédex de escolha: 1.025 espécies com sprite, separadas por região, e
 * as dex de forma — megas, formas regionais, Gigantamax, Primal.
 *
 * Cada linha já vem do servidor com o recorte que escolhê-la aplica, porque
 * o filtro muda de forma para forma: mega é `forma=mega`, a de Alola é
 * `forma=alola`, e Gigantamax não tem nome em carta nenhuma — a carta dela é
 * a VMAX, então o recorte é por estágio.
 *
 * Os sprites vêm por hotlink do repositório da PokéAPI, como as cartas vêm
 * do CDN do TCGdex. Nada rehospedado aqui.
 */
export function Pokedex({
  idioma,
  escolhida,
  regioes,
  aoEscolher,
}: {
  idioma: Idioma;
  escolhida: string | null;
  regioes: Opcao[];
  aoEscolher: (p: Partial<Recorte>, nome: string) => void;
}) {
  const [dex, setDex] = useState("especie");
  const [regiao, setRegiao] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [abas, setAbas] = useState<Opcao[]>([]);
  const [especies, setEspecies] = useState<EspecieDex[]>([]);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    let cancelado = false;
    const t = setTimeout(() => {
      // oxlint-disable-next-line react/set-state-in-effect
      setCarregando(true);
      api
        .pokedex({ dex, idioma, regiao, busca })
        .then((d) => {
          if (cancelado) return;
          setAbas(d.abas);
          setEspecies(d.especies);
        })
        .catch(() => !cancelado && setEspecies([]))
        .finally(() => !cancelado && setCarregando(false));
    }, 200);
    return () => {
      cancelado = true;
      clearTimeout(t);
    };
  }, [dex, idioma, regiao, busca]);

  // Nas dex de forma a região da espécie continua valendo (Raichu de Alola é
  // de Kanto), mas filtrar por ela ali confunde mais do que ajuda.
  const porRegiao = dex === "especie";

  return (
    <div className="pokedex">
      <div className="grupo">
        <span className="rotulo">Pokédex</span>
        {abas.map((a) => (
          <button
            key={a.valor}
            type="button"
            className="chip"
            aria-pressed={dex === a.valor}
            onClick={() => {
              setDex(a.valor);
              setRegiao(null);
            }}
          >
            {a.nome}
          </button>
        ))}
        <input
          type="search"
          value={busca}
          placeholder="Buscar: charizard, リザードン, 6…"
          onChange={(e) => setBusca(e.target.value)}
          autoComplete="off"
        />
      </div>

      {porRegiao && (
        <div className="grupo">
          <span className="rotulo">Região</span>
          <button
            type="button"
            className="chip"
            aria-pressed={regiao === null}
            onClick={() => setRegiao(null)}
          >
            Todas
          </button>
          {regioes.map((r) => (
            <button
              key={r.valor}
              type="button"
              className="chip"
              aria-pressed={regiao === r.valor}
              onClick={() => setRegiao(regiao === r.valor ? null : r.valor)}
            >
              {r.nome}
            </button>
          ))}
        </div>
      )}

      <div className="dex-grade">
        {carregando && especies.length === 0 ? (
          <div className="dex-aviso">Carregando a Pokédex…</div>
        ) : especies.length === 0 ? (
          <div className="dex-aviso">Nenhum Pokémon aqui.</div>
        ) : (
          especies.map((e) => (
            <button
              key={e.valor + (e.recorte.forma ?? "") + (e.recorte.estagio ?? "")}
              type="button"
              className="dex-item"
              aria-pressed={escolhida === e.valor}
              onClick={() => aoEscolher(e.recorte, e.nome)}
              title={`#${e.dex} · ${e.nome}${e.nome_ja ? ` · ${e.nome_ja}` : ""}`}
            >
              {e.sprite && <img src={e.sprite} alt="" loading="lazy" width="72" height="72" />}
              <span className="dex-nome">{e.nome}</span>
              <span className="dex-meta">
                #{String(e.dex).padStart(3, "0")} · {e.slots} slots
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
