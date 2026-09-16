"""
Analise de itens: o que so se sabe depois de as pessoas responderem.

O resto deste pipeline julga um item pelo que ele parece. Isto julga-o pelo que
ele fez a uma populacao, e sao coisas diferentes: um item pode estar impecavel
escrito e continuar a nao medir nada.

Tres numeros por item e um para o exame inteiro:

  dificuldade (p)       fraccao que acertou. Alto = facil. Chama-se p-value por
                        razoes historicas e nao tem nada que ver com o p-value
                        da estatistica inferencial.

  discriminacao (rpb)   correlacao ponto-bisserial entre acertar este item e a
                        nota no resto do exame. E o numero que mais importa:
                        negativo quer dizer que os bons falham e os fracos
                        acertam, e isso e quase sempre enunciado ambiguo ou
                        chave errada.

  distractores          quantos escolheram cada opcao, e a nota media de quem a
                        escolheu. Um distractor que ninguem escolhe nao esta a
                        fazer trabalho nenhum. Um distractor escolhido pelos
                        melhores alunos e uma segunda resposta certa disfarcada.

  KR-20                 consistencia interna do exame todo. Diz se os itens
                        estao a medir a mesma coisa uns que os outros.

O ponto-bisserial e calculado contra a nota TOTAL MENOS O PROPRIO ITEM. Sem
essa correccao, cada item esta a correlacionar-se em parte consigo proprio, e a
discriminacao aparece sistematicamente inflacionada, sobretudo em exames curtos
como os de oito perguntas.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

# Limiares de sinalizacao. Sao convencoes correntes em avaliacao educativa, nao
# sao leis: um item facil de proposito no inicio de um capitulo esta bem.
P_MUITO_FACIL = 0.95
P_MUITO_DIFICIL = 0.25
RPB_FRACO = 0.15
RPB_NEGATIVO = 0.0
KR20_ACEITAVEL = 0.70
MIN_RESPOSTAS = 30  # abaixo disto os numeros sao ruido, e dizemos isso


@dataclass
class Opcao:
    indice: int
    escolhas: int
    fraccao: float
    nota_media_de_quem_escolheu: float | None


@dataclass
class Item:
    id: str
    respostas: int
    dificuldade: float
    discriminacao: float | None
    opcoes: list[Opcao] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


@dataclass
class Exame:
    itens: list[Item]
    candidatos: int
    kr20: float | None
    avisos: list[str] = field(default_factory=list)


def _ponto_bisserial(acertos: list[int], criterio: list[float]) -> float | None:
    """
    Correlacao entre acertar o item (0 ou 1) e o criterio (nota nos restantes).

    Devolve None quando nao ha variancia: se toda a gente acertou, ou toda a
    gente falhou, a correlacao nao existe. Devolver zero nesse caso seria
    mentir, porque zero quer dizer "nao discrimina" e isto quer dizer "nao da
    para saber".
    """
    n = len(acertos)
    if n < 2:
        return None
    certos = [c for a, c in zip(acertos, criterio) if a == 1]
    errados = [c for a, c in zip(acertos, criterio) if a == 0]
    if not certos or not errados:
        return None
    dp = statistics.pstdev(criterio)
    if dp == 0:
        return None
    p = len(certos) / n
    return (statistics.mean(certos) - statistics.mean(errados)) / dp * math.sqrt(p * (1 - p))


def _kr20(matriz: list[list[int]]) -> float | None:
    """
    Kuder-Richardson 20, a consistencia interna para itens dicotomicos.

    E o alfa de Cronbach quando as respostas sao certas ou erradas. Devolve
    None se a variancia das notas totais for zero, porque nesse caso nao ha
    nada para explicar.
    """
    if not matriz or len(matriz) < 2:
        return None
    k = len(matriz[0])
    if k < 2:
        return None
    totais = [sum(linha) for linha in matriz]
    var_total = statistics.pvariance(totais)
    if var_total == 0:
        return None
    soma_pq = 0.0
    for j in range(k):
        p = sum(linha[j] for linha in matriz) / len(matriz)
        soma_pq += p * (1 - p)
    return (k / (k - 1)) * (1 - soma_pq / var_total)


def analisar(
    matriz: list[list[int]],
    ids: list[str] | None = None,
    escolhas: list[list[int | None]] | None = None,
) -> Exame:
    """
    matriz    uma linha por candidato, uma coluna por item, 1 acertou 0 falhou.
    ids       nomes dos itens, por omissao item-1, item-2...
    escolhas  opcional, a MESMA forma, mas com o indice da opcao escolhida.
              So com isto e que se consegue analise de distractores.
    """
    if not matriz:
        return Exame(itens=[], candidatos=0, kr20=None, avisos=["sem respostas"])

    n_cand = len(matriz)
    k = len(matriz[0])
    if any(len(linha) != k for linha in matriz):
        raise ValueError("todas as linhas tem de ter o mesmo numero de itens")

    nomes = ids or [f"item-{i + 1}" for i in range(k)]
    avisos_exame: list[str] = []
    if n_cand < MIN_RESPOSTAS:
        avisos_exame.append(
            f"{n_cand} candidatos: abaixo de {MIN_RESPOSTAS} estes numeros sao "
            f"indicativos e nao devem decidir nada")

    totais = [sum(linha) for linha in matriz]
    itens: list[Item] = []

    for j in range(k):
        coluna = [linha[j] for linha in matriz]
        p = sum(coluna) / n_cand
        # Criterio corrigido: nota total menos o proprio item.
        criterio = [t - c for t, c in zip(totais, coluna)]
        rpb = _ponto_bisserial(coluna, [float(x) for x in criterio])

        avisos: list[str] = []
        if p >= P_MUITO_FACIL:
            avisos.append(f"acertaram {p:.0%}: nao esta a separar ninguem")
        elif p <= P_MUITO_DIFICIL:
            avisos.append(f"so {p:.0%} acertou: ou e mesmo dificil, ou esta mal escrito")
        if rpb is None:
            avisos.append("sem variancia suficiente para calcular discriminacao")
        elif rpb < RPB_NEGATIVO:
            avisos.append(f"discriminacao NEGATIVA ({rpb:.2f}): os melhores estao a falhar "
                          f"este item, suspeita da chave")
        elif rpb < RPB_FRACO:
            avisos.append(f"discriminacao fraca ({rpb:.2f}): nao mede o mesmo que o resto")

        opcoes: list[Opcao] = []
        if escolhas:
            col_esc = [linha[j] for linha in escolhas]
            vistas = sorted({e for e in col_esc if e is not None})
            for idx in vistas:
                quem = [t for t, e in zip(totais, col_esc) if e == idx]
                opcoes.append(Opcao(
                    indice=idx,
                    escolhas=len(quem),
                    fraccao=len(quem) / n_cand,
                    nota_media_de_quem_escolheu=statistics.mean(quem) if quem else None,
                ))
            avisos.extend(_avisos_distractores(opcoes, coluna, col_esc, totais))

        itens.append(Item(id=nomes[j], respostas=n_cand, dificuldade=p,
                          discriminacao=rpb, opcoes=opcoes, avisos=avisos))

    kr = _kr20(matriz)
    if kr is not None and kr < KR20_ACEITAVEL:
        avisos_exame.append(f"KR-20 de {kr:.2f}, abaixo de {KR20_ACEITAVEL}: os itens nao "
                            f"estao a medir todos a mesma coisa")

    return Exame(itens=itens, candidatos=n_cand, kr20=kr, avisos=avisos_exame)


def _avisos_distractores(opcoes: list[Opcao], acertos: list[int],
                         col_esc: list[int | None], totais: list[int]) -> list[str]:
    out: list[str] = []
    # Qual das opcoes e a certa: a que foi escolhida por quem acertou.
    certa = next((e for a, e in zip(acertos, col_esc) if a == 1 and e is not None), None)
    media_geral = statistics.mean(totais) if totais else 0.0

    for o in opcoes:
        if o.indice == certa:
            continue
        if o.escolhas == 0:
            out.append(f"opcao {o.indice} nunca foi escolhida: nao esta a fazer trabalho nenhum")
        elif (o.nota_media_de_quem_escolheu is not None
              and o.nota_media_de_quem_escolheu > media_geral):
            out.append(f"opcao {o.indice} foi escolhida por quem tem nota ACIMA da media: "
                       f"e uma segunda resposta defensavel, nao um distractor")
    return out


def formatar(exame: Exame) -> str:
    """Relatorio de texto, para ler no terminal."""
    linhas: list[str] = []
    linhas.append(f"{exame.candidatos} candidatos, {len(exame.itens)} itens")
    linhas.append(f"KR-20: {exame.kr20:.2f}" if exame.kr20 is not None else "KR-20: nao calculavel")
    for a in exame.avisos:
        linhas.append(f"  nota: {a}")
    linhas.append("")
    linhas.append(f"{'item':<14}{'dificuldade':>12}{'discrim.':>10}")
    for it in exame.itens:
        d = f"{it.discriminacao:.2f}" if it.discriminacao is not None else "  n/d"
        linhas.append(f"{it.id:<14}{it.dificuldade:>11.0%}{d:>10}")
        for a in it.avisos:
            linhas.append(f"{'':14}{a}")
    return "\n".join(linhas)
