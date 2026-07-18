"""Formatação de números e datas em pt-BR."""

from __future__ import annotations


def decimal(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def percentual(valor: float, sinal: bool = False) -> str:
    prefixo = "+" if sinal and valor > 0 else ""
    return f"{prefixo}{decimal(valor)}%"


def compacto(valor: float) -> str:
    for limite, sufixo in ((1e9, "B"), (1e6, "M"), (1e3, "mil")):
        if abs(valor) >= limite:
            return f"{decimal(valor / limite, 1)}{sufixo}"
    return decimal(valor, 0)


def moeda_compacta(valor: float) -> str:
    return f"R$ {compacto(valor)}"


def competencia_br(competencia: str) -> str:
    return f"{competencia[5:7]}/{competencia[:4]}"


def dia_br(data_iso: str | None) -> str:
    if not data_iso or len(data_iso) < 10:
        return ""
    return f"{data_iso[8:10]}/{data_iso[5:7]}/{data_iso[:4]}"
