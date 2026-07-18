"""Contexto compartilhado que as regras de red flag recebem para avaliar."""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import series


@dataclass
class Contexto:
    """Séries do fundo já carregadas do cache local.

    `serie` são as linhas do informe complemento (ordem cronológica);
    `cotacoes` são os candles mensais; `vp_ajustada` é o VP/cota com
    desdobramentos neutralizados, indexado por competência.
    """

    serie: list
    vp_ajustada: dict[str, float] = field(default_factory=dict)
    cotacoes: list = field(default_factory=list)
    preco_atual: float | None = None

    def dy_acumulado_12m(self) -> float | None:
        if len(self.serie) < 12:
            return None
        return series.dy_acumulado(self.serie, 12)

    def meses_com_distribuicao_12m(self) -> int | None:
        if len(self.serie) < 12:
            return None
        return sum(
            1
            for linha in self.serie[-12:]
            if series.dy_valido(linha["dy_mes"]) and linha["dy_mes"] > 0
        )

    def variacao_vp(self, meses: int) -> float | None:
        return series.variacao_vp_ajustado(self.vp_ajustada, meses)

    def variacao_cotas(self, meses: int) -> float | None:
        return series.variacao_pct(self.serie, "cotas_emitidas", meses)

    def cotistas(self) -> float | None:
        if not self.serie:
            return None
        return self.serie[-1]["cotistas"]

    def pvp_atual(self) -> float | None:
        if self.preco_atual is None or not self.serie:
            return None
        vp = self.serie[-1]["vp_cota"]
        if not vp:
            return None
        return self.preco_atual / vp

    def pvp_historico(self) -> list[float]:
        return [
            candle["fechamento"] / self.vp_ajustada[candle["competencia"]]
            for candle in self.cotacoes
            if candle["fechamento"] and self.vp_ajustada.get(candle["competencia"])
        ]
