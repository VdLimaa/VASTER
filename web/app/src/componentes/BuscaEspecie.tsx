import { useEffect, useState } from "react";
import { api, type Especie } from "../api";

/**
 * O masterset de um Pokémon — a premissa do projeto, e o único filtro que
 * não cabe em chips: são 1.025 espécies.
 *
 * Busca por nome em inglês, por nome japonês e pelo número da Pokédex, que é
 * como colecionador procura. O estado do campo é dele; para fora sai só a
 * espécie escolhida.
 */
export function BuscaEspecie({
  escolhida,
  aoEscolher,
}: {
  escolhida: Especie | null;
  aoEscolher: (e: Especie | null) => void;
}) {
  const [texto, setTexto] = useState("");
  const [achados, setAchados] = useState<Especie[]>([]);

  // Com menos de duas letras nem busca, e o que já veio fica escondido pelo
  // `mostrar` abaixo — derivar no render evita um setState dentro do efeito.
  useEffect(() => {
    const alvo = texto.trim();
    if (alvo.length < 2) return;
    let cancelado = false;
    const t = setTimeout(() => {
      api
        .especies(alvo)
        .then((e) => !cancelado && setAchados(e))
        .catch(() => !cancelado && setAchados([]));
    }, 220);
    return () => {
      cancelado = true;
      clearTimeout(t);
    };
  }, [texto]);

  const mostrar = texto.trim().length >= 2 ? achados : [];

  if (escolhida) {
    return (
      <button
        type="button"
        className="chip"
        aria-pressed="true"
        onClick={() => {
          aoEscolher(null);
          setTexto("");
        }}
        title="Tirar o filtro de espécie"
      >
        {escolhida.nome}
        <span className="n">#{escolhida.dex}</span>
        <span aria-hidden="true">×</span>
      </button>
    );
  }

  return (
    <>
      <input
        type="search"
        value={texto}
        placeholder="Pokémon (ex: charizard, リザードン, 6)"
        onChange={(e) => setTexto(e.target.value)}
        autoComplete="off"
      />
      {mostrar.slice(0, 8).map((e) => (
        <button
          key={e.valor}
          type="button"
          className="chip"
          onClick={() => {
            aoEscolher(e);
            setTexto("");
          }}
        >
          {e.nome}
          <span className="n">#{e.dex}</span>
        </button>
      ))}
      {texto.trim().length >= 2 && mostrar.length === 0 && (
        <span className="sem-achado">nenhum Pokémon com esse nome</span>
      )}
    </>
  );
}
