"""Red flags de ETF — regras próprias da classe (as de FII não fazem sentido).

Mesma filosofia do motor de FIIs: cada alerta tem severidade, evidência
numérica e fonte; regra sem dado vira "não avaliada" (nunca aprovação
silenciosa). O selo reutiliza os 5 níveis do Scout.
"""

from __future__ import annotations

from . import formato, redflags
from .modelos import RedFlag, Severidade

# PL abaixo disso não paga os custos fixos de um ETF — gestoras encerram/deslistam
_PL_MINIMO_VIAVEL = 30_000_000.0
_PL_PEQUENO = 100_000_000.0
# volume médio diário abaixo disso = spread alto e dificuldade real de sair
_LIQUIDEZ_MINIMA = 100_000.0
_HISTORICO_CURTO_MESES = 12


def avaliar(dados: dict) -> redflags.Resultado:
    """`dados` = dicionário do montar_dados_etf (etf_html)."""
    resultado = redflags.Resultado()

    situacao = (dados.get("situacao_cvm") or "").strip()
    chave = situacao.upper()
    if chave.startswith(("EM LIQUIDA", "CANCELAD")):
        encerrando = chave.startswith("EM LIQUIDA")
        resultado.flags.append(
            RedFlag(
                severidade=Severidade.ALTA,
                titulo=(
                    "Fundo em liquidação (encerramento)"
                    if encerrando
                    else "Registro cancelado na CVM"
                ),
                fato=(
                    "O registro do fundo na CVM está como “Em Liquidação”: o fundo está "
                    "sendo encerrado — os ativos são vendidos e o dinheiro devolvido aos "
                    "cotistas. Não é um fundo em operação normal."
                    if encerrando
                    else "O registro do fundo na CVM está como “Cancelado”: o fundo encerrou. "
                    "Os dados exibidos vêm das últimas informações publicadas."
                ),
                evidencia=f'situação cadastral: "{situacao}"',
                fonte="registro de fundos da CVM (dados abertos, atualização semanal)",
                codigo="etf_situacao_cvm",
            )
        )
    elif situacao:
        resultado.aprovadas.append("registro na CVM em funcionamento normal")
    else:
        resultado.nao_avaliadas.append("situação cadastral (fora do registro FII/FIIM da CVM)")

    pl = dados.get("pl")
    if pl is None:
        resultado.nao_avaliadas.append("patrimônio líquido (sem carteira CVM ainda)")
    else:
        valor = pl["pl"]
        quando = formato.competencia_br(pl["competencia"])
        if valor < _PL_MINIMO_VIAVEL:
            resultado.flags.append(
                RedFlag(
                    severidade=Severidade.ALTA,
                    titulo="Patrimônio muito pequeno — risco de encerramento",
                    fato=(
                        f"O fundo tem {formato.moeda_compacta(valor)} de patrimônio ({quando}). "
                        "ETF desse tamanho normalmente não paga os próprios custos — o encerramento "
                        "ou a deslistagem viram uma questão de tempo, e o cotista é resgatado a "
                        "mercado, na data que não escolheu."
                    ),
                    evidencia=f"PL {formato.moeda_compacta(valor)} < {formato.moeda_compacta(_PL_MINIMO_VIAVEL)} (piso de viabilidade)",
                    fonte="carteira mensal CVM (CDA)",
                    codigo="etf_pl_inviavel",
                )
            )
        elif valor < _PL_PEQUENO:
            resultado.flags.append(
                RedFlag(
                    severidade=Severidade.MEDIA,
                    titulo="Patrimônio pequeno",
                    fato=(
                        f"O fundo tem {formato.moeda_compacta(valor)} de patrimônio ({quando}) — "
                        "abaixo do porte em que ETFs costumam se sustentar no longo prazo."
                    ),
                    evidencia=f"PL {formato.moeda_compacta(valor)} < {formato.moeda_compacta(_PL_PEQUENO)}",
                    fonte="carteira mensal CVM (CDA)",
                    codigo="etf_pl_pequeno",
                )
            )
        else:
            resultado.aprovadas.append(
                f"patrimônio ({formato.moeda_compacta(valor)}) acima do piso de viabilidade"
            )

    liquidez = dados.get("liquidez")
    if liquidez is None:
        resultado.nao_avaliadas.append("liquidez (sem volume de pregão na base)")
    elif liquidez < _LIQUIDEZ_MINIMA:
        resultado.flags.append(
            RedFlag(
                severidade=Severidade.MEDIA,
                titulo="Liquidez baixa",
                fato=(
                    f"Giram ≈{formato.moeda_compacta(liquidez)} por pregão (média dos últimos meses). "
                    "Pouca liquidez significa spread alto na compra e dificuldade real de VENDER "
                    "sem derrubar o preço."
                ),
                evidencia=f"volume médio {formato.moeda_compacta(liquidez)}/dia < {formato.moeda_compacta(_LIQUIDEZ_MINIMA)}/dia",
                fonte="COTAHIST oficial da B3 (volume financeiro)",
                codigo="etf_liquidez",
            )
        )
    else:
        resultado.aprovadas.append(
            f"liquidez saudável (≈{formato.moeda_compacta(liquidez)}/pregão)"
        )

    meses = len(dados.get("cotacao") or [])
    if meses == 0:
        resultado.nao_avaliadas.append("histórico de pregão (sem cotações na base)")
    elif meses < _HISTORICO_CURTO_MESES:
        resultado.flags.append(
            RedFlag(
                severidade=Severidade.BAIXA,
                titulo="Histórico curto de negociação",
                fato=(
                    f"Só {meses} meses de pregão — cedo demais para julgar aderência ao índice, "
                    "liquidez estável ou comportamento em crise."
                ),
                evidencia=f"{meses} meses de cotação (< {_HISTORICO_CURTO_MESES})",
                fonte="COTAHIST oficial da B3",
                codigo="etf_novo",
            )
        )
    else:
        resultado.aprovadas.append(f"histórico de pregão suficiente ({meses} meses)")

    if not dados.get("carteira"):
        resultado.flags.append(
            RedFlag(
                severidade=Severidade.BAIXA,
                titulo="Carteira não divulgada em aberto",
                fato=(
                    "O fundo não tem carteira aberta no CDA da CVM (posições confidenciais ou "
                    "ainda não publicadas) — dá para saber O QUE ele promete, mas não conferir "
                    "O QUE ele carrega."
                ),
                evidencia="sem posições no arquivo cda_fie mais recente",
                fonte="CDA/CVM",
                codigo="etf_carteira_fechada",
            )
        )
    else:
        resultado.aprovadas.append("carteira aberta e auditável no CDA da CVM")
        divergencia = dados.get("divergencia_classe")
        if divergencia:
            resultado.flags.append(
                RedFlag(
                    severidade=Severidade.BAIXA,
                    titulo="Carteira em desacordo com a classe declarada",
                    fato=(
                        "A carteira atual não bate com a classificação do fundo — pode ser "
                        "realocação em curso ou mudança de estratégia. Vale conferir no site "
                        f"da gestora. Detalhe: {divergencia}"
                    ),
                    evidencia=divergencia,
                    fonte="CDA/CVM vs curadoria Scout",
                    codigo="etf_classe_divergente",
                )
            )
        else:
            resultado.aprovadas.append("carteira coerente com a classe declarada")

    return resultado
