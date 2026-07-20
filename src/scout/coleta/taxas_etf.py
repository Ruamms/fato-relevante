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
import sys
from pathlib import Path


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
            if not ticker or valor is None:
                continue
            taxas[ticker] = {
                "taxa_adm_aa": valor,
                "fonte": (linha.get("fonte") or "").strip(),
                "verificado_em": (linha.get("verificado_em") or "").strip(),
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
