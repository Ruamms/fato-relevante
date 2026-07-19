"""Regra: rendimentos declarados acima do resultado financeiro (exata).

Usa o resultado contábil/financeiro do informe trimestral — o número
oficial, sem proxy: soma dos últimos 4 trimestres de rendimento
declarado vs resultado financeiro líquido gerado.
"""

from __future__ import annotations

from .. import formato
from ..modelos import RedFlag, Severidade
from .contexto import Contexto

CODIGO = "distribuicao_exata"
NOME = "rendimentos declarados vs resultado financeiro"
OK = "rendimentos declarados dentro do resultado financeiro gerado (últimos 4 trimestres)"

_TOLERANCIA = 1.05  # 5%: reservas acumuladas permitem distribuir um pouco acima


def aplicavel(ctx: Contexto) -> bool:
    return (
        ctx.rendimentos_declarados_4t() is not None
        and ctx.resultado_financeiro_4t() is not None
        and ctx.rendimentos_declarados_4t() > 0
    )


def avaliar(ctx: Contexto) -> RedFlag | None:
    rendimentos = ctx.rendimentos_declarados_4t()
    resultado = ctx.resultado_financeiro_4t()
    if resultado > 0 and rendimentos <= resultado * _TOLERANCIA:
        return None
    # refinamento: o informe traz o resultado ACUMULADO (a "reserva") — se ele
    # cobre o excesso, a distribuição é sobra retida de períodos anteriores
    # (ex.: venda de imóvel), não consumo de patrimônio
    acumulado = ctx.resultado_acumulado_atual()
    excesso = rendimentos - max(resultado, 0)
    if acumulado is not None and acumulado > 0 and excesso <= acumulado:
        return None
    if resultado <= 0:
        fato = (
            f"O fundo declarou {formato.moeda_compacta(rendimentos)} em rendimentos nos "
            "últimos 4 trimestres com resultado financeiro NEGATIVO "
            f"({formato.moeda_compacta(resultado)}) — a distribuição está saindo de "
            "reservas ou do patrimônio, não do resultado."
        )
        severidade = Severidade.ALTA
    else:
        razao = rendimentos / resultado
        fato = (
            f"O fundo declarou {formato.moeda_compacta(rendimentos)} em rendimentos nos "
            f"últimos 4 trimestres, {formato.percentual((razao - 1) * 100)} acima do "
            f"resultado financeiro gerado ({formato.moeda_compacta(resultado)}). Pode ser "
            "distribuição legítima de lucros acumulados em períodos anteriores (ex.: venda "
            "de imóveis) — os relatórios do fundo dizem se é sustentável."
        )
        # acima do resultado com resultado positivo é ponto de investigação (MÉDIA);
        # ALTA fica para o caso indefensável: distribuir com resultado negativo
        severidade = Severidade.MEDIA
    reserva = (
        f"; resultado acumulado (reserva) {formato.moeda_compacta(acumulado)} não cobre o excesso"
        if acumulado is not None
        else "; resultado acumulado não informado"
    )
    return RedFlag(
        severidade=severidade,
        titulo="Rendimentos acima do resultado financeiro",
        fato=fato,
        evidencia=(
            f"rendimentos declarados 4T {formato.moeda_compacta(rendimentos)} vs "
            f"resultado financeiro líquido 4T {formato.moeda_compacta(resultado)}{reserva}"
        ),
        fonte="informe trimestral CVM (resultado contábil/financeiro)",
        codigo=CODIGO,
    )
