import type { Demo } from "../api";
import { GRADES, type Grade } from "../grades";

/**
 * O painel do modo demonstração, no lugar dos filtros.
 *
 * Filtro que não filtra é pior que filtro nenhum: sem backend não existe
 * "qualquer coleção, qualquer região", existe este punhado de recortes
 * gravados. Então a tela oferece exatamente eles, e diz o que falta para
 * abrir o resto.
 */
export function Demonstracao({
  demo,
  escolhido,
  aoEscolher,
  grade,
  aoMudarGrade,
}: {
  demo: Demo;
  escolhido: string | null;
  aoEscolher: (chave: string) => void;
  grade: Grade;
  aoMudarGrade: (g: Grade) => void;
}) {
  const atual = demo.recortes.find((r) => r.chave === escolhido);
  const dia = demo.gerado_em.slice(0, 10).split("-").reverse().join("/");

  return (
    <div className="filtros nao-imprime">
      <div className="aviso">
        <strong>Modo demonstração</strong>
        <span>
          A API não está no ar, então a tela está lendo {demo.recortes.length} recortes
          prontos, gravados em {dia} de um catálogo com{" "}
          {demo.saude.slots.toLocaleString("pt-BR")} slots em {demo.saude.colecoes} coleções.
          Para montar <em>qualquer</em> recorte — coleção, região, tipo e os três idiomas —
          suba o banco e a API: <code>scripts\subir.bat</code> no Windows,{" "}
          <code>scripts/subir.sh</code> no Linux e no macOS.
        </span>
      </div>

      <div className="grupo">
        <span className="rotulo">Recorte</span>
        {demo.recortes.map((r) => (
          <button
            key={r.chave}
            type="button"
            className="chip"
            aria-pressed={r.chave === escolhido}
            onClick={() => aoEscolher(r.chave)}
          >
            {r.nome}
            <span className="n">{r.resumo.slots}</span>
          </button>
        ))}
      </div>

      <div className="grupo">
        <span className="rotulo">Grade</span>
        {GRADES.map((g) => (
          <button
            key={g.valor}
            type="button"
            className="chip"
            aria-pressed={grade.valor === g.valor}
            onClick={() => aoMudarGrade(g)}
          >
            {g.valor}
          </button>
        ))}
      </div>

      {atual && <p className="nota-recorte">{atual.nota}</p>}
    </div>
  );
}
