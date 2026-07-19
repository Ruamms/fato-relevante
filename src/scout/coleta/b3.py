"""Cotações oficiais da B3 — arquivos históricos COTAHIST.

Fonte pública e documentada (Série Histórica de Cotações da B3), sem chave
e sem termos de uso restritivos: a base certa para um site público. Um
arquivo cobre TODOS os papéis do pregão de uma vez — nada de uma requisição
por ticker.

O COTAHIST traz preço NOMINAL (fechamento oficial, D-1). Os ajustes são
calculados aqui, de forma auditável:
- desdobramento/grupamento: mesmo algoritmo do ajuste de VP (salto >2,5x);
- proventos: retorno total mensal usando o rendimento estimado por cota
  (DY informado à CVM × VP ajustado), ancorado no preço atual.
"""

from __future__ import annotations

import io
import re
import sqlite3
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from datetime import date, datetime

from .. import armazenamento, series

URL_ARQUIVO = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/{nome}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (scout)"}
ANO_INICIAL = 2011  # cobre o histórico que o site sempre exibiu

_CODNEG_FII = re.compile(r"[A-Z]{4}11")


def nome_anual(ano: int) -> str:
    return f"COTAHIST_A{ano}.ZIP"


def nome_mensal(ano: int, mes: int) -> str:
    return f"COTAHIST_M{mes:02d}{ano}.ZIP"


def _baixar(nome: str, tentativas: int = 3) -> bytes:
    ultimo_erro: Exception | None = None
    url = URL_ARQUIVO.format(nome=nome)
    for tentativa in range(tentativas):
        try:
            requisicao = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(requisicao, timeout=600) as resposta:
                return resposta.read()
        except (urllib.error.URLError, OSError) as erro:
            ultimo_erro = erro
            if tentativa < tentativas - 1:
                time.sleep(5 * (tentativa + 1) ** 2)
    raise ultimo_erro


def extrair_pregoes(conteudo: bytes) -> dict[str, list[tuple[str, float]]]:
    """{ticker: [(dia AAAA-MM-DD, fechamento), ...]} dos FIIs do arquivo.

    Registro tipo 01, código BDI 12 (Fundos Imobiliários) e código de
    negociação padrão de cota (XXXX11 — direitos e recibos ficam fora).
    Layout posicional oficial: PREULT em [108:121], V99 (2 decimais).
    """
    pregoes: dict[str, list[tuple[str, float]]] = {}
    with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
        with zf.open(zf.namelist()[0]) as fh:
            for bruta in io.TextIOWrapper(fh, encoding="latin-1"):
                if not bruta.startswith("01") or bruta[10:12] != "12":
                    continue
                codneg = bruta[12:24].strip()
                if not _CODNEG_FII.fullmatch(codneg):
                    continue
                dia = f"{bruta[2:6]}-{bruta[6:8]}-{bruta[8:10]}"
                fechamento = int(bruta[108:121]) / 100
                if fechamento <= 0:
                    continue
                pregoes.setdefault(codneg, []).append((dia, fechamento))
    return pregoes


def gravar_pregoes(con: sqlite3.Connection, pregoes: dict[str, list[tuple[str, float]]]) -> int:
    """Agrega por mês (vale o último pregão) e grava em cotacoes_b3."""
    linhas = []
    for ticker, dias in pregoes.items():
        por_mes: dict[str, tuple[str, float]] = {}
        for dia, fechamento in sorted(dias):
            por_mes[dia[:7]] = (dia, fechamento)
        for competencia, (dia, fechamento) in por_mes.items():
            linhas.append((ticker, competencia, fechamento, dia))
    con.executemany(
        """
        INSERT OR REPLACE INTO cotacoes_b3 (ticker, competencia, fechamento, dia)
        VALUES (?, ?, ?, ?)
        """,
        linhas,
    )
    con.commit()
    return len(linhas)


def arquivos_pendentes(con: sqlite3.Connection, hoje: date) -> list[str]:
    """Anuais dos anos completos que faltam + mensais do ano corrente
    (o do mês corrente é sempre rebaixado; o anterior também nos primeiros
    dias do mês, quando ainda recebe acertos)."""
    carregados = {linha[0] for linha in con.execute("SELECT arquivo FROM cargas")}
    pendentes = [
        nome_anual(ano) for ano in range(ANO_INICIAL, hoje.year) if nome_anual(ano) not in carregados
    ]
    refazer_desde = hoje.month - (1 if hoje.day <= 5 and hoje.month > 1 else 0)
    for mes in range(1, hoje.month + 1):
        nome = nome_mensal(hoje.year, mes)
        if nome not in carregados or mes >= refazer_desde:
            pendentes.append(nome)
    return pendentes


