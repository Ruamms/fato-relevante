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
    imoveis_atuais: list = field(default_factory=list)      # linhas do trimestre mais recente
    resultados: list = field(default_factory=list)          # resultados trimestrais (cronológico)
    tem_informe_trimestral: bool = False                    # fundo aparece no dataset trimestral
    situacao_cvm: str | None = None                         # situação no registro de fundos da CVM

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

    def meses_de_historico(self) -> int:
        return len(self.serie)

    def vacancia_atual(self) -> float | None:
        """Vacância física do trimestre mais recente, em %, ponderada por área.

        A CVM grava a vacância por imóvel como fração (1.0 = 100% vago);
        valores fora de [0, 1] são lixo auto-declarado e ficam de fora.
        """
        pares = [
            (linha["vacancia"], linha["area"] or 0)
            for linha in self.imoveis_atuais
            if linha["vacancia"] is not None and 0 <= linha["vacancia"] <= 1
        ]
        if not pares:
            return None
        area_total = sum(area for _, area in pares)
        if area_total > 0:
            return 100 * sum(v * area for v, area in pares) / area_total
        return 100 * sum(v for v, _ in pares) / len(pares)

    def resultado_financeiro_4t(self) -> float | None:
        return self._soma_trimestres("resultado_financeiro")

    def rendimentos_declarados_4t(self) -> float | None:
        return self._soma_trimestres("rendimentos_declarados")

    def resultado_acumulado_atual(self) -> float | None:
        """Resultado financeiro líquido ACUMULADO do trimestre mais recente —
        a 'reserva' que sustenta distribuição acima do resultado do período."""
        if not self.resultados:
            return None
        ultimo = self.resultados[-1]
        try:
            return ultimo["resultado_acumulado"]
        except (KeyError, IndexError):
            return None

    def _soma_trimestres(self, campo: str) -> float | None:
        ultimos = [linha[campo] for linha in self.resultados[-4:]]
        if len(ultimos) < 4 or any(valor is None for valor in ultimos):
            return None
        return sum(ultimos)

    def pvp_historico(self) -> list[float]:
        return [
            candle["fechamento"] / self.vp_ajustada[candle["competencia"]]
            for candle in self.cotacoes
            if candle["fechamento"] and self.vp_ajustada.get(candle["competencia"])
        ]
