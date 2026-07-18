"""Regra: rendimento interrompido ou irregular nos últimos 12 meses."""

from __future__ import annotations

from ..modelos import RedFlag, Severidade
from .contexto import Contexto

CODIGO = "rendimento"
NOME = "regularidade dos rendimentos"
OK = "rendimentos distribuídos com regularidade nos últimos 12 meses"

_MESES_MINIMOS = 10
_MESES_CRITICOS = 6


def aplicavel(ctx: Contexto) -> bool:
    return ctx.meses_com_distribuicao_12m() is not None


def avaliar(ctx: Contexto) -> RedFlag | None:
    meses = ctx.meses_com_distribuicao_12m()
    if meses >= _MESES_MINIMOS:
        return None
    return RedFlag(
        severidade=Severidade.MEDIA if meses <= _MESES_CRITICOS else Severidade.BAIXA,
        titulo="Rendimentos irregulares",
        fato=(
            f"O fundo distribuiu rendimentos em apenas {meses} dos últimos 12 meses. "
            "Pode ser política do fundo (distribuição semestral, por exemplo) ou "
            "dificuldade de geração de caixa — os relatórios dizem qual dos dois."
        ),
        evidencia=f"{meses}/12 meses com dividend yield declarado acima de zero",
        fonte="informes mensais CVM (dividend yield mensal)",
        codigo=CODIGO,
    )
