"""Fachada de cotações da análise — hoje servida pelos arquivos oficiais
COTAHIST da B3 (ver `coleta/b3.py`).

`garantir_atualizada` mantém o contrato antigo (por ticker), mas por baixo
UM refresh diário do arquivo do mês corrente cobre a base inteira — a
primeira chamada do dia baixa e recalcula; as demais são instantâneas.

O preço exibido é o último FECHAMENTO OFICIAL de pregão (D-1) — melhor
fonte gratuita e documentada que existe; preço em tempo real é licenciado
e pago na B3.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from .. import armazenamento
from . import b3


def garantir_atualizada(
    con: sqlite3.Connection, ticker: str, agora: datetime | None = None
) -> str | None:
    """Garante o cache de cotações fresco (1x/dia, base inteira de uma vez).

    Retorna None quando está tudo certo, ou uma mensagem de aviso para
    exibir ao usuário (cache antigo ou ticker sem negociação)."""
    ticker = ticker.strip().upper()
    aviso = b3.garantir_mes_corrente(con, agora)
    meta = armazenamento.cotacao_meta(con, ticker)
    if meta is None:
        return "cotação de bolsa indisponível para este ticker (não negociado na B3 ou base desatualizada — rode scout atualizar)"
    if aviso:
        return f"{aviso} — preço de {_data_br(meta['cotado_em'])}"
    return None


def _data_br(iso: str | None) -> str:
    if not iso or len(iso) < 10:
        return "?"
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"
