"""Coleta do IPE (CVM) — fatos relevantes e comunicados de COMPANHIAS ABERTAS.

O IPE é o equivalente do FNET para empresas: um índice CSV anual com todos os
documentos entregues (categoria, assunto, data e LINK de download direto).
Devolvemos os documentos no MESMO formato do `fnet.listar` ({id, tipo,
categoria, data_entrega}) para reaproveitar o pipeline de leitura por IA
(seleção, cache idempotente e prompts) sem cirurgia.

Descoberta (22/07/2026): o zip do ano corrente (ipe_cia_aberta_2026) passou a
existir — o probe de 20/07 ainda não o encontrava. O índice é leve (~1,3 MB).
"""

from __future__ import annotations

import csv
import io
import sqlite3
import zipfile
from datetime import date
from pathlib import Path

URL_INDICE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{ano}.zip"
_HEADERS = {"User-Agent": "Mozilla/5.0"}
# categorias que valem leitura por IA (mesmo espírito do FNET: o que assusta)
_CATEGORIAS = ("Fato Relevante", "Comunicado ao Mercado")

_cache_indice: dict[int, list[dict]] = {}


def _baixar_indice(ano: int, timeout: int = 60) -> bytes:
    import urllib.request

    requisicao = urllib.request.Request(URL_INDICE.format(ano=ano), headers=_HEADERS)
    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
        return resposta.read()


def indice_do_ano(ano: int) -> list[dict]:
    """Índice IPE do ano inteiro (cacheado em memória: 1 download serve a fila
    toda do lote — diferente do FNET, que é 1 requisição por fundo)."""
    if ano not in _cache_indice:
        conteudo = _baixar_indice(ano)
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            with zf.open(zf.namelist()[0]) as fh:
                _cache_indice[ano] = list(
                    csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1"), delimiter=";")
                )
    return _cache_indice[ano]


def listar(cod_cvm: str, hoje: date | None = None, quantidade: int = 6) -> list[dict]:
    """Documentos recentes da empresa no formato do fnet.listar (mais novo
    primeiro). Cobre o ano corrente e o anterior (fato velho não assusta)."""
    hoje = hoje or date.today()
    codigo = str(int(cod_cvm)) if str(cod_cvm).isdigit() else str(cod_cvm)
    docs: list[dict] = []
    for ano in (hoje.year, hoje.year - 1):
        try:
            linhas = indice_do_ano(ano)
        except Exception:
            continue  # ano sem zip (virada) ou CVM fora do ar: segue com o que há
        for linha in linhas:
            if str(linha.get("Codigo_CVM") or "").lstrip("0") != codigo.lstrip("0"):
                continue
            categoria = (linha.get("Categoria") or "").strip()
            if not any(c in categoria for c in _CATEGORIAS):
                continue
            protocolo = (linha.get("Protocolo_Entrega") or "").strip()
            link = (linha.get("Link_Download") or "").strip()
            if not protocolo or not link:
                continue
            entrega = (linha.get("Data_Entrega") or "").strip()
            import hashlib

            docs.append(
                {
                    # id numérico p/ cache idempotente: hash estável do protocolo
                    # (o protocolo em dígitos estoura 64 bits e o SQLite o
                    # rebaixaria a REAL, quebrando a idempotência)
                    "id": int(hashlib.sha1(protocolo.encode()).hexdigest()[:15], 16),
                    "tipo": (linha.get("Assunto") or linha.get("Tipo") or "").strip()[:120],
                    "categoria": categoria,
                    # dd/mm/aaaa hh:mm — mesmo formato que o fnet devolve
                    "data_entrega": _data_br(entrega),
                    "link": link,
                }
            )
    docs.sort(key=lambda d: d["data_entrega"][6:10] + d["data_entrega"][3:5] + d["data_entrega"][:2], reverse=True)
    return docs[:quantidade]


def _data_br(iso: str) -> str:
    """2026-07-18 → 18/07/2026 (formato do FNET, que o pipeline já entende)."""
    iso = iso[:10]
    if len(iso) == 10 and iso[4] == "-":
        return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]} 00:00"
    return iso


def baixar(link: str, timeout: int = 90, tentativas: int = 3) -> bytes:
    """Download do documento (PDF) com o mesmo retry robusto do FNET —
    open + read na mesma tentativa, IncompleteRead coberto."""
    import urllib.request

    from . import fnet

    requisicao = urllib.request.Request(link, headers=_HEADERS)
    return fnet._buscar_com_retry(
        requisicao, timeout=timeout, tentativas=tentativas, consumir=lambda r: r.read()
    )


def garantir_documento(
    con: sqlite3.Connection, cnpj: str, documento_: dict, destino: Path,
    timeout: int = 90, tentativas: int = 3,
) -> Path:
    """Cache idempotente igual ao do FNET (mesma tabela `documentos`): baixa o
    PDF do IPE uma vez e reaproveita nas rodadas seguintes."""
    from .. import armazenamento
    from .fnet import _arquivo_pdf_truncado, so_digitos

    registrado = armazenamento.documento(con, cnpj, documento_["id"])
    if registrado and registrado["arquivo"] and Path(registrado["arquivo"]).exists():
        cache = Path(registrado["arquivo"])
        if not _arquivo_pdf_truncado(cache):
            return cache

    conteudo = baixar(documento_["link"], timeout=timeout, tentativas=tentativas)
    pasta = destino / so_digitos(cnpj)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{documento_['id']}.pdf"
    caminho.write_bytes(conteudo)
    armazenamento.gravar_documento(
        con, cnpj, documento_["id"], documento_["tipo"], documento_["categoria"],
        documento_["data_entrega"], str(caminho),
    )
    return caminho
