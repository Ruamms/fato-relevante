"""Página de AÇÃO — raio-x da EMPRESA visto pelo papel consultado.

Decisão do roadmap (A4): página por EMPRESA com N papéis. Cada papel (PETR3,
PETR4…) tem a sua URL e mostra a mesma empresa — múltiplos do papel consultado
em destaque (P/L, P/VP e DY dependem do preço DAQUELE papel) e os papéis irmãos
com link. A carteirinha de regras explica a classe para leigo (isenção dos
R$ 20 mil, JCP tributado, ON vs PN vs unit). Tudo factual, com fonte — nunca
recomendação.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from .. import analise, armazenamento, formato, series
from . import graficos
from .html import CSS_MARCA, TAG_FAVICON, _e, marca_html

# carteirinha de regras da classe — linguagem de leigo, fatos com fonte
REGRAS_ACOES = (
    "Uma ação = um pedaço da empresa. O retorno vem de dois lugares: valorização "
    "do preço e proventos (dividendos e JCP).",
    "IR na venda: 15% sobre o ganho em operações comuns — mas vendas de até "
    "R$ 20 mil/MÊS (somando todas as ações) são ISENTAS (Lei 9.250/1995, art. 22). "
    "Day trade não tem isenção e paga 20%.",
    "Dividendos chegam LÍQUIDOS (isentos de IR hoje). JCP (juros sobre capital "
    "próprio) chega com 15% retido na fonte — o valor anunciado não é o valor "
    "que cai na conta.",
    "ON (final 3) = ação ordinária, dá direito a VOTO e ao tag along mínimo de "
    "80% em venda de controle. PN (final 4) = preferencial, prioridade nos "
    "proventos mas em geral sem voto. UNIT (final 11) = pacote com ON+PN juntas.",
    "O preço aqui é o fechamento oficial da B3 do último pregão (D-1) — não é "
    "cotação em tempo real.",
)

_RODAPE = (
    "Isto não é recomendação de investimento. Fontes: B3 (cotações oficiais "
    "COTAHIST, listagem, eventos e proventos) e CVM (cadastro de companhias e "
    "demonstrações financeiras padronizadas — DFP). Regras tributárias citadas "
    "em caráter informativo — confirme com um contador."
)


def montar_dados_acao(con: sqlite3.Connection, ticker: str, hoje: date | None = None) -> dict | None:
    """Reúne tudo que a página da ação precisa; None se o ticker não for um
    papel conhecido (escopo v1 = IBrX-100)."""
    from ..coleta import fundamentos as modulo_fundamentos

    hoje = hoje or date.today()
    ticker = ticker.strip().upper()
    empresa = armazenamento.empresa_por_ticker(con, ticker)
    if empresa is None:
        return None
    papeis = armazenamento.papeis_da_empresa(con, empresa["cod_cvm"])
    balancos = armazenamento.fundamentos_da_empresa(con, empresa["cod_cvm"])
    indicadores = modulo_fundamentos.indicadores(balancos[-1]) if balancos else {}

    cotacoes = armazenamento.serie_cotacoes(con, ticker)
    cotacao = [(l["competencia"], l["fechamento"]) for l in cotacoes if l["fechamento"]]
    ajustado = [
        (l["competencia"], l["fechamento_ajustado"]) for l in cotacoes if l["fechamento_ajustado"]
    ]
    indices = {nome: armazenamento.serie_indice(con, nome) for nome in ("CDI", "IPCA")}
    meta = armazenamento.cotacao_meta(con, ticker)

    # múltiplos de TODOS os papéis da empresa (cada um com o seu preço)
    multiplos_por_papel = {
        p["ticker"]: {
            **modulo_fundamentos.multiplos_do_papel(con, p["ticker"], hoje),
            "tipo": p["tipo"],
            "preco": (m["preco_atual"] if (m := armazenamento.cotacao_meta(con, p["ticker"])) else None),
            "proventos_12m": armazenamento.proventos_12m(con, p["ticker"], hoje),
        }
        for p in papeis
    }

    ultimo_provento = con.execute(
        "SELECT * FROM acao_proventos WHERE ticker = ? ORDER BY data_com DESC LIMIT 1",
        (ticker,),
    ).fetchone()

    # red flags societárias (A3, benchmarkadas) + selo — mesmos 5 níveis de FII/ETF
    from .. import acao_flags, redflags

    resultado_flags = acao_flags.avaliar(
        {
            "empresa": empresa,
            "balancos": balancos,
            "metas": armazenamento.dfp_meta_da_empresa(con, empresa["cod_cvm"]),
            "auditores": armazenamento.auditores_da_empresa(con, empresa["cod_cvm"]),
            "proventos_ano_por_ticker": {
                p["ticker"]: armazenamento.proventos_por_ano(con, p["ticker"]) for p in papeis
            },
            "eventos": con.execute(
                f"SELECT data, label, fator FROM acao_eventos WHERE ticker IN "
                f"({','.join('?' * len(papeis))})",
                [p["ticker"] for p in papeis],
            ).fetchall(),
        },
        hoje=hoje,
    )

    return {
        "flags": resultado_flags,
        "selo": redflags.selo(resultado_flags),
        "ticker": ticker,
        "empresa": empresa,
        "papeis": papeis,
        "balancos": balancos,
        "indicadores": indicadores,
        "multiplos": multiplos_por_papel,
        "cotacao": cotacao,
        "preco_atual": meta["preco_atual"] if meta else None,
        "cotado_em": meta["cotado_em"] if meta else None,
        "variacao_12m": series.variacao_pct(
            [{"competencia": c, "fechamento": v} for c, v in ajustado], "fechamento", 12
        ),
        "rentabilidade": analise._rentabilidades(cotacao, ajustado, indices),
        "ultimo_provento": ultimo_provento,
        "liquidez": armazenamento.liquidez_recente(con, ticker),
    }


def _trunca(texto: str, limite: int) -> str:
    texto = (texto or "").strip()
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _setor_curto(empresa) -> str:
    """Setor legível: o setor_b3 vem como 'A / B / C' — o 1º nível já orienta."""
    bruto = (empresa["setor_b3"] or empresa["setor_cvm"] or "").strip()
    return bruto.split("/")[0].strip().rstrip(".") if bruto else "—"


def gerar(
    dados: dict,
    agora: datetime | None = None,
    com_menu: bool = False,
    leitura: dict | None = None,
    publicados: set[str] | None = None,
) -> str:
    from .html import (
        CSS_BUSCA_TOPO,
        CSS_MENU,
        JS_BUSCA_TOPO,
        JS_GRAFICO_HOVER,
        JS_MENU,
        _secao_ia,
        _secao_parecer,
        menu_html,
    )

    agora = agora or datetime.now()
    menu = menu_html() if com_menu else ""
    css_menu = (CSS_MENU + CSS_BUSCA_TOPO) if com_menu else ""
    js_menu = (JS_MENU + JS_BUSCA_TOPO) if com_menu else ""
    empresa = dados["empresa"]
    ticker = dados["ticker"]
    ind = dados["indicadores"]
    financeiro = bool(ind.get("setor_financeiro"))
    balancos = dados["balancos"]
    ultimo = balancos[-1] if balancos else None
    mult = dados["multiplos"].get(ticker, {})

    def _ajuda(_: str) -> str:  # glossário das ações entra num passo futuro
        return ""

    cards = []

    def _card(nome: str, valor: str, extra: str = "") -> None:
        extra_html = f'<div class="extra">{extra}</div>' if extra else ""
        cards.append(
            f'<div class="card"><div class="nome">{nome}{_ajuda(nome)}</div>'
            f'<div class="valor">{valor}</div>{extra_html}</div>'
        )

    if dados["preco_atual"]:
        quando = (dados["cotado_em"] or "")[:10]
        _card("Cotação (fechamento oficial)", f"R$ {formato.decimal(dados['preco_atual'])}",
              f"pregão de {formato.dia_br(quando) if quando else '—'}")
    if dados["variacao_12m"] is not None:
        _card("Variação 12 meses", formato.percentual(dados["variacao_12m"], sinal=True),
              "preço ajustado por eventos e proventos")
    if mult.get("pl") is not None:
        _card("P/L", formato.decimal(mult["pl"]), "preço ÷ lucro por ação (último anual)")
    elif ultimo is not None and (ultimo["lucro_liquido"] or 0) <= 0:
        _card("P/L", "—", "empresa em prejuízo no último anual: P/L não se aplica")
    if mult.get("pvp") is not None:
        _card("P/VP", formato.decimal(mult["pvp"]), "preço ÷ valor patrimonial por ação")
    if mult.get("dy") is not None and mult.get("preco"):
        _card("Dividend yield 12m", formato.percentual(mult["dy"]),
              f"R$ {formato.decimal(mult.get('proventos_12m') or 0)}/ação em proventos (data-com)")
    if ind.get("roe") is not None:
        _card("ROE", formato.percentual(ind["roe"]), f"lucro ÷ patrimônio · anual {ultimo['ano']}")
    if ind.get("margem_liquida") is not None:
        _card("Margem líquida", formato.percentual(ind["margem_liquida"]),
              f"lucro ÷ receita · anual {ultimo['ano']}")
    if ind.get("ebitda") is not None:
        _card("EBITDA", formato.moeda_compacta(ind["ebitda"]),
              f"margem {formato.percentual(ind['margem_ebitda'])} · anual {ultimo['ano']}"
              if ind.get("margem_ebitda") is not None else f"anual {ultimo['ano']}")
    if ind.get("divida_liquida") is not None:
        rotulo_div = "caixa líquido" if ind["divida_liquida"] < 0 else "dívida líquida"
        extra_div = (
            f"{formato.decimal(ind['divida_liquida_pl'])}× o patrimônio líquido"
            if ind.get("divida_liquida_pl") is not None
            else ""
        )
        _card(rotulo_div.capitalize(), formato.moeda_compacta(abs(ind["divida_liquida"])), extra_div)
    if ultimo is not None and ultimo["lucro_liquido"] is not None:
        _card("Lucro líquido", formato.moeda_compacta(ultimo["lucro_liquido"]),
              f"anual {ultimo['ano']} (DFP consolidada)")
    if dados["liquidez"]:
        _card("Liquidez", f"{formato.moeda_compacta(dados['liquidez'])}/dia",
              "volume financeiro médio por pregão (3 meses)")
    if financeiro:
        _card("Setor financeiro", '<span class="compacto">banco/seguradora</span>',
              "margem bruta, EBITDA e dívida não se aplicam ao modelo contábil")

    # --- papéis da empresa (cada um com o seu preço e múltiplos) -------------
    linhas_papeis = []
    for p in dados["papeis"]:
        t = p["ticker"]
        m = dados["multiplos"].get(t, {})
        atual = " ◀" if t == ticker else ""
        nome_papel = (
            f"<b>{_e(t)}</b>{atual}"
            if t == ticker
            else (f'<a href="{_e(t)}.html">{_e(t)}</a>' if (publicados and t in publicados) else _e(t))
        )
        fmt = lambda v, f=formato.decimal: f(v) if v is not None else "—"  # noqa: E731
        linhas_papeis.append(
            f"<tr><td>{nome_papel}</td><td>{_e(p['tipo'] or '—')}</td>"
            f"<td>{'R$ ' + formato.decimal(m['preco']) if m.get('preco') else '—'}</td>"
            f"<td>{fmt(m.get('pl'))}</td><td>{fmt(m.get('pvp'))}</td>"
            f"<td>{fmt(m.get('dy'), formato.percentual)}</td></tr>"
        )
    secao_papeis = f"""
  <h2>Papéis da empresa</h2>
  <div class="grafico">
  <table class="imoveis">
    <thead><tr><th>papel</th><th>tipo</th><th>preço (D-1)</th><th>P/L</th><th>P/VP</th><th>DY 12m</th></tr></thead>
    <tbody>{''.join(linhas_papeis)}</tbody>
  </table>
  <div class="nota">mesma empresa, preços independentes por papel — P/L, P/VP e DY seguem o preço de cada um</div>
  </div>
