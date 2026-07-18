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


_MESES_CURTOS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def competencia_br(competencia: str) -> str:
    return f"{competencia[5:7]}/{competencia[:4]}"


def competencia_curta(competencia: str) -> str:
    """AAAA-MM -> 'mai/26' (rótulo de eixo e tooltip)."""
    try:
        mes = int(competencia[5:7])
    except (ValueError, IndexError):
        return competencia
    if not 1 <= mes <= 12:
        return competencia
    return f"{_MESES_CURTOS[mes - 1]}/{competencia[2:4]}"


def idade_legivel(momento_iso: str | None, agora) -> str:
    """'2026-07-17 17:04' vs agora -> 'há 20 min' / 'há 3 h' / 'há 2 dias'."""
    from datetime import datetime

    if not momento_iso:
        return ""
    try:
        momento = datetime.fromisoformat(momento_iso)
    except ValueError:
        return ""
    segundos = (agora - momento).total_seconds()
    if segundos < 0:
        return ""
    if segundos < 3600:
        return f"há {max(1, int(segundos // 60))} min"
    if segundos < 48 * 3600:
        return f"há {int(segundos // 3600)} h"
    return f"há {int(segundos // 86400)} dias"


def dia_br(data_iso: str | None) -> str:
    if not data_iso or len(data_iso) < 10:
        return ""
    return f"{data_iso[8:10]}/{data_iso[5:7]}/{data_iso[:4]}"