def atualizar(
    con: sqlite3.Connection,
    hoje: date | None = None,
    ao_progredir: Callable[[str], None] | None = None,
) -> list[str]:
    hoje = hoje or date.today()
    resumo = []
    for nome in arquivos_pendentes(con, hoje):
        pregoes = extrair_pregoes(_baixar(nome))
        total = gravar_pregoes(con, pregoes)
        con.execute(
            "INSERT OR REPLACE INTO cargas (arquivo, carregado_em) VALUES (?, datetime('now'))",
            (nome,),
        )
        con.commit()
        mensagem = f"{nome}: {total} cotações mensais de {len(pregoes)} FIIs"
        resumo.append(mensagem)
        if ao_progredir:
            ao_progredir(mensagem)
    if resumo:
        tickers = recalcular_derivadas(con)
        mensagem = f"cotações ajustadas (desdobramento + proventos) para {tickers} tickers"
        resumo.append(mensagem)
        if ao_progredir:
            ao_progredir(mensagem)
    return resumo


def garantir_mes_corrente(con: sqlite3.Connection, agora: datetime | None = None) -> str | None:
    """Refresca o arquivo do mês corrente no máximo 1x/dia (um download
    cobre todos os tickers). Retorna aviso quando a rede falhar."""
    agora = agora or datetime.now()
    nome = nome_mensal(agora.year, agora.month)
    carga = con.execute(
        "SELECT carregado_em FROM cargas WHERE arquivo = ?", (nome,)
    ).fetchone()
    if carga and str(carga[0])[:10] == agora.strftime("%Y-%m-%d"):
        return None
    try:
        pregoes = extrair_pregoes(_baixar(nome, tentativas=1))
        gravar_pregoes(con, pregoes)
        con.execute(
            "INSERT OR REPLACE INTO cargas (arquivo, carregado_em) VALUES (?, ?)",
            (nome, agora.isoformat(timespec="seconds")),
        )
        con.commit()
        recalcular_derivadas(con, agora=agora)
        return None
    except Exception:
        return "sem conexão com a B3 — usando o cache local de cotações"


def recalcular_derivadas(con: sqlite3.Connection, agora: datetime | None = None) -> int:
    """Reconstrói a tabela `cotacoes` (a que a análise lê) a partir do
    nominal da B3: fechamento ajustado por desdobramento + série de retorno
    total (proventos estimados pelos informes CVM), ancorada no preço atual."""
    agora = agora or datetime.now()
    atualizado_em = agora.isoformat(timespec="seconds")
    tickers = [
        linha[0] for linha in con.execute("SELECT DISTINCT ticker FROM cotacoes_b3")
    ]
    for ticker in tickers:
        linhas = con.execute(
            "SELECT competencia, fechamento, dia FROM cotacoes_b3 WHERE ticker = ? ORDER BY competencia",
            (ticker,),
        ).fetchall()
        bruta = [(linha["competencia"], linha["fechamento"]) for linha in linhas]
        ajustada_split = series.ajustada_por_evento_de_cotas(bruta)
        proventos = _proventos_por_mes(con, ticker)
        total = _retorno_total(ajustada_split, proventos)
        candles = [
            (competencia, fechamento, total.get(competencia, fechamento))
            for competencia, fechamento in ajustada_split
        ]
        ultimo = linhas[-1]
        # série 100% B3: derruba resíduos de fontes anteriores (Yahoo) do ticker
        con.execute("DELETE FROM cotacoes WHERE ticker = ?", (ticker,))
        armazenamento.gravar_cotacoes(
            con, ticker, candles, ultimo["fechamento"], ultimo["dia"], atualizado_em
        )
    return len(tickers)


def _proventos_por_mes(con: sqlite3.Connection, ticker: str) -> dict[str, float]:
    """Rendimento estimado por cota (R$) por competência, na base de cotas
    atual: DY mensal informado à CVM × VP/cota ajustado."""
    fundo = armazenamento.resolver_fundo(con, ticker)
    if fundo is None:
        return {}
    serie = armazenamento.serie_complemento(con, fundo.cnpj)
    vp_ajustada = series.serie_vp_ajustada(serie)
    return {
        linha["competencia"]: linha["dy_mes"] * vp_ajustada[linha["competencia"]]
        for linha in serie
        if series.dy_valido(linha["dy_mes"]) and vp_ajustada.get(linha["competencia"])
    }


def _retorno_total(
    ajustada_split: list[tuple[str, float]], proventos: dict[str, float]
) -> dict[str, float]:
    """Série de retorno total (preço + proventos reinvestidos), ancorada no
    último ponto = preço atual. Para trás: adj[t-1] = adj[t] × f[t-1] / (f[t] + prov[t])."""
    total: dict[str, float] = {}
    seguinte: tuple[str, float, float] | None = None  # (competencia, fech, adj)
    for competencia, fechamento in reversed(ajustada_split):
        if seguinte is None:
            valor = fechamento
        else:
            comp_seguinte, fech_seguinte, adj_seguinte = seguinte
            base = fech_seguinte + proventos.get(comp_seguinte, 0.0)
            valor = adj_seguinte * fechamento / base if base > 0 else fechamento
        total[competencia] = valor
        seguinte = (competencia, fechamento, valor)
    return total