"""

    # --- balanço anual (série de até 4 anos, DFP consolidada) ----------------
    secao_balanco = ""
    if balancos:
        from ..coleta import fundamentos as modulo_fundamentos

        def _dinheiro(v):
            return formato.moeda_compacta(v) if v is not None else "—"

        def _pct(v):
            return formato.percentual(v) if v is not None else "—"

        linhas_anos = []
        for b in balancos:
            i = modulo_fundamentos.indicadores(b)
            colunas = [str(b["ano"]), _dinheiro(b["receita"]), _dinheiro(b["lucro_liquido"]),
                       _pct(i.get("margem_liquida")), _pct(i.get("roe"))]
            if not financeiro:
                colunas += [_dinheiro(i.get("ebitda")), _dinheiro(i.get("divida_liquida"))]
            colunas += [_dinheiro(b["patrimonio_liquido"])]
            linhas_anos.append("<tr>" + "".join(f"<td>{c}</td>" for c in colunas) + "</tr>")
        cab = ["ano", "receita", "lucro líquido", "margem líq.", "ROE"]
        if not financeiro:
            cab += ["EBITDA", "dívida líquida"]
        cab += ["patrimônio líquido"]
        cabecalho = "".join(f"<th>{c}</th>" for c in cab)

        grafico_resultado = ""
        serie_receita = [(str(b["ano"]), b["receita"]) for b in balancos if b["receita"] is not None]
        serie_lucro = [(str(b["ano"]), b["lucro_liquido"]) for b in balancos if b["lucro_liquido"] is not None]
        series_plot = [s for s in (("Receita", serie_receita), ("Lucro líquido", serie_lucro)) if len(s[1]) >= 2]
        if series_plot:
            svg = graficos.grafico_linhas(series_plot, formatador=formato.moeda_compacta)
            if svg:
                grafico_resultado = f'<div class="grafico"><h3>Receita × Lucro líquido (anual)</h3>{svg}</div>'

        secao_balanco = f"""
  <h2>Balanço anual (DFP)</h2>
  <div class="grafico">
  <table class="imoveis">
    <thead><tr>{cabecalho}</tr></thead>
    <tbody>{''.join(linhas_anos)}</tbody>
  </table>
  <div class="nota">demonstrações financeiras padronizadas (CVM), consolidado · valores do exercício
  {"· banco/seguradora: EBITDA e dívida não se aplicam" if financeiro else ""}</div>
  </div>
  {grafico_resultado}
