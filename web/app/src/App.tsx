import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  FACETAS_VAZIAS,
  RECORTE_VAZIO,
  temEscopo,
  type Binder,
  type Colecao,
  type Demo,
  type Facetas,
  type Opcao,
  type Recorte,
  type Saude,
} from "./api";
import { Fichario } from "./componentes/Fichario";
import { GRADES, type Grade, totalAberturas } from "./grades";
import { Demonstracao } from "./componentes/Demonstracao";
import { Filtros } from "./componentes/Filtros";
import { type Modo } from "./modos";
import { Resumo } from "./componentes/Resumo";
import { alternar, carregar, salvar, type Marca } from "./marcas";

type Estado = Recorte & { grade: Grade };

/**
 * Com API no ar a tela monta qualquer recorte. Sem API, cai no snapshot
 * estático e oferece só os recortes gravados — ver `api/snapshot.py`. É o que
 * faz `npm run dev` valer a pena sozinho, sem Postgres e sem Python.
 */
type Fonte = "descobrindo" | "api" | "demo" | "nada";

const INICIAL: Estado = {
  idioma: "pt", // português é o padrão: é o ponto do projeto
  ...RECORTE_VAZIO,
  grade: GRADES[1], // 3x3, o fichário clássico
};

export default function App() {
  const [recorte, setRecorte] = useState<Estado>(INICIAL);
  const [busca, setBusca] = useState("");
  const [idiomas, setIdiomas] = useState<Opcao[]>([]);
  const [facetas, setFacetas] = useState<Facetas>(FACETAS_VAZIAS);
  const [colecoes, setColecoes] = useState<Colecao[]>([]);
  const [nomeEspecie, setNomeEspecie] = useState<string | null>(null);
  const [modo, setModo] = useState<Modo>("pokemon");
  // Limpar o recorte também zera a busca e a aba da Pokédex, que são estado
  // dela. Trocar a key remonta o componente — mais simples e mais confiável
  // que um efeito espelhando prop em estado.
  const [limpezas, setLimpezas] = useState(0);
  const [binder, setBinder] = useState<Binder | null>(null);
  const [saude, setSaude] = useState<Saude | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [abertura, setAbertura] = useState(0);
  const [marcas, setMarcas] = useState<Record<string, Marca>>(() => carregar());
  const [fonte, setFonte] = useState<Fonte>("descobrindo");
  const [demo, setDemo] = useState<Demo | null>(null);
  const [escolhido, setEscolhido] = useState<string | null>(null);

  // Primeira pergunta da tela: a API responde? Se não, tenta o snapshot. Só
  // depois disso as outras chamadas acontecem — em modo demonstração nenhuma
  // delas tem para onde ir.
  useEffect(() => {
    let vivo = true;
    api
      .saude()
      .then((s) => vivo && (setSaude(s), setFonte("api")))
      .catch(() =>
        api
          .demo()
          .then((d) => {
            if (!vivo) return;
            setDemo(d);
            setEscolhido(d.recortes[0]?.chave ?? null);
            setFonte("demo");
          })
          .catch(() => vivo && setFonte("nada")),
      );
    return () => {
      vivo = false;
    };
  }, []);

  useEffect(() => {
    if (fonte !== "api") return;
    api.idiomas().then(setIdiomas).catch(() => setIdiomas([]));
  }, [fonte]);

  // As facetas e a lista de coleções seguem o recorte inteiro: mostrar um
  // filtro que não filtra nada é pior que não mostrar. Uma requisição para as
  // cinco listas — ver db/queries/facetas.sql.
  useEffect(() => {
    if (fonte !== "api") return;
    let cancelado = false;
    const t = setTimeout(() => {
      api
        .facetas(recorte)
        .then((f) => !cancelado && setFacetas(f))
        .catch(() => !cancelado && setFacetas(FACETAS_VAZIAS));
    }, 180);
    return () => {
      cancelado = true;
      clearTimeout(t);
    };
  }, [fonte, recorte]);

  useEffect(() => {
    if (fonte !== "api") return;
    let cancelado = false;
    const t = setTimeout(() => {
      api
        .colecoes(recorte, busca)
        .then((c) => !cancelado && setColecoes(c))
        .catch(() => !cancelado && setColecoes([]));
    }, 220);
    return () => {
      cancelado = true;
      clearTimeout(t);
    };
  }, [fonte, recorte, busca]);

  // Derivado, não estado: ter recorte é uma leitura do que já está no
  // recorte, e calcular no render evita um setState dentro do efeito.
  const temRecorte = temEscopo(recorte);

  useEffect(() => {
    if (fonte !== "api" || !temRecorte) return;
    let cancelado = false;
    // O lint reclama de setState dentro de efeito, mas aqui é exatamente o
    // caso que ele mesmo descreve como legítimo: sincronizar com um sistema
    // externo. O "carregando" tem que subir ANTES da chamada, senão a tela
    // mostra o recorte velho enquanto o novo vem.
    // oxlint-disable-next-line react/set-state-in-effect
    setCarregando(true);
    api
      .binder(recorte)
      .then((d) => {
        if (cancelado) return;
        setBinder(d);
        setErro(null);
        setAbertura(0);
      })
      .catch((e: Error) => !cancelado && (setErro(e.message), setBinder(null)))
      .finally(() => !cancelado && setCarregando(false));
    return () => {
      cancelado = true;
    };
  }, [fonte, temRecorte, recorte]);

  const mudar = useCallback((p: Partial<Estado>) => {
    setRecorte((r) => ({ ...r, ...p }));
    if (!("grade" in p)) setAbertura(0);
  }, []);

  const marcar = useCallback((id: number, valor: Marca | null) => {
    setMarcas((m) => {
      const prox = alternar(m, id, valor);
      salvar(prox);
      return prox;
    });
  }, []);

  // No modo demonstração o recorte sai do snapshot; com API, do binder. Daí
  // para baixo a tela é a mesma — fichário, grade, marcas e impressão não
  // sabem de onde veio o dado.
  const recortePronto = demo?.recortes.find((r) => r.chave === escolhido) ?? null;
  // Sem recorte, nada do binder anterior aparece — nem por um quadro.
  const dados: Binder | null = fonte === "demo" ? recortePronto : temRecorte ? binder : null;
  const slots = dados?.slots ?? [];
  const aberturas = useMemo(
    () => (slots.length ? totalAberturas(slots.length, recorte.grade) : 0),
    [slots.length, recorte.grade],
  );

  // Impressão: o fichário sai em sequência, uma página por folha, e não só a
  // abertura aberta na tela. window.print() é síncrono, então não adianta
  // trocar o estado dentro de beforeprint — o React não repinta a tempo. O
  // caminho é marcar, deixar pintar, e só então abrir o diálogo.
  const [imprimindo, setImprimindo] = useState(false);
  const imprimir = useCallback(() => setImprimindo(true), []);
  useEffect(() => {
    if (!imprimindo) return;
    const t = setTimeout(() => {
      window.print();
      setImprimindo(false);
    }, 150);
    return () => clearTimeout(t);
  }, [imprimindo]);

  const contagem = saude ?? demo?.saude ?? null;
  const anos =
    recorte.anoDe && recorte.anoAte && recorte.anoDe !== recorte.anoAte
      ? `${recorte.anoDe}–${recorte.anoAte}`
      : (recorte.anoDe ?? recorte.anoAte ?? null);
  const titulo =
    fonte === "demo"
      ? (recortePronto?.nome ?? "")
      : binder
        ? [
            nomeEspecie,
            recorte.colecao ? colecoes.find((c) => c.set_id === recorte.colecao)?.set_name : null,
            recorte.era,
            recorte.regiao ? facetas.regioes.find((r) => r.valor === recorte.regiao)?.nome : null,
            recorte.categoria
              ? facetas.categorias.find((c) => c.valor === recorte.categoria)?.nome
              : null,
            recorte.subtipo
              ? facetas.subtipos.find((s) => s.valor === recorte.subtipo)?.nome
              : null,
            recorte.tipo ? facetas.tipos.find((t) => t.valor === recorte.tipo)?.nome : null,
            recorte.raridade
              ? facetas.raridades.find((r) => r.valor === recorte.raridade)?.nome
              : null,
            recorte.sufixo,
            recorte.estagio
              ? facetas.estagios.find((e) => e.valor === recorte.estagio)?.nome
              : null,
            recorte.variante
              ? facetas.variantes.find((v) => v.valor === recorte.variante)?.nome
              : null,
            anos,
          ]
            .filter(Boolean)
            .join(" · ")
        : "";

  return (
    <div className="wrap">
      <h1>Monte seu fichário</h1>
      <p className="sub">
        Sem login — o que você marca fica salvo neste aparelho.
        {contagem &&
          ` · ${contagem.slots.toLocaleString("pt-BR")} slots em ${contagem.colecoes} coleções`}
      </p>

      {fonte === "demo" && demo ? (
        <Demonstracao
          demo={demo}
          escolhido={escolhido}
          aoEscolher={(c) => {
            setEscolhido(c);
            setAbertura(0);
          }}
          grade={recorte.grade}
          aoMudarGrade={(g) => mudar({ grade: g })}
        />
      ) : (
        <Filtros
          idiomas={idiomas}
          facetas={facetas}
          colecoes={colecoes}
          estado={recorte}
          modo={modo}
          aoTrocarModo={setModo}
          aoMudar={mudar}
          nomeEspecie={nomeEspecie}
          limpezas={limpezas}
          aoEscolherEspecie={(p, nome) => {
            setNomeEspecie(nome || null);
            mudar(p);
          }}
          busca={busca}
          aoBuscar={setBusca}
          aoLimpar={() => {
            setRecorte({ ...INICIAL, idioma: recorte.idioma, grade: recorte.grade });
            setNomeEspecie(null);
            setBusca("");
            setLimpezas((n) => n + 1);
          }}
        />
      )}

      <div className="palco">
        <div>
          {titulo && <div className="impressao-cabeca">Masterset — {titulo}</div>}
          {erro ? (
            <div className="vaziao">
              <strong>Não deu</strong>
              {erro}
            </div>
          ) : carregando || fonte === "descobrindo" ? (
            <div className="vaziao">Carregando…</div>
          ) : fonte === "nada" ? (
            <div className="vaziao">
              <strong>Nem a API nem o snapshot responderam</strong>
              Suba o banco e a API com <code>scripts\subir.bat</code> (Windows) ou{" "}
              <code>scripts/subir.sh</code>. Para a tela abrir sozinha, gere o snapshot:{" "}
              <code>python -m ingest snapshot</code>.
            </div>
          ) : !dados ? (
            <div className="vaziao">
              <strong>Escolha um recorte</strong>
              Escolha um Pokémon na Pokédex, uma coleção, uma região ou um tipo de carta —
              e combine à vontade: Mega Charizard em português, só as cartas de apoiador da
              151, ou todo Pikachu de 1999 a 2005.
            </div>
          ) : slots.length === 0 ? (
            <div className="vaziao">
              <strong>Nenhum slot nesse recorte</strong>
              Afrouxe um filtro ou troque o idioma.
            </div>
          ) : (
            <>
              <Fichario
                slots={slots}
                grade={recorte.grade}
                abertura={abertura}
                marcas={marcas}
                aoMarcar={marcar}
                imprimindoTudo={imprimindo}
              />
              <div className="paginacao nao-imprime">
                <button
                  type="button"
                  disabled={abertura === 0}
                  onClick={() => setAbertura((a) => a - 1)}
                >
                  ← Anterior
                </button>
                <span>
                  Abertura {abertura + 1} de {aberturas}
                </span>
                <button
                  type="button"
                  disabled={abertura + 1 >= aberturas}
                  onClick={() => setAbertura((a) => a + 1)}
                >
                  Próxima →
                </button>
              </div>
            </>
          )}
        </div>
        <Resumo
          slots={slots}
          marcas={marcas}
          resumo={dados?.resumo ?? null}
          aoImprimir={imprimir}
        />
      </div>

      <div className="rodape nao-imprime">
        <p>
          {fonte === "demo"
            ? "Dado de um snapshot estático, sem backend no ar."
            : "Dado do seu Postgres, servido por uvicorn api.main:app."}{" "}
          As imagens vêm por hotlink do CDN do TCGdex — nenhuma carta é rehospedada.
        </p>
      </div>
    </div>
  );
}
