"""Resolvedor único de preço de um ativo, por tipo.

A ideia (desenho do usuário): cada posição dentro de um ETF tem um TIPO
(ação, FII, ETF, renda fixa, exterior, cripto). Para reprecificar a carteira
"a preço de hoje", basta perguntar a este resolvedor o preço atual de cada
ativo — e cada tipo pluga na sua fonte:

- Ação / FII / ETF  -> já temos preço diário (fechamento D-1) em `cotacoes_meta`
  (COTAHIST da B3, codbdi 02/12/14). Acende HOJE.
- Renda Fixa / Exterior / Cripto -> ainda sem preço POR ATIVO; retorna None e a
  posição fica no valor informado à CVM. Quando a fonte existir, é só adicionar
  um ramo aqui — nada mais no resto do código muda ("deixa tudo pronto").

Nunca inventa preço: se não há fonte, é None.
"""

from __future__ import annotations

import re
import sqlite3

from . import armazenamento

_TICKER_ACAO = re.compile(r"^[A-Z]{4}\d{1,2}$")  # PETR4, VALE3, ITUB4…


def ticker_para_preco(posicao: dict) -> str | None:
    """O ticker que usamos para buscar preço: o alvo já resolvido (FII/ETF pelo
    CNPJ do emissor) ou o próprio código quando é uma ação (CD_ATIVO da B3)."""
    alvo = posicao.get("ticker_alvo")
    if alvo:
        return alvo
    codigo = (posicao.get("codigo") or "").strip().upper()
    if _TICKER_ACAO.match(codigo):
        return codigo
    return None


def preco_por_ticker(con: sqlite3.Connection, ticker: str) -> dict | None:
    """{preco, cotado_em} do fechamento oficial mais recente, ou None."""
    meta = armazenamento.cotacao_meta(con, ticker)
    if meta is None or meta["preco_atual"] is None:
        return None
    return {"preco": meta["preco_atual"], "cotado_em": meta["cotado_em"]}


def reprecificar_posicoes(
    con: sqlite3.Connection, posicoes: list[dict]
) -> tuple[list[dict], dict]:
    """Enriquece cada posição com `preco_hoje`, `cotado_em` e `valor_hoje`
    (quantidade × preço, quando temos a quantidade). Devolve (posições, resumo),
    onde o resumo traz a COBERTURA: quanto da carteira (pelo peso do CDA) tem
    preço de hoje na nossa base."""
    enriquecidas: list[dict] = []
    peso_com_preco = 0.0
    valor_hoje_total = 0.0
    tem_algum_valor = False
    for posicao in posicoes:
        ticker = ticker_para_preco(posicao)
        cotacao = preco_por_ticker(con, ticker) if ticker else None
        quantidade = posicao.get("quantidade")
        valor_hoje = (
            cotacao["preco"] * quantidade if (cotacao and quantidade) else None
        )
        enriquecidas.append(
            {
                **posicao,
                "preco_hoje": cotacao["preco"] if cotacao else None,
                "cotado_em": cotacao["cotado_em"] if cotacao else None,
                "valor_hoje": valor_hoje,
            }
        )
        if cotacao:
            peso_com_preco += posicao.get("pct") or 0.0
        if valor_hoje is not None:
            valor_hoje_total += valor_hoje
            tem_algum_valor = True
    resumo = {
        "cobertura_pct": round(peso_com_preco, 1),  # % do peso da carteira com preço de hoje
        "valor_hoje_total": valor_hoje_total if tem_algum_valor else None,
    }
    return enriquecidas, resumo