"""

    grafico_cotacao = ""
    if dados["cotacao"]:
        svg = graficos.grafico_linhas(
            [("Cotação", dados["cotacao"])],
            formatador=lambda v: f"R$ {formato.decimal(v)}",
        )
        if svg:
            grafico_cotacao = (
                f'<h2>Gráficos</h2><div class="grafico"><h3>Cotação (fechamento oficial B3)</h3>{svg}</div>'
            )

    rentabilidade = ""
    janela_maxima = dados["rentabilidade"].get("máximo") or dados["rentabilidade"].get("12 meses")
    if janela_maxima and "com" in janela_maxima:
        svg = graficos.grafico_linhas(
            janela_maxima["com"], formatador=lambda v: formato.percentual(v)
        )
        if svg:
            rentabilidade = (
                f'<div class="grafico"><h3>Rentabilidade acumulada × CDI × IPCA</h3>{svg}'
                '<div class="nota">retorno total (preço ajustado por eventos + proventos '
                "reinvestidos) · índices: Banco Central</div></div>"
            )

    itens_regras = "".join(f"<li>{_e(regra)}</li>" for regra in REGRAS_ACOES)
    ultimo_prov = dados["ultimo_provento"]
    if ultimo_prov:
        itens_regras += (
            f"<li><b>Último provento deste papel:</b> {_e(ultimo_prov['label'] or 'provento')} de "
            f"R$ {formato.decimal(ultimo_prov['valor'])}/ação (data-com "
            f"{formato.dia_br(ultimo_prov['data_com'])}) — fonte: B3.</li>"
        )

    from .html import _COR_SELO, _COR_SEVERIDADE

    selo_html = ""
    if dados.get("selo"):
        cor = _COR_SELO.get(dados["selo"].nivel, "#7C8894")
        selo_html = (
            f'<span class="selo" style="background:{cor}" title="{_e(dados["selo"].descricao)}">'
            f"{_e(dados['selo'].rotulo)}</span>"
        )

    flags_html = ""
    if dados.get("flags"):
        resultado = dados["flags"]
        partes = []
        for flag in resultado.flags:
            cor = _COR_SEVERIDADE[flag.severidade]
            partes.append(
                f'<div class="flag" style="border-left-color:{cor}">'
                f'<span class="sev" style="color:{cor}">{_e(flag.severidade.value)}</span>'
                f"<h3>{_e(flag.titulo)}</h3><p>{_e(flag.fato)}</p>"
                f'<p class="evid">evidência: {_e(flag.evidencia)}</p>'
                f'<p class="fonte">fonte: {_e(flag.fonte)}</p></div>'
            )
        if not partes and resultado.aprovadas:
            partes.append('<p class="ok">✓ nenhum alerta disparado</p>')
        if resultado.aprovadas:
            itens_ok = "".join(f"<li>{_e(texto)}</li>" for texto in resultado.aprovadas)
            partes.append(
                '<p class="ok">✓ Verificações que rodaram e passaram sem alerta:</p>'
                f'<ul class="ok">{itens_ok}</ul>'
            )
        for pendente in resultado.nao_avaliadas:
            partes.append(f'<p class="na">· não avaliada: {_e(pendente)}</p>')
        flags_html = f"<h2>🚩 Red flags</h2>{''.join(partes)}"

    auditor = (empresa["auditor"] or "").strip()
    meta_auditor = f" · auditor: {_e(_trunca(auditor, 40))}" if auditor else ""
    situacao = (empresa["situacao"] or "").strip().upper()
    aviso_situacao = (
        f'<span class="selo" style="background:#DB7A7A">{_e(situacao.title())}</span>'
        if situacao and situacao != "ATIVO"
        else ""
    )

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(ticker)} — Scout</title>
{TAG_FAVICON}
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing:border-box; margin:0; }}
body {{ background:#0F1416; color:#EAEEF0; font-family:system-ui,sans-serif; line-height:1.5; }}
.pagina {{ max-width:960px; margin:0 auto; padding:28px 20px 40px; }}
h1 {{ font-family:'Scout Display',system-ui,sans-serif; font-size:28px; font-weight:700; letter-spacing:-.02em; margin:6px 0 2px; }} h1 small {{ color:#9AA7B2; font-size:15px; font-weight:400; }}
h2 {{ font-family:'Scout Display',system-ui,sans-serif; font-size:22px; font-weight:700; letter-spacing:-.01em; margin:26px 0 10px; }}
a {{ color:#8FCB9B; }}
.meta {{ color:#9AA7B2; font-size:13px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr)); gap:10px; margin:20px 0; }}
.card {{ background:#161D20; border:1px solid #1B2225; border-radius:10px; padding:12px 14px; }}
.card .nome {{ color:#9AA7B2; font-size:12px; text-transform:uppercase; letter-spacing:.06em; }}
.card .valor {{ font-family:'Scout Display',system-ui,sans-serif; font-size:23px; font-weight:700; letter-spacing:-.01em; margin-top:4px; font-variant-numeric:tabular-nums; }}
.card .valor .compacto {{ font-size:15px; line-height:1.35; display:block; }}
.card .extra {{ color:#9AA7B2; font-size:12px; margin-top:2px; }}
.selo {{ display:inline-block; padding:3px 12px; border-radius:999px; font-weight:700;
  font-size:12px; color:#0F1416; white-space:nowrap; vertical-align:middle; }}
.flag {{ background:#161D20; border:1px solid #1B2225; border-left:4px solid; border-radius:10px; padding:14px 16px; margin-bottom:10px; }}
.flag .sev {{ font-size:12px; font-weight:800; letter-spacing:.08em; }}
.flag h3 {{ font-size:16px; margin:2px 0 6px; }}
.flag .evid {{ background:#0F1416; border:1px solid #1B2225; border-radius:7px; padding:6px 10px;
  font-family:ui-monospace,Consolas,monospace; font-size:12.5px; color:#9AA7B2; margin-top:8px; }}
.flag .fonte {{ color:#6B7681; font-size:12px; margin-top:5px; }}
.ok {{ color:#7BD69A; font-size:14px; }} .na {{ color:#9AA7B2; font-size:13px; }}
ul.ok {{ list-style:none; padding-left:6px; }}
ul.ok li {{ color:#9AA7B2; margin:3px 0; }}
ul.ok li::before {{ content:'✓  '; color:#7BD69A; font-weight:700; }}
.regras {{ background:#161D20; border:1px solid #8FCB9B; border-radius:10px; padding:16px 18px; }}
.regras h2 {{ margin:0 0 8px; font-size:16px; color:#8FCB9B; }}
.regras li {{ margin:6px 0 6px 18px; font-size:14px; }}
.grafico {{ background:#161D20; border:1px solid #1B2225; border-radius:10px; padding:14px 16px 10px; margin-bottom:14px; }}
.grafico h3 {{ font-size:15px; color:#9AA7B2; margin-bottom:8px; }}
.grafico .nota, .nota {{ color:#6B7681; font-size:11.5px; }}
table.imoveis {{ width:100%; border-collapse:collapse; font-size:13.5px; font-variant-numeric:tabular-nums; }}
table.imoveis th {{ color:#9AA7B2; font-size:11.5px; text-transform:uppercase; letter-spacing:.05em; text-align:left; padding:6px 10px; border-bottom:1px solid #263034; }}
table.imoveis td {{ padding:7px 10px; border-bottom:1px solid #1B2225; }}
table.imoveis td:not(:first-child):not(:nth-child(2)), table.imoveis th:not(:first-child):not(:nth-child(2)) {{ text-align:right; }}
.rodape {{ color:#9AA7B2; font-size:12.5px; border-top:1px solid #1B2225; margin-top:30px; padding-top:14px; }}
{css_menu}
{CSS_MARCA}
</style>
</head>
<body>
<div class="pagina">
  {marca_html("index.html", com_busca_ticker=com_menu)}
  {menu}
  <h1>{_e(ticker)} <small title="{_e(empresa["nome"] or "")}">{_e(_trunca(empresa["nome_pregao"] or empresa["nome"] or "", 60))}</small> {selo_html}{aviso_situacao}</h1>
  <div class="meta">Ação · {_e(dados["multiplos"].get(ticker, {}).get("tipo") or "")} · {_e(_setor_curto(empresa))}
  · {_e(empresa["segmento_listagem"] or "—")}{meta_auditor} · página gerada em {agora.strftime("%d/%m/%Y %H:%M")}</div>

  <div class="cards">{"".join(cards)}</div>

  {flags_html}

  {_secao_parecer(leitura)}

  {_secao_ia(leitura, agora)}

  <div class="regras">
  <h2>As regras desta classe (Ações)</h2>
  <ul>{itens_regras}</ul>
  </div>

  {secao_papeis}

  {secao_balanco}

  {grafico_cotacao}
  {rentabilidade}

  <div class="rodape">{_RODAPE}<br>
  Projeto open source: <a href="https://github.com/Ruamms/scout">github.com/Ruamms/scout</a>
  · <a href="apoie.html">apoie o projeto</a>
  · <a href="acoes.html">todas as ações</a> · <a href="index.html">início</a></div>
</div>
<script>
{JS_GRAFICO_HOVER}
{js_menu}
</script>
</body>
</html>
"""
