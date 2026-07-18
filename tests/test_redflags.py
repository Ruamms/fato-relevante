from scout import redflags, series
from scout.modelos import Severidade
from scout.redflags import (
    cotistas,
    diluicao,
    distribuicao,
    pvp_faixa,
    rendimento,
    vp_queda,
)
from scout.redflags.contexto import Contexto


def _serie(meses: int, vp=100.0, dy=0.008, cotas=1000.0, cotistas_=1000.0, **por_mes):
    """Série mensal sintética terminando em 2026-06.

    `por_mes` permite sobrescrever campos por índice: vp_5=90 muda o
    vp_cota do 6º mês (índice 5).
    """
    linhas = []
    for indice in range(meses):
        total = 2026 * 12 + 5 - (meses - 1 - indice)  # 2026-06 é o último
        competencia = f"{total // 12:04d}-{total % 12 + 1:02d}"
        linhas.append(
            {
                "competencia": competencia,
                "vp_cota": por_mes.get(f"vp_{indice}", vp),
                "dy_mes": por_mes.get(f"dy_{indice}", dy),
                "cotas_emitidas": por_mes.get(f"cotas_{indice}", cotas),
                "cotistas": cotistas_,
                "patrimonio_liquido": vp * cotas,
                "valor_ativo": vp * cotas,
                "amortizacao_mes": None,
                "rentab_patrimonial_mes": None,
            }
        )
    return linhas


def _contexto(serie, **kwargs):
    return Contexto(serie=serie, vp_ajustada=series.serie_vp_ajustada(serie), **kwargs)


# --- distribuição vs patrimônio ----------------------------------------------


def test_distribuicao_dispara_quando_vp_cai_distribuindo():
    serie = _serie(14, vp=100.0, dy=0.009)
    for indice in range(14):  # VP derretendo ~1%/mês
        serie[indice]["vp_cota"] = 100.0 - indice
    ctx = _contexto(serie)
    flag = distribuicao.avaliar(ctx)
    assert flag is not None
    assert flag.severidade == Severidade.ALTA
    assert "12 meses" in flag.fato
    assert flag.evidencia


def test_distribuicao_nao_dispara_com_vp_estavel():
    ctx = _contexto(_serie(14, vp=100.0, dy=0.009))
    assert distribuicao.aplicavel(ctx)
    assert distribuicao.avaliar(ctx) is None


def test_distribuicao_nao_aplicavel_com_serie_curta():
    assert not distribuicao.aplicavel(_contexto(_serie(3)))


# --- diluição -----------------------------------------------------------------


def test_diluicao_dispara_com_emissao_e_vp_caindo():
    serie = _serie(26, vp=100.0)
    for indice, linha in enumerate(serie):
        linha["cotas_emitidas"] = 1000.0 + indice * 20  # +50% no período
        linha["vp_cota"] = 100.0 - indice * 0.5  # VP -12,5%
    flag = diluicao.avaliar(_contexto(serie))
    assert flag is not None
    assert flag.severidade == Severidade.MEDIA
    assert "cotas" in flag.fato


def test_diluicao_nao_dispara_quando_emissao_preserva_vp():
    serie = _serie(26)
    for indice, linha in enumerate(serie):
        linha["cotas_emitidas"] = 1000.0 + indice * 20
    assert diluicao.avaliar(_contexto(serie)) is None


# --- queda de VP ---------------------------------------------------------------


def test_vp_queda_grave_e_severidade_alta():
    serie = _serie(14, vp=100.0)
    for linha in serie[-6:]:
        linha["vp_cota"] = 75.0  # -25% vs 12m atrás
    flag = vp_queda.avaliar(_contexto(serie))
    assert flag is not None
    assert flag.severidade == Severidade.ALTA


def test_vp_estavel_aprova():
    assert vp_queda.avaliar(_contexto(_serie(14))) is None


# --- cotistas ------------------------------------------------------------------


def test_menos_de_100_cotistas_e_alerta_alto_de_ir():
    flag = cotistas.avaliar(_contexto(_serie(2, cotistas_=80)))
    assert flag is not None
    assert flag.severidade == Severidade.ALTA
    assert "isenção" in flag.fato


def test_base_pequena_e_alerta_baixo():
    flag = cotistas.avaliar(_contexto(_serie(2, cotistas_=153)))
    assert flag is not None
    assert flag.severidade == Severidade.BAIXA


def test_base_grande_aprova():
    assert cotistas.avaliar(_contexto(_serie(2, cotistas_=10_000))) is None


# --- P/VP vs faixa histórica ----------------------------------------------------


def _cotacoes(serie, fator: float):
    return [
        {"competencia": linha["competencia"], "fechamento": linha["vp_cota"] * fator}
        for linha in serie
    ]


def test_pvp_com_premio_extremo_dispara():
    serie = _serie(30, vp=100.0)
    ctx = _contexto(serie, cotacoes=_cotacoes(serie, 1.0), preco_atual=150.0)
    flag = pvp_faixa.avaliar(ctx)
    assert flag is not None
    assert "prêmio" in flag.fato


def test_pvp_dentro_da_faixa_aprova():
    serie = _serie(30, vp=100.0)
    ctx = _contexto(serie, cotacoes=_cotacoes(serie, 1.0), preco_atual=105.0)
    assert pvp_faixa.aplicavel(ctx)
    assert pvp_faixa.avaliar(ctx) is None


def test_pvp_nao_aplicavel_sem_cotacao():
    ctx = _contexto(_serie(30))
    assert not pvp_faixa.aplicavel(ctx)


# --- regularidade do rendimento -------------------------------------------------


def test_rendimento_interrompido_dispara():
    serie = _serie(12)
    for linha in serie[-5:]:
        linha["dy_mes"] = 0.0
    flag = rendimento.avaliar(_contexto(serie))
    assert flag is not None
    assert "7 dos últimos 12" in flag.fato


def test_rendimento_regular_aprova():
    assert rendimento.avaliar(_contexto(_serie(12))) is None


# --- motor ----------------------------------------------------------------------


def test_motor_separa_flags_aprovadas_e_nao_avaliadas():
    serie = _serie(14, cotistas_=80)  # sem cotações -> P/VP não avaliável
    resultado = redflags.avaliar(_contexto(serie))
    codigos = [flag.codigo for flag in resultado.flags]
    assert "cotistas" in codigos
    assert pvp_faixa.NOME in resultado.nao_avaliadas
    assert rendimento.OK in resultado.aprovadas


def test_motor_ordena_por_severidade():
    serie = _serie(14, cotistas_=80)  # ALTA (cotistas)
    for linha in serie[-5:]:
        linha["dy_mes"] = 0.0  # BAIXA/MÉDIA (rendimento)
    resultado = redflags.avaliar(_contexto(serie))
    severidades = [flag.severidade for flag in resultado.flags]
    assert severidades == sorted(
        severidades, key=lambda s: {Severidade.ALTA: 0, Severidade.MEDIA: 1, Severidade.BAIXA: 2}[s]
    )