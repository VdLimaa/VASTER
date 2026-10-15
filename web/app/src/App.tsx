import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  FACETAS_VAZIAS,
  RECORTE_VAZIO,
  temEscopo,
  type Binder,
  type Colecao,
  type Demo,
  type Especie,
  type Facetas,
  type Opcao,
  type Recorte,
  type Saude,
} from "./api";
import { Fichario } from "./componentes/Fichario";
import { GRADES, type Grade, totalAberturas } from "./grades";
import { Demonstracao } from "./componentes/Demonstracao";
import { Filtros } from "./componentes/Filtros";
import { Resumo } from "./componentes/Resumo";
import { alternar, carregar, salvar, type Marca } from "./marcas";

type Estado = Recorte & { grade: Grade };

/**
 * Com API no ar a tela monta qualquer recorte. Sem API, cai no snapshot
 * estático e oferece só os recortes gravados — ver `api/snapshot.py`. É o que
 * faz `npm run dev` valer a pena sozinho, sem Postgres e sem Python.
 */
type Modo = "descobrindo" | "api" | "demo" | "nada";

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
  const [especie, setEspecie] = useState<Especie | null>(null);
  const [binder, setBinder] = useState<Binder | null>(null);
  const [saude, setSaude] = useState<Saude | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [abertura, setAbertura] = useState(0);
  const [marcas, setMarcas] = useState<Record<string, Marca>>(() => carregar());
  const [modo, setModo] = useState<Modo>("descobrindo");
  const [demo, setDemo] = useState<Demo | null>(null);
  const [escolhido, setEscolhido] = useState<string | null>(null);

  // Primeira pergunta da tela: a API responde? Se não, tenta o snapshot. Só
  // depois disso as outras chamadas acontecem — em modo demonstração nenhuma
  // delas tem para onde ir.
  useEffect(() => {
    let vivo = true;
    api
      .saude()
      .then((s) => vivo && (setSaude(s), setModo("api")))
      .catch(() =>
        api
          .demo()
          .then((d) => {
            if (!vivo) return;
            setDemo(d);
            setEscolhido(d.recortes[0]?.chave ?? null);
            setModo("demo");
          })
          .catch(() => vivo && setModo("nada")),
      );
    return () => {
      vivo = false;
    };
  }, []);

  useEffect(() => {
    if (modo !== "api") return;
    api.idiomas().then(setIdiomas).catch(() => setIdiomas([]));
  }, [modo]);

  // As facetas e a lista de coleções seguem o recorte inteiro: mostrar um
  // filtro que não filtra nada é pior que não mostrar. Uma requisição para as
  // cinco listas — ver db/queries/facetas.sql.
  useEffect(() => {
    if (modo !== "api") return;
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
  }, [modo, recorte]);

  useEffect(() => {
    if (modo !== "api") return;
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
  }, [modo, recorte, busca]);

  // Derivado, não estado: ter recorte é uma leitura do que já está no
  // recorte, e calcular no render evita um setState dentro do efeito.
  const temRecorte = temEscopo(recorte);

  useEffect(() => {
    if (modo !== "api" || !temRecorte) return;
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
  }, [modo, temRecorte, recorte]);

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
  const dados: Binder | null = modo === "demo" ? recortePronto : temRecorte ? binder : null;
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
    modo === "demo"
      ? (recortePronto?.nome ?? "")
      : binder
        ? [
            especie?.nome,
            recorte.colecao ? colecoes.find((c) => c.set_id === recorte.colecao)?.set_name : null,
            recorte.era,
            recorte.regiao ? facetas.regioes.find((r) => r.valor === recorte.regiao)?.nome : null,
            recorte.raridade
              ? facetas.raridades.find((r) => r.valor === recorte.raridade)?.nome
              : null,
            recorte.tipo ? facetas.tipos.find((t) => t.valor === recorte.tipo)?.nome : null,
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

      {modo === "demo" && demo ? (
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
          especie={especie}
          estado={recorte}
          aoMudar={mudar}
          aoEscolherEspecie={(e) => {
            setEspecie(e);
            mudar({ especie: e?.valor ?? null });
          }}
          busca={busca}
          aoBuscar={setBusca}
          aoLimpar={() => {
            setRecorte({ ...INICIAL, idioma: recorte.idioma, grade: recorte.grade });
            setEspecie(null);
            setBusca("");
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
          ) : carregando || modo === "descobrindo" ? (
            <div className="vaziao">Carregando…</div>
          ) : modo === "nada" ? (
            <div className="vaziao">
              <strong>Nem a API nem o snapshot responderam</strong>
              Suba o banco e a API com <code>scripts\subir.bat</code> (Windows) ou{" "}
              <code>scripts/subir.sh</code>. Para a tela abrir sozinha, gere o snapshot:{" "}
              <code>python -m ingest snapshot</code>.
            </div>
          ) : !dados ? (
            <div className="vaziao">
              <strong>Escolha um recorte</strong>
              Um Pokémon, uma coleção, uma região ou uma era — e combine à vontade: Kanto
              dentro da 151, ou todo Charizard em português de 1999 a 2010.
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
          {modo === "demo"
            ? "Dado de um snapshot estático, sem backend no ar."
            : "Dado do seu Postgres, servido por uvicorn api.main:app."}{" "}
          As imagens vêm por hotlink do CDN do TCGdex — nenhuma carta é rehospedada.
        </p>
      </div>
    </div>
  );
}
