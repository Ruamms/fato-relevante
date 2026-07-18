"""Coleta dos informes mensais de FII dos dados abertos da CVM.

Fonte: https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/
Um ZIP por ano (2016+), cada um com os CSVs geral, complemento e
ativo_passivo (separador ';', encoding latin-1).
"""

from __future__ import annotations

import csv
import io
import sqlite3
import urllib.request
import zipfile
from collections.abc import Callable
from datetime import date

URL_BASE = "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/"
ANO_INICIAL = 2016

# A Resolução CVM 175 renomeou colunas a partir de 2024; este mapa
# normaliza os dois vocabulários para o antigo.
_RENOMEIA = {
    "CNPJ_Fundo_Classe": "CNPJ_Fundo",
    "Nome_Fundo_Classe": "Nome_Fundo",
}


def nome_arquivo(ano: int) -> str:
    return f"inf_mensal_fii_{ano}.zip"


def baixar(ano: int) -> bytes:
    url = URL_BASE + nome_arquivo(ano)
    with urllib.request.urlopen(url, timeout=120) as resposta:
        return resposta.read()


def anos_pendentes(con: sqlite3.Connection, hoje: date) -> list[int]:
    """Anos a baixar: os que faltam + os 2 últimos (informes chegam com atraso)."""
    carregados = {linha[0] for linha in con.execute("SELECT arquivo FROM cargas")}
    return [
        ano
        for ano in range(ANO_INICIAL, hoje.year + 1)
        if nome_arquivo(ano) not in carregados or ano >= hoje.year - 1
    ]


def atualizar(
    con: sqlite3.Connection,
    hoje: date | None = None,
    ao_progredir: Callable[[str], None] | None = None,
) -> list[str]:
    hoje = hoje or date.today()
    resumo = []
    for ano in anos_pendentes(con, hoje):
        arquivo = nome_arquivo(ano)
        conteudo = baixar(ano)
        gerais, complementos = carregar_zip(con, conteudo, arquivo)
        mensagem = f"{arquivo}: {gerais} informes gerais, {complementos} complementos"
        resumo.append(mensagem)
        if ao_progredir:
            ao_progredir(mensagem)
    return resumo


def carregar_zip(con: sqlite3.Connection, conteudo: bytes, arquivo: str) -> tuple[int, int]:
    with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
        gerais = _ler_csv(zf, "geral")
        complementos = _ler_csv(zf, "complemento")
    n_gerais = _gravar_gerais(con, gerais)
    n_complementos = _gravar_complementos(con, complementos)
    con.execute(
        "INSERT OR REPLACE INTO cargas (arquivo, carregado_em) VALUES (?, datetime('now'))",
        (arquivo,),
    )
    con.commit()
    return n_gerais, n_complementos


def _ler_csv(zf: zipfile.ZipFile, sufixo: str) -> list[dict]:
    membro = next((n for n in zf.namelist() if sufixo in n), None)
    if membro is None:
        raise ValueError(f"CSV '{sufixo}' não encontrado no ZIP ({zf.namelist()})")
    with zf.open(membro) as fh:
        texto = io.TextIOWrapper(fh, encoding="latin-1")
        linhas = [_normalizar(linha) for linha in csv.DictReader(texto, delimiter=";")]
    # Grava na ordem: menor versão primeiro e, em empate, linhas com ISIN
    # por último — assim o REPLACE deixa vencer a informação mais completa.
    linhas.sort(key=lambda l: (_inteiro(l.get("Versao")), 1 if l.get("Codigo_ISIN") else 0))
    return linhas


def _normalizar(linha: dict) -> dict:
    return {_RENOMEIA.get(chave, chave): valor for chave, valor in linha.items() if chave}


def _gravar_gerais(con: sqlite3.Connection, linhas: list[dict]) -> int:
    total = 0
    for linha in linhas:
        chave = _chave(linha)
        if chave is None:
            continue
        con.execute(
            """
            INSERT OR REPLACE INTO informes_gerais
                (cnpj, competencia, nome, segmento, tipo_gestao, isin, cotas_emitidas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                *chave,
                linha.get("Nome_Fundo") or None,
                linha.get("Segmento_Atuacao") or None,
                linha.get("Tipo_Gestao") or None,
                linha.get("Codigo_ISIN") or None,
                _numero(linha.get("Quantidade_Cotas_Emitidas")),
            ),
        )
        total += 1
    return total


def _gravar_complementos(con: sqlite3.Connection, linhas: list[dict]) -> int:
    total = 0
    for linha in linhas:
        chave = _chave(linha)
        if chave is None:
            continue
        con.execute(
            """
            INSERT OR REPLACE INTO informes_complemento
                (cnpj, competencia, valor_ativo, patrimonio_liquido, cotas_emitidas,
                 vp_cota, rentab_patrimonial_mes, dy_mes, amortizacao_mes, cotistas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                *chave,
                _numero(linha.get("Valor_Ativo")),
                _numero(linha.get("Patrimonio_Liquido")),
                _numero(linha.get("Cotas_Emitidas")),
                _numero(linha.get("Valor_Patrimonial_Cotas")),
                _numero(linha.get("Percentual_Rentabilidade_Patrimonial_Mes")),
                _numero(linha.get("Percentual_Dividend_Yield_Mes")),
                _numero(linha.get("Percentual_Amortizacao_Cotas_Mes")),
                _numero(linha.get("Total_Numero_Cotistas")),
            ),
        )
        total += 1
    return total


def _chave(linha: dict) -> tuple[str, str] | None:
    cnpj = (linha.get("CNPJ_Fundo") or "").strip()
    referencia = (linha.get("Data_Referencia") or "").strip()
    if not cnpj or len(referencia) < 7:
        return None
    return cnpj, referencia[:7]


def _numero(valor: str | None) -> float | None:
    if valor is None:
        return None
    valor = valor.strip()
    if not valor:
        return None
    try:
        return float(valor)
    except ValueError:
        return None


def _inteiro(valor: str | None) -> int:
    try:
        return int(valor or 0)
    except ValueError:
        return 0
