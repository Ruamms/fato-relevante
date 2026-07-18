"""Regra: base de cotistas pequena.

Abaixo de 100 cotistas o FII deixa de cumprir um dos requisitos da
isenção de imposto de renda dos rendimentos para pessoa física
(Lei 11.033/2004, mínimo elevado de 50 para 100 pela Lei 14.754/2023).
Mesmo acima disso, uma base muito pequena indica liquidez baixa e
concentração de poder de voto.
"""

from __future__ import annotations

from .. import formato
from ..modelos import RedFlag, Severidade
from .contexto import Contexto

CODIGO = "cotistas"
NOME = "tamanho da base de cotistas"
OK = "base de cotistas adequada"

_MINIMO_ISENCAO = 100
_BASE_PEQUENA = 500


def aplicavel(ctx: Contexto) -> bool:
    return ctx.cotistas() is not None


def avaliar(ctx: Contexto) -> RedFlag | None:
    total = int(ctx.cotistas())
    if total >= _BASE_PEQUENA:
        return None
    if total < _MINIMO_ISENCAO:
        return RedFlag(
            severidade=Severidade.ALTA,
            titulo="Menos cotistas que o mínimo para isenção de IR",
            fato=(
                f"O fundo tem {formato.compacto(total)} cotistas — abaixo dos 100 exigidos "
                "para a isenção de IR dos rendimentos de pessoa física "
                "(Lei 14.754/2023). Rendimentos podem ser tributados."
            ),
            evidencia=f"{total} cotistas no último informe mensal (mínimo legal: 100)",
            fonte="informes mensais CVM (número de cotistas)",
            codigo=CODIGO,
        )
    return RedFlag(
        severidade=Severidade.BAIXA,
        titulo="Base de cotistas muito pequena",
        fato=(
            f"O fundo tem apenas {formato.compacto(total)} cotistas — liquidez tende a ser "
            "baixa e poucos cotistas concentram as decisões em assembleia."
        ),
        evidencia=f"{total} cotistas no último informe mensal",
        fonte="informes mensais CVM (número de cotistas)",
        codigo=CODIGO,
    )
