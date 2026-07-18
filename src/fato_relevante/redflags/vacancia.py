"""Regra: vacância física alta (imóveis vazios não pagam aluguel)."""

from __future__ import annotations

from .. import formato
from ..modelos import RedFlag, Severidade
from .contexto import Contexto

CODIGO = "vacancia"
NOME = "vacância dos imóveis"
OK = "vacância dos imóveis abaixo dos limiares de alerta"

_VACANCIA_MEDIA = 15.0
_VACANCIA_ALTA = 30.0


def aplicavel(ctx: Contexto) -> bool:
    return ctx.vacancia_atual() is not None


def avaliar(ctx: Contexto) -> RedFlag | None:
    vacancia = ctx.vacancia_atual()
    if vacancia < _VACANCIA_MEDIA:
        return None
    vagos = sum(
        1
        for linha in ctx.imoveis_atuais
        if linha["vacancia"] is not None and linha["vacancia"] >= 0.5
    )
    total = len(ctx.imoveis_atuais)
    return RedFlag(
        severidade=Severidade.ALTA if vacancia >= _VACANCIA_ALTA else Severidade.MEDIA,
        titulo="Vacância física alta",
        fato=(
            f"{formato.percentual(vacancia)} da área dos imóveis está vaga "
            f"({vagos} de {total} imóveis com metade ou mais da área vazia) — "
            "área vaga não gera aluguel e ainda gera custo de condomínio e IPTU."
        ),
        evidencia=(
            f"vacância ponderada por área {formato.percentual(vacancia)} no trimestre "
            f"mais recente; limiar de alerta: {formato.percentual(_VACANCIA_MEDIA)}"
        ),
        fonte="informe trimestral CVM (vacância por imóvel)",
        codigo=CODIGO,
    )
