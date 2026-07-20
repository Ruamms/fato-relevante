"""Taxa de administração de ETFs — curadoria com fonte (dados/taxas_etfs.csv).

Ao contrário do FII, o ETF (fundo de índice) NÃO entra no regime que publica
taxa de administração em dados abertos da CVM: ela não está no registro de
fundos, nem no cad_fi/extrato/lâmina, e a B3 também não expõe. A única fonte
oficial é o REGULAMENTO do fundo. Por isso a taxa de ETF é tratada como
curadoria: um número por ticker, sempre acompanhado da fonte (link do
regulamento) e da data em que foi conferido. Determinístico e auditável — o
Scout nunca inventa a taxa.

O arquivo pode ser pré-preenchido lendo o regulamento no FNET (proposta) e é
sempre revisado manualmente antes de entrar.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

# "taxa de administração ... 0,30% ..." — captura o 1º percentual plausível
# depois da expressão. DETERMINÍSTICO (regex), nunca IA: o número sai do texto
# oficial do regulamento, e ainda assim entra como PROPOSTA para revisão humana.
_RE_TAXA_ADM = re.compile(
    r"taxa\s+de\s+administra[çc][ãa]o[^%]{0,180}?(\d{1,2}(?:[.,]\d{1,4})?)\s*%",
    re.IGNORECASE,
)


def extrair_taxa_regulamento(texto: str) -> dict | None:
    """Acha a taxa de administração (% a.a.) no texto de um regulamento.

    Retorna {taxa_adm_aa, trecho, confianca} ou None. Prefere o trecho que fala
    em "ano/a.a." (confiança alta); pula o que fala em "mês/mensal" (não vamos
    reportar taxa mensal como anual). É sempre uma PROPOSTA — quem confirma é o
    humano, olhando o trecho e a fonte."""
    if not texto:
        return None
    plano = " ".join(texto.split())
    candidatos: list[dict] = []
    for casamento in _RE_TAXA_ADM.finditer(plano):
        try:
            valor = float(casamento.group(1).replace(",", "."))
        except ValueError:
            continue
        if not 0 < valor <= 3:  # taxa de ETF fica bem abaixo de 3% a.a.
            continue
        cauda_curta = plano[casamento.end() : casamento.end() + 25].lower()
        if "mês" in cauda_curta or "mes" in cauda_curta or "mensal" in cauda_curta:
            continue  # taxa mensal (armadilha) — não confundir com a anual
        # "ao ano/a.a." costuma vir após o valor por extenso entre parênteses,
        # então a janela para confiança é mais larga que a de "mês"
        cauda_longa = plano[casamento.end() : casamento.end() + 70].lower()
        trecho = plano[casamento.start() : casamento.end() + 40].strip()
        confianca = "alta" if ("ano" in cauda_longa or "a.a" in cauda_longa) else "media"
        candidatos.append({"taxa_adm_aa": valor, "trecho": trecho, "confianca": confianca})
    if not candidatos:
        return None
    return next((c for c in candidatos if c["confianca"] == "alta"), candidatos[0])


_CAP_POR_RODADA = 20  # lê no máximo N regulamentos NOVOS por atualizar (FNET é lento)


def _caminho_gravavel() -> Path | None:
    """O CSV de curadoria no repositório (gravável). None quando rodando do
    executável empacotado (dados embutidos são read-only) — a coleta só grava
    a partir do código-fonte."""
    caminho = Path(__file__).resolve().parents[3] / "dados" / "taxas_etfs.csv"
    return caminho if caminho.parent.exists() else None


def _tickers_no_arquivo(caminho: Path) -> set[str]:
    """Todos os tickers já no arquivo (achados, manuais OU 'não achados') — é a
    chave do incremental: quem já está aqui não é relido."""
    if not caminho.exists():
        return set()
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        return {
            (linha.get("ticker") or "").strip().upper()
            for linha in csv.DictReader(fh, delimiter=";")
            if (linha.get("ticker") or "").strip()
        }


def atualizar(con, ao_progredir=None) -> str | None:
    """Passo do `scout atualizar`: lê o REGULAMENTO no FNET dos ETFs que ainda
    não estão em dados/taxas_etfs.csv e ATUALIZA o arquivo — preenche a taxa
    quando acha (com a confiança, entra direto no site) e deixa uma linha
    'nao_achou'/'sem_regulamento' quando não acha (fica aguardando conferência
    manual). Incremental: quem já está no arquivo NÃO é relido. Processa até
    `_CAP_POR_RODADA` por rodada (FNET é lento); o resto vem na próxima.
    Retorna None quando não há nada a fazer (grava só do código-fonte)."""
    import os
    from datetime import date

    from .. import armazenamento, ia
    from . import fnet

    # a curadoria de taxa roda LOCAL (o FNET pendura a partir do IP do CI, e o
    # que o CI gravasse seria efêmero); no GitHub Actions o site usa o CSV que
    # você commitou depois de rodar aqui
    if os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"):
        return None
    caminho = _caminho_gravavel()
    if caminho is None:
        return None
    presentes = _tickers_no_arquivo(caminho)
    pendentes = [
        etf
        for etf in armazenamento.etfs_listados(con)
        if (etf["ticker"] or "").strip().upper()
        and (etf["ticker"] or "").strip().upper() not in presentes
    ]
    if not pendentes:
        return None  # todos já lidos — "se já foi, não chama de novo"

    lote = pendentes[:_CAP_POR_RODADA]
    hoje = date.today().isoformat()
    novos: list[tuple] = []
    achados = 0
    for etf in lote:
        ticker = etf["ticker"].strip().upper()
        try:
            documentos = fnet.listar(etf["cnpj"], quantidade=120, timeout=12, tentativas=2)
        except Exception:  # noqa: BLE001 — falha de rede NÃO marca como lido (retenta depois)
            continue
        regulamento = fnet.ultimo_regulamento(documentos)
        if regulamento is None:
            novos.append((ticker, "", "", hoje, "sem_regulamento"))
            continue
        try:
            caminho_pdf = fnet._garantir_documento(
                con,
                etf["cnpj"],
                regulamento,
                armazenamento.diretorio_dados() / "documentos",
                timeout=45,
                tentativas=2,
            )
            achado = extrair_taxa_regulamento(ia.extrair_texto_pdf(caminho_pdf, max_paginas=60))
        except Exception:  # noqa: BLE001 — download/parse falhou: não marca (retenta)
            continue
        fonte = fnet.URL_DOWNLOAD.format(id=regulamento["id"])
        if achado:
            achados += 1
            taxa = f"{achado['taxa_adm_aa']:.2f}".replace(".", ",")
            novos.append((ticker, taxa, fonte, hoje, achado["confianca"]))
        else:
            novos.append((ticker, "", fonte, hoje, "nao_achou"))

    if novos:
        import csv as _csv

        with caminho.open("a", encoding="utf-8-sig", newline="") as fh:
            _csv.writer(fh, delimiter=";").writerows(novos)
    restantes = len(pendentes) - len(lote)
    mensagem = (
        f"taxas de ETF (regulamento): {achados} achada(s) de {len(novos)} lida(s)"
        + (f" · {restantes} p/ próxima rodada" if restantes > 0 else " · fila completa")
    )
    if ao_progredir:
        ao_progredir(mensagem)
    return mensagem


def carregar(raiz: Path | None = None) -> dict[str, dict]:
    """dados/taxas_etfs.csv -> {TICKER: {taxa_adm_aa, fonte, verificado_em}}.

    Procura no repositório (curadoria editável) e, no executável PyInstaller,
    nos dados embutidos (sys._MEIPASS) — mesmo padrão da classificação."""
    candidatos = [
        (raiz or Path(".")) / "dados" / "taxas_etfs.csv",
        Path(__file__).resolve().parents[3] / "dados" / "taxas_etfs.csv",
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidatos.insert(0, Path(meipass) / "dados" / "taxas_etfs.csv")
    caminho = next((c for c in candidatos if c.exists()), None)
    if caminho is None:
        return {}
    taxas: dict[str, dict] = {}
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        for linha in csv.DictReader(fh, delimiter=";"):
            ticker = (linha.get("ticker") or "").strip().upper()
            valor = _numero(linha.get("taxa_adm_aa"))
            confianca = (linha.get("confianca") or "").strip().lower()
            # PORTEIRO (regra do dono): só vai pro site quem tem taxa numérica E
            # confiança preenchida. O que foi ACHADO no regulamento já vem com
            # confiança (alta/média) e entra direto; o que NÃO foi achado fica no
            # arquivo como "nao_achou"/"sem_regulamento" (sem taxa) até alguém
            # conferir e preencher manualmente.
            if not ticker or valor is None or confianca in ("", "nao_achou", "sem_regulamento"):
                continue
            taxas[ticker] = {
                "taxa_adm_aa": valor,
                "fonte": (linha.get("fonte") or "").strip(),
                "verificado_em": (linha.get("verificado_em") or "").strip(),
                "confianca": confianca,
            }
    return taxas


def _numero(valor: str | None) -> float | None:
    """Taxa em % a.a., aceitando vírgula ou ponto. Descarta o que não faz
    sentido: taxa de ETF fica tipicamente entre 0 e 3% a.a."""
    if valor is None:
        return None
    valor = valor.strip().replace(",", ".")
    if not valor:
        return None
    try:
        numero = float(valor)
    except ValueError:
        return None
    return numero if 0 <= numero <= 3 else None
