"""Coleta de índices de referência: CDI e IPCA (SGS/Banco Central) e IFIX
(estatísticas históricas oficiais da B3).

Fontes oficiais, gratuitas e sem chave. Valores gravados são percentuais
MENSAIS (ex.: 1.16 = 1,16% no mês).
"""

from __future__ import annotations

import base64
import json
import sqlite3
import urllib.request
from datetime import date

from .. import armazenamento

SERIES_SGS = {"CDI": 4391, "IPCA": 433}
URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    "?formato=json&dataInicial=01/01/2016"
)
URL_IFIX = (
    "https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay/{token}"
)
ANO_INICIAL_IFIX = 2011  # primeiro ano do índice


def garantir_atualizados(con: sqlite3.Connection, hoje: date | None = None) -> str | None:
    """Sincroniza CDI, IPCA e IFIX (1x/dia). Retorna aviso se ficou sem dado novo."""
    hoje = hoje or date.today()
    pendentes = [
        serie
        for serie in list(SERIES_SGS) + ["IFIX"]
        if (meta := armazenamento.indice_meta(con, serie)) is None
        or meta["atualizado_em"] != hoje.isoformat()
    ]
    if not pendentes:
        return None
    falhas = []
    for serie in pendentes:
        try:
            valores = buscar_ifix(hoje) if serie == "IFIX" else buscar(serie)
        except Exception:
            falhas.append(serie)
            continue
        armazenamento.gravar_indice(con, serie, valores, hoje.isoformat())
    if falhas:
        tem_cache = all(armazenamento.serie_indice(con, serie) for serie in falhas)
        if tem_cache:
            return f"sem conexão com a fonte de índices — usando cache de {'/'.join(falhas)}"
        return f"índices indisponíveis (sem conexão): {'/'.join(falhas)}"
    return None


def buscar(serie: str) -> list[tuple[str, float]]:
    url = URL.format(codigo=SERIES_SGS[serie])
    requisicao = urllib.request.Request(url, headers={"User-Agent": "scout"})
    with urllib.request.urlopen(requisicao, timeout=60) as resposta:
        return extrair(json.load(resposta))


def buscar_ifix(hoje: date | None = None) -> list[tuple[str, float]]:
    """% mensal do IFIX a partir dos fechamentos oficiais da B3 (um request
    leve por ano). O encadeamento entre anos usa o dezembro anterior."""
    hoje = hoje or date.today()
    fechos: dict[str, float] = {}
    for ano in range(ANO_INICIAL_IFIX, hoje.year + 1):
        fechos.update(fechos_ifix_do_ano(_buscar_ano_ifix(ano), ano))
    return variacoes_mensais(fechos)


def _buscar_ano_ifix(ano: int) -> dict:
    parametros = {
        "index": "IFIX",
        "language": "pt-br",
        "year": str(ano),
        "pageNumber": 1,
        "pageSize": 40,
    }
    token = base64.b64encode(json.dumps(parametros).encode()).decode()
    requisicao = urllib.request.Request(
        URL_IFIX.format(token=token), headers={"User-Agent": "Mozilla/5.0 (scout)"}
    )
    with urllib.request.urlopen(requisicao, timeout=60) as resposta:
        return json.load(resposta)


def fechos_ifix_do_ano(dados: dict, ano: int) -> dict[str, float]:
    """{competencia: fechamento} — o valor do maior dia com dado em cada mês.
    O JSON da B3 traz uma grade dia × mês (rateValue1..12, formato pt-BR)."""
    ultimo_por_mes: dict[int, tuple[int, float]] = {}
    for linha in dados.get("results") or []:
        dia = linha.get("day")
        if not dia:
            continue
        for mes in range(1, 13):
            valor = _numero_br(linha.get(f"rateValue{mes}"))
            if valor is None:
                continue
            if mes not in ultimo_por_mes or dia > ultimo_por_mes[mes][0]:
                ultimo_por_mes[mes] = (dia, valor)
    return {f"{ano}-{mes:02d}": valor for mes, (_, valor) in ultimo_por_mes.items()}


def variacoes_mensais(fechos: dict[str, float]) -> list[tuple[str, float]]:
    """Fechamentos mensais -> % de variação mês a mês (competências ordenadas)."""
    ordenado = sorted(fechos.items())
    valores = []
    for (comp_anterior, fecho_anterior), (competencia, fecho) in zip(ordenado, ordenado[1:]):
        if fecho_anterior:
            valores.append((competencia, 100 * (fecho / fecho_anterior - 1)))
    return valores


def _numero_br(texto) -> float | None:
    if not texto or not str(texto).strip():
        return None
    try:
        return float(str(texto).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def extrair(dados: list[dict]) -> list[tuple[str, float]]:
    """Converte o JSON do SGS ([{'data': '01/MM/AAAA', 'valor': '1.16'}])."""
    valores = []
    for item in dados:
        data, valor = item.get("data", ""), item.get("valor", "")
        if len(data) < 10 or not valor:
            continue
        competencia = f"{data[6:10]}-{data[3:5]}"
        try:
            valores.append((competencia, float(valor)))
        except ValueError:
            continue
    return valores
