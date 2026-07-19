"""Cotações dos ETFs de RENDA FIXA — API pública de cotações da B3.

Esses fundos negociam no mercado de renda fixa da B3 e NÃO aparecem no
COTAHIST (ver docs/ETFS.md). A fonte aqui é a API oficial que alimenta o
próprio site da B3 (`cotacao.b3.com.br`): último preço, data do pregão e
quantidade negociada.

Não há histórico retroativo público — então a série HISTÓRICA nasce da
coleta diária daqui para a frente (1 fechamento por dia útil, acumulado em
`cotacoes_b3` como os demais). Honestidade > mágica: o gráfico desses fundos
começa curto e engorda com o tempo.
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.request
from datetime import date

URL_COTACAO = "https://cotacao.b3.com.br/mds/api/v1/instrumentQuotation/{ticker}"
URL_DIA = "https://cotacao.b3.com.br/mds/api/v1/DailyFluctuationHistory/{ticker}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (scout)"}


def _obter(url: str) -> dict:
    requisicao = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(requisicao, timeout=45) as resposta:
        return json.load(resposta)


def buscar(ticker: str) -> tuple[str, float, float] | None:
    """(dia do pregão AAAA-MM-DD, fechamento, volume R$ do dia) ou None."""
    try:
        historia = _obter(URL_DIA.format(ticker=ticker))
        dia = (historia.get("TradgFlr") or {}).get("date") or ""
        cotacao = _obter(URL_COTACAO.format(ticker=ticker))
        negocio = (cotacao.get("Trad") or [{}])[0]
        qtn = ((negocio.get("scty") or {}).get("SctyQtn")) or {}
        preco = qtn.get("curPrc") or qtn.get("closPric")
        media = qtn.get("avrgPric") or preco
        quantidade = negocio.get("ttlQty") or 0
    except Exception:
        return None
    if not dia or not preco:
        return None
    volume = float(media or 0) * float(quantidade or 0)
    return dia, float(preco), volume


def atualizar_diaria(
    con: sqlite3.Connection, hoje: date | None = None, ao_progredir=None
) -> str | None:
    """Coleta o fechamento do dia dos ETFs de renda fixa (1x/dia).

    Upsert idempotente por (ticker, dia do pregão): rodar duas vezes no mesmo
    dia não duplica volume nem pregões."""
    from . import b3

    hoje = hoje or date.today()
    carga = con.execute(
        "SELECT carregado_em FROM cargas WHERE arquivo = 'RF_COTACOES_DIA'"
    ).fetchone()
    if carga and str(carga[0])[:10] == hoje.isoformat():
        return None
    tickers = [
        linha[0]
        for linha in con.execute(
            "SELECT ticker FROM etfs WHERE tipo_b3 = 'ETF-RF' AND ticker IS NOT NULL AND ticker <> ''"
        )
    ]
    if not tickers:
        return None
    coletados = 0
    for ticker in tickers:
        resultado = buscar(ticker)
        time.sleep(0.15)  # educação com a fonte
        if resultado is None:
            continue
        dia, preco, volume = resultado
        _upsert_dia(con, ticker, dia, preco, volume)
        coletados += 1
    con.execute(
        "INSERT OR REPLACE INTO cargas (arquivo, carregado_em) VALUES ('RF_COTACOES_DIA', ?)",
        (hoje.isoformat(),),
    )
    con.commit()
    if coletados:
        b3.recalcular_derivadas(con)
    mensagem = (
        f"cotações de ETF de renda fixa (B3, mercado próprio): {coletados}/{len(tickers)} coletadas"
    )
    if ao_progredir:
        ao_progredir(mensagem)
    return mensagem


def _upsert_dia(con: sqlite3.Connection, ticker: str, dia: str, preco: float, volume: float) -> None:
    competencia = dia[:7]
    atual = con.execute(
        "SELECT dia, volume, pregoes FROM cotacoes_b3 WHERE ticker = ? AND competencia = ?",
        (ticker, competencia),
    ).fetchone()
    if atual and atual["dia"] == dia:
        return  # o pregão de hoje já foi registrado
    volume_mes = (atual["volume"] or 0 if atual else 0) + volume
    pregoes = (atual["pregoes"] or 0 if atual else 0) + 1
    con.execute(
        """
        INSERT OR REPLACE INTO cotacoes_b3 (ticker, competencia, fechamento, dia, volume, pregoes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (ticker, competencia, preco, dia, volume_mes, pregoes),
    )
