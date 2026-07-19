"""Regra: P/VP muito fora da própria faixa histórica.

Não diz se está caro ou barato — registra o fato de que o mercado está
precificando o fundo muito longe do que costumou precificar, o que
merece investigação (nos dois sentidos).
"""

from __future__ import annotations

from .. import formato
from ..modelos import RedFlag, Severidade
from .contexto import Contexto

CODIGO = "pvp_faixa"
NOME = "P/VP vs faixa histórica"
OK = "P/VP dentro da faixa histórica"

_MINIMO_OBSERVACOES = 24
_DESVIO_RELEVANTE = 0.30


def aplicavel(ctx: Contexto) -> bool:
    return (
        ctx.pvp_atual() is not None
        and len(ctx.pvp_historico()) >= _MINIMO_OBSERVACOES
    )


def avaliar(ctx: Contexto) -> RedFlag | None:
    atual = ctx.pvp_atual()
    historico = ctx.pvp_historico()
    media = sum(historico) / len(historico)
    if media <= 0:
        return None
    desvio = atual / media - 1
    if abs(desvio) < _DESVIO_RELEVANTE:
        return None
    if desvio > 0:
        descricao = (
            f"A cota negocia com prêmio de {formato.percentual(desvio * 100)} sobre a média "
            "histórica do próprio fundo — o mercado está pagando bem mais que o habitual "
            "por cada real de patrimônio."
        )
        titulo = "P/VP muito acima da média histórica"
    else:
        descricao = (
            f"A cota negocia com desconto de {formato.percentual(abs(desvio) * 100)} sobre a "
            "média histórica do próprio fundo — o mercado pode estar precificando um "
            "problema; vale investigar os relatórios."
        )
        titulo = "P/VP muito abaixo da média histórica"
    return RedFlag(
        severidade=Severidade.BAIXA,
        titulo=titulo,
        fato=descricao,
        evidencia=(
            f"P/VP atual {formato.decimal(atual)} vs média histórica {formato.decimal(media)} "
            f"({len(historico)} meses observados)"
        ),
        fonte="cotações oficiais da B3 (COTAHIST) + valor patrimonial da cota (CVM)",
        codigo=CODIGO,
    )
