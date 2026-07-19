"""Regra: situação do registro do fundo na CVM.

O registro de fundos da CVM (dados abertos) traz a situação cadastral.
"Em Liquidação" = o fundo está sendo ENCERRADO: vende os ativos e devolve
o dinheiro aos cotistas. "Cancelado" = o registro já foi baixado. Um fundo
em liquidação continua enviando informes mensais normalmente — por isso o
corte de atividade (informe recente) não pega esses casos; esta regra pega.
"""

from __future__ import annotations

from ..modelos import RedFlag, Severidade
from .contexto import Contexto

CODIGO = "situacao_cvm"
NOME = "situação do registro na CVM"
OK = "registro na CVM em funcionamento normal"

_EM_LIQUIDACAO = "EM LIQUIDA"
_CANCELADO = "CANCELAD"


def aplicavel(ctx: Contexto) -> bool:
    return bool((ctx.situacao_cvm or "").strip())


def avaliar(ctx: Contexto) -> RedFlag | None:
    situacao = (ctx.situacao_cvm or "").strip()
    chave = situacao.upper()
    if chave.startswith(_EM_LIQUIDACAO):
        return RedFlag(
            severidade=Severidade.ALTA,
            titulo="Fundo em liquidação (encerramento)",
            fato=(
                "O registro do fundo na CVM está como “Em Liquidação”: o fundo está "
                "sendo encerrado — os ativos são vendidos e o dinheiro devolvido aos "
                "cotistas. Não é um fundo em operação normal; indicadores e histórico "
                "descrevem um fundo que está deixando de existir."
            ),
            evidencia=f'situação cadastral: "{situacao}"',
            fonte="registro de fundos da CVM (dados abertos, atualização semanal)",
            codigo=CODIGO,
        )
    if chave.startswith(_CANCELADO):
        return RedFlag(
            severidade=Severidade.ALTA,
            titulo="Registro cancelado na CVM",
            fato=(
                "O registro do fundo na CVM está como “Cancelado”: o fundo encerrou. "
                "Os dados exibidos vêm dos últimos informes enviados antes do fim."
            ),
            evidencia=f'situação cadastral: "{situacao}"',
            fonte="registro de fundos da CVM (dados abertos, atualização semanal)",
            codigo=CODIGO,
        )
    return None  # Em Funcionamento Normal (e pré-operacional: coberto por "fundo novo")
