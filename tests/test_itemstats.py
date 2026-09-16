"""
Testes da analise de itens.

Cada caso constroi uma populacao com um defeito conhecido e exige que a analise
o encontre. E o controlo e sempre o mesmo padrao: ao lado de cada caso partido
ha um caso saudavel que tem de passar limpo, senao o unico que eu estaria a
provar era que o analisador se queixa de tudo.
"""

from __future__ import annotations

import pytest

from pipeline.itemstats import (
    KR20_ACEITAVEL, MIN_RESPOSTAS, analisar, formatar,
)


def _coorte(n: int = 100, k: int = 8) -> list[list[int]]:
    """
    Uma populacao saudavel, construida a mao e nao ao acaso.

    O candidato i tem capacidade i/n, e acerta o item j se a capacidade dele
    passar a dificuldade do item. Isto produz exactamente o que um exame bom
    produz: itens com dificuldades diferentes e discriminacao positiva, sem
    precisar de gerador aleatorio (que tornaria o teste instavel).
    """
    # Taxas de acerto entre 0.70 e 0.30, que e a zona util de um exame bom. A
    # primeira versao ia de 0.11 a 0.89 e o item mais dificil disparava o aviso
    # com razao: a fixture e que estava errada, nao o analisador.
    dificuldades = [0.30 + 0.40 * j / (k - 1) for j in range(k)]
    return [[1 if (i / n) >= d else 0 for d in dificuldades] for i in range(n)]


def test_coorte_saudavel_nao_levanta_avisos():
    e = analisar(_coorte())
    assert e.candidatos == 100
    assert e.kr20 is not None and e.kr20 >= KR20_ACEITAVEL
    assert not e.avisos
    assert all(not it.avisos for it in e.itens)


def test_item_que_toda_a_gente_acerta():
    m = _coorte()
    for linha in m:
        linha[0] = 1
    e = analisar(m)
    assert any("nao esta a separar" in a for a in e.itens[0].avisos)


def test_item_que_quase_ninguem_acerta():
    m = _coorte()
    for i, linha in enumerate(m):
        linha[0] = 1 if i > 90 else 0
    e = analisar(m)
    assert any("mal escrito" in a for a in e.itens[0].avisos)


def test_discriminacao_negativa_e_apanhada():
    """O caso que mais importa: a chave esta trocada e os bons falham."""
    m = _coorte()
    for i, linha in enumerate(m):
        linha[0] = 0 if (i / len(m)) >= 0.5 else 1  # ao contrario do resto
    e = analisar(m)
    assert e.itens[0].discriminacao is not None
    assert e.itens[0].discriminacao < 0
    assert any("NEGATIVA" in a for a in e.itens[0].avisos)


def test_discriminacao_e_corrigida_pelo_proprio_item():
    """
    Sem tirar o item do criterio, a discriminacao vem inflacionada.

    Num exame de oito itens o proprio item vale um oitavo da nota, e isso chega
    para uma diferenca visivel. Este teste existe porque a versao errada passa
    todos os outros testes deste ficheiro.
    """
    m = _coorte(n=100, k=8)
    e = analisar(m)
    corrigida = e.itens[3].discriminacao

    totais = [sum(l) for l in m]
    coluna = [l[3] for l in m]
    from pipeline.itemstats import _ponto_bisserial
    inflacionada = _ponto_bisserial(coluna, [float(t) for t in totais])

    assert corrigida is not None and inflacionada is not None
    assert inflacionada > corrigida


def test_kr20_baixo_quando_os_itens_medem_coisas_diferentes():
    """Metade dos itens mede uma coisa, metade mede outra, sem relacao."""
    # Cada item com um periodo diferente e coprimo dos outros: nenhum par de
    # itens se correlaciona, que e o que faz a consistencia interna cair.
    periodos = [2, 3, 5, 7, 11, 13]
    m = [[1 if (i // 1) % per < per // 2 else 0 for per in periodos] for i in range(120)]
    e = analisar(m)
    assert e.kr20 is not None and e.kr20 < KR20_ACEITAVEL
    assert any("mesma coisa" in a for a in e.avisos)


def test_poucos_candidatos_avisa_em_vez_de_fingir():
    e = analisar(_coorte(n=12))
    assert any("indicativos" in a for a in e.avisos)
    assert str(MIN_RESPOSTAS) in " ".join(e.avisos)


def test_sem_variancia_devolve_none_e_nao_zero():
    """Toda a gente acertou: a discriminacao nao existe, nao e zero."""
    m = [[1, 1, 0] for _ in range(50)]
    e = analisar(m)
    assert e.itens[0].discriminacao is None
    assert any("sem variancia" in a for a in e.itens[0].avisos)


# --------------------------------------------------------------- distractores
def _com_escolhas(matriz, escolhas):
    return analisar(matriz, escolhas=escolhas)


def test_distractor_que_ninguem_escolhe():
    m = _coorte(n=60, k=3)
    esc = []
    for linha in m:
        # opcao 0 e a certa; quem falha escolhe sempre a 1, nunca a 2
        esc.append([0 if c == 1 else 1 for c in linha])
    e = _com_escolhas(m, esc)
    # a opcao 2 nunca aparece nas escolhas, logo nao entra nas opcoes vistas;
    # o que se verifica e que as que aparecem sao so duas
    assert len(e.itens[0].opcoes) == 2


def test_distractor_escolhido_pelos_melhores():
    """Uma segunda resposta defensavel disfarcada de distractor."""
    # Cinco itens: quatro estabelecem a escala de capacidade, e o item 0 e o
    # que esta sob suspeita. No item 0 a chave e a opcao 0, mas quem tem nota
    # alta escolhe a opcao 2, que e uma segunda resposta defensavel.
    n = 100
    m = []
    for i in range(n):
        forte = i >= 50
        bons = [1 if forte else 0] * 4
        m.append([0 if forte else 1] + bons)  # os fortes falham o item 0
    esc = [[2 if linha[0] == 0 else 0] + [0 if c == 1 else 1 for c in linha[1:]]
           for linha in m]
    e = _com_escolhas(m, esc)
    texto = " ".join(a for it in e.itens for a in it.avisos)
    assert "defensavel" in texto


# ------------------------------------------------------------------ formatar
def test_relatorio_sai_legivel():
    saida = formatar(analisar(_coorte()))
    assert "candidatos" in saida and "KR-20" in saida and "dificuldade" in saida


def test_matriz_irregular_e_erro():
    with pytest.raises(ValueError):
        analisar([[1, 0, 1], [1, 0]])


def test_sem_respostas_nao_rebenta():
    e = analisar([])
    assert e.candidatos == 0 and e.kr20 is None
