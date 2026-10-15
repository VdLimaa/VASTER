"""O snapshot não precisa de banco para estar errado.

Um tipo fora do vocabulário, ou um idioma que não existe, dá recorte vazio —
e recorte vazio desaparece da tela sem ninguém notar, porque `gerar()` pula
quem não tem slot. Estes testes são a rede para isso. O id da coleção só o
banco sabe conferir; é o que `python -m ingest snapshot` mostra ao gravar.
"""

from __future__ import annotations

from api import consultas
from api.snapshot import RECORTES


def test_chaves_unicas() -> None:
    chaves = [r.chave for r in RECORTES]
    assert len(chaves) == len(set(chaves))


def test_tipo_existe_no_vocabulario() -> None:
    for r in RECORTES:
        if r.tipo is not None:
            assert consultas.kinds_do_grupo([r.tipo]), f"{r.chave}: tipo '{r.tipo}' não existe"


def test_idioma_conhecido() -> None:
    for r in RECORTES:
        assert r.idioma in consultas.IDIOMAS, f"{r.chave}: idioma '{r.idioma}'"


def test_todo_recorte_tem_recorte() -> None:
    """Sem coleção, região nem espécie, a rota recusa — o snapshot também não
    deve ter um recorte que puxaria o catálogo inteiro."""
    for r in RECORTES:
        assert r.colecao or r.regiao or r.especie or r.categoria, f"{r.chave}: recorte vazio"


def test_nota_explica() -> None:
    for r in RECORTES:
        assert len(r.nota) > 40, f"{r.chave}: a nota precisa dizer o que o recorte mostra"
