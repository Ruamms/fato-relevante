"""Regra: distribuição possivelmente acima da geração de resultado.

Se o fundo distribui rendimentos enquanto o VP/cota cai de forma
relevante no mesmo período, parte do rendimento pode estar saindo do
patrimônio (amortização disfarçada), não do resultado gerado.
"""

from __future__ import annotations

from .. import formato
from ..modelos import RedFlag, Severidade
from .contexto import Contexto

CODIGO = "distribuicao"
NOME = "distribuição vs variação patrimonial"
OK = "distribuição compatível com a variação patrimonial"

_QUEDA_RELEVANTE = -3.0
_QUEDA_GRAVE = -8.0


def aplicavel(ctx: Contexto) -> bool:
    return ctx.dy_acumulado_12m() is not None and ctx.variacao_vp(12) is not None


def avaliar(ctx: Contexto) -> RedFlag | None:
    dy_12m = ctx.dy_acumulado_12m() * 100
    variacao_vp = ctx.variacao_vp(12)
    if dy_12m <= 0 or variacao_vp > _QUEDA_RELEVANTE:
        return None
    return RedFlag(
        severidade=Severidade.ALTA if variacao_vp <= _QUEDA_GRAVE else Severidade.MEDIA,
        titulo="Distribuição possivelmente acima da geração de resultado",
        fato=(
            f"O fundo distribuiu {formato.percentual(dy_12m)} em rendimentos nos últimos "
            f"12 meses enquanto o VP/cota caiu {formato.percentual(abs(variacao_vp))} — "
            "parte do rendimento pode estar saindo do patrimônio, não do resultado."
        ),
        evidencia=(
            f"DY acumulado 12m {formato.percentual(dy_12m)}; "
            f"VP/cota ajustado {formato.percentual(variacao_vp, sinal=True)} em 12m"
        ),
        fonte="informes mensais CVM (dividend yield e valor patrimonial da cota)",
        codigo=CODIGO,
    )
