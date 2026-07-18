"""Coleta de documentos do FNET (B3): relatórios gerenciais e fatos relevantes.

API pública, sem chave. A pesquisa devolve JSON; o download devolve o PDF
direto. Os PDFs baixados ficam em `<dados>/documentos/<cnpj>/<id>.pdf` e o
índice vai para a tabela `documentos`.
"""

from __future__ import annotations

import json
import re
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

from .. import armazenamento

URL_PESQUISA = (
    "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"
    "?d=0&s=0&l={quantidade}&o%5B0%5D%5BdataEntrega%5D=desc&cnpjFundo={cnpj}"
    "&idCategoriaDocumento=0&idTipoDocumento=0&idEspecieDocumento=0"
)
URL_DOWNLOAD = "https://fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id={id}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (fato-relevante)"}


def so_digitos(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def listar(cnpj: str, quantidade: int = 30) -> list[dict]:
    """Documentos mais recentes do fundo no FNET (mais novo primeiro)."""
    url = URL_PESQUISA.format(cnpj=so_digitos(cnpj), quantidade=quantidade)
    requisicao = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(requisicao, timeout=60) as resposta:
        dados = json.load(resposta)
    return [
        {
            "id": item.get("id"),
            "tipo": (item.get("tipoDocumento") or "").strip(),
            "categoria": (item.get("categoriaDocumento") or "").strip(),
            "data_entrega": (item.get("dataEntrega") or "").strip(),
        }
        for item in dados.get("data", [])
        if item.get("id")
    ]


def baixar(id_fnet: int) -> bytes:
    requisicao = urllib.request.Request(
        URL_DOWNLOAD.format(id=id_fnet), headers=_HEADERS
    )
    with urllib.request.urlopen(requisicao, timeout=180) as resposta:
        return resposta.read()


def ultimo_relatorio_gerencial(documentos: list[dict]) -> dict | None:
    for documento_ in documentos:
        if "relatório gerencial" in documento_["tipo"].lower():
            return documento_
    return None


def fatos_relevantes(documentos: list[dict], quantidade: int = 3) -> list[dict]:
    return [
        documento_
        for documento_ in documentos
        if documento_["categoria"].lower() == "fato relevante"
    ][:quantidade]


def garantir_relatorio(
    con: sqlite3.Connection, cnpj: str, destino: Path | None = None
) -> tuple[Path, dict] | None:
    """Garante o último relatório gerencial baixado; retorna (caminho, metadados).

    Idempotente: se o PDF do documento mais recente já está no disco, não
    vai à rede de novo para baixá-lo.
    """
    destino = destino or armazenamento.diretorio_dados() / "documentos"
    documentos = listar(cnpj)
    relatorio = ultimo_relatorio_gerencial(documentos)
    if relatorio is None:
        return None
    registrado = armazenamento.documento(con, cnpj, relatorio["id"])
    if registrado and registrado["arquivo"] and Path(registrado["arquivo"]).exists():
        return Path(registrado["arquivo"]), relatorio

    conteudo = baixar(relatorio["id"])
    pasta = destino / so_digitos(cnpj)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{relatorio['id']}.pdf"
    caminho.write_bytes(conteudo)
    armazenamento.gravar_documento(
        con,
        cnpj,
        relatorio["id"],
        relatorio["tipo"],
        relatorio["categoria"],
        relatorio["data_entrega"],
        str(caminho),
    )
    return caminho, relatorio
