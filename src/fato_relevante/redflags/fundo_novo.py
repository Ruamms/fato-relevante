"""Regra: fundo novo — histórico curto demais para conclusões.

Não é defeito do fundo; é um ponto de atenção do usuário: com pouco
histórico, quase nenhuma outra regra consegue avaliar e o passado não
diz nada sobre consistência.
"""

from __future__ import annotations

from ..modelos import RedFlag, Severidade
from .contexto import Contexto

CODIGO = "fundo_novo"
NOME = "tempo de histórico do fundo"
OK = "fundo com 24+ meses de histórico na CVM"

_MESES_MINIMOS = 24


def aplicavel(ctx: Contexto) -> bool:
    return ctx.meses_de_historico() > 0


def avaliar(ctx: Contexto) -> RedFlag | None:
    meses = ctx.meses_de_historico()
    if meses >= _MESES_MINIMOS:
        return None
    return RedFlag(
        severidade=Severidade.BAIXA,
        titulo="Fundo novo — histórico curto",
        fato=(
            f"O fundo tem apenas {meses} meses de informes na CVM. Com pouco histórico "
            "não dá para avaliar consistência de rendimento, gestão em crise ou ciclos — "
            "boa parte das regras deste raio-x fica sem base para rodar."
        ),
        evidencia=f"{meses} informes mensais na CVM (referência de maturidade: {_MESES_MINIMOS}+)",
        fonte="informes mensais CVM (série histórica)",
        codigo=CODIGO,
    )
