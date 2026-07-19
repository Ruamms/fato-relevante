"""Classificação determinística do parecer do auditor independente.

Lê o texto das Demonstrações Financeiras (FNET) e identifica o tipo de
opinião do auditor — sem IA: são fórmulas normatizadas (NBC TA 700/705/570),
e regex sobre elas é mais confiável e auditável que um modelo. O trecho
citado permite conferir no PDF original.
"""

from __future__ import annotations

import re
import unicodedata

# ordem importa: da opinião mais grave para a mais branda
_TIPOS = [
    ("abstencao", r"abstencao de opiniao|nao expressamos opiniao"),
    ("adversa", r"opiniao adversa"),
    ("ressalva", r"opiniao com ressalva|exceto pelo|exceto quanto"),
    ("sem_ressalva", r"em todos os aspectos relevantes|opiniao sobre as demonstracoes|nossa opiniao"),
]

ROTULOS = {
    "abstencao": "abstenção de opinião",
    "adversa": "opinião adversa",
    "ressalva": "opinião com ressalva",
    "sem_ressalva": "opinião sem ressalvas",
    "nao_identificado": "parecer não identificado no texto",
}

# gravidade para exibição: True = merece destaque de alerta
GRAVE = {"abstencao", "adversa", "ressalva"}

_CONTINUIDADE = r"incerteza (?:relevante )?(?:relacionada|quanto) .{0,40}continuidade operacional"


def _normalizar(texto: str) -> str:
    """minúsculas, sem acentos e com espaços colapsados — regex estável."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento.lower())


def _trecho_original(texto: str, padrao_normalizado: str) -> str:
    """Frase do texto ORIGINAL em torno da primeira menção a 'opinião'."""
    encontro = re.search(r"[^.]*opini[ãa]o[^.]*\.", texto, flags=re.IGNORECASE)
    if not encontro:
        return ""
    frase = re.sub(r"\s+", " ", encontro.group(0)).strip()
    return frase[:400]


def classificar(texto: str) -> dict:
    """{tipo, rotulo, grave, continuidade, trecho} a partir do texto da DF."""
    normalizado = _normalizar(texto)
    tipo = "nao_identificado"
    for candidato, padrao in _TIPOS:
        if re.search(padrao, normalizado):
            tipo = candidato
            break
    continuidade = bool(re.search(_CONTINUIDADE, normalizado))
    return {
        "tipo": tipo,
        "rotulo": ROTULOS[tipo],
        "grave": tipo in GRAVE,
        "continuidade": continuidade,
        "trecho": _trecho_original(texto, tipo) if tipo != "nao_identificado" else "",
    }
