"""Regra: VP/cota em queda relevante em 12 meses (patrimônio derretendo)."""

from __future__ import annotations

from .. import formato
from ..modelos import RedFlag, Severidade
from .contexto import Contexto

CODIGO = "vp_queda"
NOME = "queda do VP/cota em 12 meses"
OK = "VP/cota sem queda relevante em 12 meses"

_QUEDA_MEDIA = -10.0
_QUEDA_ALTA = -20.0


def aplicavel(ctx: Contexto) -> bool:
    return ctx.variacao_vp(12) is not None


def avaliar(ctx: Contexto) -> RedFlag | None:
    variacao = ctx.variacao_vp(12)
    if variacao > _QUEDA_MEDIA:
        return None
    return RedFlag(
        severidade=Severidade.ALTA if variacao <= _QUEDA_ALTA else Severidade.MEDIA,
        titulo="VP/cota em queda relevante",
        fato=(
            f"O valor patrimonial por cota caiu {formato.percentual(abs(variacao))} nos "
            "últimos 12 meses — o patrimônio do fundo está encolhendo por cota."
        ),
        evidencia=f"VP/cota ajustado {formato.percentual(variacao, sinal=True)} em 12m",
        fonte="informes mensais CVM (valor patrimonial da cota)",
        codigo=CODIGO,
    )
