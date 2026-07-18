"""Regra: emissão de cotas com VP/cota em queda (diluição destrutiva).

Emitir cotas não é ruim em si — vira problema quando o número de cotas
cresce e o valor patrimonial por cota cai no mesmo período: os cotistas
antigos ficaram com uma fatia menor de um bolo que não cresceu junto.
"""

from __future__ import annotations

from .. import formato
from ..modelos import RedFlag, Severidade
from .contexto import Contexto

CODIGO = "diluicao"
NOME = "diluição por emissão de cotas"
OK = "sem diluição destrutiva nas emissões de cotas"

_CRESCIMENTO_RELEVANTE = 10.0
_QUEDA_VP = -2.0


def _janela(ctx: Contexto) -> int | None:
    for meses in (24, 12):
        if ctx.variacao_cotas(meses) is not None and ctx.variacao_vp(meses) is not None:
            return meses
    return None


def aplicavel(ctx: Contexto) -> bool:
    return _janela(ctx) is not None


def avaliar(ctx: Contexto) -> RedFlag | None:
    meses = _janela(ctx)
    variacao_cotas = ctx.variacao_cotas(meses)
    variacao_vp = ctx.variacao_vp(meses)
    if variacao_cotas < _CRESCIMENTO_RELEVANTE or variacao_vp > _QUEDA_VP:
        return None
    return RedFlag(
        severidade=Severidade.MEDIA,
        titulo="Emissão de cotas com VP/cota em queda",
        fato=(
            f"O número de cotas cresceu {formato.percentual(variacao_cotas)} em {meses} meses "
            f"enquanto o VP/cota caiu {formato.percentual(abs(variacao_vp))} — as emissões "
            "não se converteram em patrimônio por cota."
        ),
        evidencia=(
            f"cotas {formato.percentual(variacao_cotas, sinal=True)} em {meses}m; "
            f"VP/cota ajustado {formato.percentual(variacao_vp, sinal=True)} no período"
        ),
        fonte="informes mensais CVM (cotas emitidas e valor patrimonial da cota)",
        codigo=CODIGO,
    )
