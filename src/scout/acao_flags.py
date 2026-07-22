"""Red flags societárias de AÇÃO (A3) — 6 regras determinísticas e auditáveis.

Benchmark obrigatório (decisão do dono, docs/ACOES.md): as regras foram
validadas retroativamente contra Americanas, IRB e Oi — se o motor não pegasse
esses casos, não estaria pronto. O SELO de ação só liga após a aprovação do
benchmark; até lá as flags existem como fatos com fonte.

Matéria-prima: dfp_meta (entrega/versão/capital/parecer estruturado da própria
CVM no zip da DFP), auditores (FCA, janelas de atuação), fundamentos (lucro) e
acao_proventos. "Sem dado = não avaliada", nunca aprovação silenciosa.
"""

from __future__ import annotations

from datetime import date

from . import formato, redflags
from .modelos import RedFlag, Severidade

_FONTE_DFP = "CVM — DFP (dados abertos, dfp_cia_aberta)"


def avaliar(dados: dict, hoje: date | None = None) -> redflags.Resultado:
    """`dados`: empresa (row), balancos (asc), metas (dfp_meta asc por ano),
    auditores (rows FCA), proventos_ano_por_ticker ({ticker: {ano: R$/ação}})."""
    hoje = hoje or date.today()
    resultado = redflags.Resultado()
    metas = list(dados.get("metas") or [])
    balancos = list(dados.get("balancos") or [])
    ultima = metas[-1] if metas else None

    # --- 1. Parecer do auditor (classificação estruturada da própria CVM) ----
    nome = "Parecer do auditor com ressalva/adverso"
    if ultima is None or not (ultima["parecer_tipo"] or "").strip():
        resultado.nao_avaliadas.append(nome)
    else:
        tipo = ultima["parecer_tipo"].strip()
        continuidade = bool(ultima["parecer_continuidade"])
        if tipo != "Sem Ressalva" or continuidade:
            grave = tipo in ("Adverso", "Negativa de Opinião") or continuidade
            detalhe = " + incerteza de continuidade operacional" if continuidade else ""
            resultado.flags.append(
                RedFlag(
                    severidade=Severidade.ALTA if grave else Severidade.MEDIA,
                    titulo=f"Parecer do auditor: {tipo}{detalhe}",
                    fato=(
                        f"O relatório do auditor independente sobre a DFP de {ultima['ano']} "
                        f"foi classificado como '{tipo}'"
                        + (
                            " e o texto aponta incerteza relevante de continuidade operacional"
                            if continuidade
                            else ""
                        )
                        + " — em companhia aberta, isso é um evento grave que merece leitura."
                    ),
                    evidencia=f"TP_RELAT_AUD='{tipo}' · exercício {ultima['ano']}"
                    + (f" · trecho: “{ultima['parecer_trecho']}”" if ultima["parecer_trecho"] else ""),
                    fonte=_FONTE_DFP + " — relatório do auditor (parecer)",
                )
            )
        else:
            resultado.aprovadas.append("Parecer do auditor sem ressalvas no último exercício")

    # --- 2. Balanço reapresentado (republicação) -----------------------------
    nome = "Balanço reapresentado"
    if ultima is None or not ultima["versao"]:
        resultado.nao_avaliadas.append(nome)
    elif int(ultima["versao"]) > 1:
        resultado.flags.append(
            RedFlag(
                severidade=Severidade.MEDIA,
                titulo="Balanço reapresentado à CVM",
                fato=(
                    f"A DFP de {ultima['ano']} está na versão {ultima['versao']} — a companhia "
                    "reapresentou o documento depois da entrega original. Reapresentação tem "
                    "motivos legítimos, mas historicamente acompanha revisões relevantes de números."
                ),
                evidencia=f"VERSAO={ultima['versao']} na DFP de {ultima['ano']}",
                fonte=_FONTE_DFP,
            )
        )
    else:
        resultado.aprovadas.append("DFP do último exercício sem reapresentação")

    # --- 3. Atraso na entrega da DFP (prazo legal: 3 meses do fim do exercício)
    nome = "Atraso na entrega da DFP"
    if ultima is None or not ultima["dt_receb"]:
        resultado.nao_avaliadas.append(nome)
    else:
        prazo = date(int(ultima["ano"]) + 1, 3, 31)
        entrega = date.fromisoformat(ultima["dt_receb"][:10])
        atraso = (entrega - prazo).days
        if atraso > 0:
            resultado.flags.append(
                RedFlag(
                    severidade=Severidade.ALTA if atraso > 60 else Severidade.MEDIA,
                    titulo=f"DFP entregue {atraso} dias após o prazo",
                    fato=(
                        f"A DFP de {ultima['ano']} foi entregue em {formato.dia_br(ultima['dt_receb'][:10])} — "
                        f"o prazo legal era {formato.dia_br(prazo.isoformat())} (3 meses após o fim do "
                        "exercício). Atraso na prestação de contas costuma sinalizar problema interno."
                    ),
                    evidencia=f"DT_RECEB={ultima['dt_receb'][:10]} · prazo 31/03 · {atraso} dias de atraso",
                    fonte=_FONTE_DFP,
                )
            )
        else:
            resultado.aprovadas.append("DFP do último exercício entregue no prazo")

    # --- 4. Diluição por emissão (ações novas sem lucro acompanhando) --------
    # Salvaguardas contra falso-positivo (validadas na base real): (a) empresas
    # preenchem a composição ora em MILHARES ora em UNIDADES entre anos — razão
    # implausível (>3x) é mudança de unidade, não emissão; (b) desdobramento/
    # grupamento/bonificação multiplica ações SEM diluir — evento societário B3
    # entre os exercícios invalida a comparação crua.
    nome = "Diluição relevante por emissão de ações"
    serie_acoes = [(m["ano"], m["acoes_total"]) for m in metas if m["acoes_total"]]
    evento_no_meio = False
    if len(serie_acoes) >= 2:
        ano_a, ano_b = serie_acoes[-2][0], serie_acoes[-1][0]
        for evento in dados.get("eventos") or []:
            rotulo = (evento["label"] or "").upper()
            data = (evento["data"] or "")[:10]
            if any(m in rotulo for m in ("DESDOBRA", "GRUPAMENTO", "BONIFICA")) and (
                f"{ano_a}-12-31" < data <= f"{ano_b}-12-31"
            ):
                evento_no_meio = True
    if len(serie_acoes) < 2:
        resultado.nao_avaliadas.append(nome)
    elif evento_no_meio:
        resultado.nao_avaliadas.append(nome + " (evento societário no período distorce a comparação)")
    else:
        (ano_a, antes), (ano_b, depois) = serie_acoes[-2], serie_acoes[-1]
        crescimento = 100 * (depois - antes) / antes if antes else 0
        if crescimento > 200 or (antes and depois / antes < 1 / 3):
            # razão implausível: quase certo que a companhia mudou a unidade
            # (mil ↔ unidade) no informe — dado inconsistente não vira alerta
            resultado.nao_avaliadas.append(nome + " (unidade inconsistente no informe da CVM)")
        elif crescimento > 20:
            lucros = {b["ano"]: b["lucro_liquido"] for b in balancos}
            lpa_antes = (lucros.get(ano_a) or 0) / antes if antes else None
            lpa_depois = (lucros.get(ano_b) or 0) / depois if depois else None
            detalhe_lpa = ""
            if lpa_antes and lpa_depois is not None and lpa_depois < lpa_antes:
                detalhe_lpa = (
                    f" · lucro por ação caiu de R$ {formato.decimal(lpa_antes)} para "
                    f"R$ {formato.decimal(lpa_depois)} no período"
                )
            resultado.flags.append(
                RedFlag(
                    severidade=Severidade.MEDIA,
                    titulo=f"Base de ações cresceu {formato.percentual(crescimento)} entre {ano_a} e {ano_b}",
                    fato=(
                        f"O total de ações integralizadas cresceu {formato.percentual(crescimento)} "
                        f"no período. Pode ser emissão (dilui quem não acompanha), incorporação/fusão "
                        "ou reestruturação societária — confira o evento no RI da companhia. "
                        "A pergunta que importa: o lucro acompanhou o número de ações?"
                    ),
                    evidencia=(
                        f"{formato.moeda_compacta(antes).replace('R$ ', '')} → "
                        f"{formato.moeda_compacta(depois).replace('R$ ', '')} ações{detalhe_lpa}"
                    ),
                    fonte=_FONTE_DFP + " — composição do capital",
                )
            )
        else:
            resultado.aprovadas.append("Base de ações estável no último exercício (sem diluição relevante)")

    # --- 5. Proventos num ano de prejuízo -------------------------------------
    nome = "Proventos pagos em ano de prejuízo"
    proventos = dados.get("proventos_ano_por_ticker") or {}
    lucros = {b["ano"]: b["lucro_liquido"] for b in balancos if b["lucro_liquido"] is not None}
    if not proventos or not lucros:
        resultado.nao_avaliadas.append(nome)
    else:
        caso = None
        for ticker, por_ano in proventos.items():
            for ano, valor in sorted(por_ano.items()):
                if ano in lucros and lucros[ano] <= 0 and valor > 0.01:
                    caso = (ticker, ano, valor, lucros[ano])
        if caso:
            ticker_c, ano_c, valor_c, lucro_c = caso
            resultado.flags.append(
                RedFlag(
                    severidade=Severidade.MEDIA,
                    titulo=f"Distribuiu proventos num ano de prejuízo ({ano_c})",
                    fato=(
                        f"{ticker_c} pagou R$ {formato.decimal(valor_c)}/ação em proventos com data-com "
                        f"em {ano_c}, ano em que a companhia reportou prejuízo de "
                        f"{formato.moeda_compacta(abs(lucro_c))}. Distribuir sem lucro consome caixa "
                        "ou reservas — não se sustenta indefinidamente."
                    ),
                    evidencia=(
                        f"proventos {ano_c}: R$ {formato.decimal(valor_c)}/ação · "
                        f"lucro líquido {ano_c}: -{formato.moeda_compacta(abs(lucro_c)).replace('R$ ', 'R$ ')}"
                    ),
                    fonte="B3 (proventos) + CVM DFP (lucro)",
                )
            )
        else:
            resultado.aprovadas.append("Proventos compatíveis com anos de lucro (nenhum pagamento em ano de prejuízo)")

    # --- 6. Troca frequente de auditor ----------------------------------------
    nome = "Troca frequente de auditor"
    auditores = list(dados.get("auditores") or [])
    if not auditores:
        resultado.nao_avaliadas.append(nome)
    else:
        corte = hoje.year - 5
        recentes = {
            (a["auditor"] or "").strip().upper()
            for a in auditores
            if a["inicio"] and a["inicio"][:4].isdigit() and int(a["inicio"][:4]) >= corte
        }
        if len(recentes) >= 3:
            resultado.flags.append(
                RedFlag(
                    severidade=Severidade.MEDIA,
                    titulo=f"{len(recentes)} auditores diferentes em 5 anos",
                    fato=(
                        f"A companhia iniciou relação com {len(recentes)} firmas de auditoria "
                        f"distintas desde {corte}. O rodízio obrigatório troca o auditor a cada "
                        "5 anos — mais trocas que isso merece atenção (divergência com auditor é "
                        "um clássico de problema contábil)."
                    ),
                    evidencia="auditores com início desde "
                    f"{corte}: {', '.join(sorted(recentes))[:180]}",
                    fonte="CVM — FCA (Formulário Cadastral, auditores com janela de atuação)",
                )
            )
        else:
            resultado.aprovadas.append("Sem rodízio anormal de auditores nos últimos 5 anos")

    resultado.flags.sort(key=lambda f: {Severidade.ALTA: 0, Severidade.MEDIA: 1, Severidade.BAIXA: 2}[f.severidade])
    return resultado
