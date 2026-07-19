from datetime import date, datetime

import pytest

from scout import analise, armazenamento
from scout.coleta import b3, cotacoes, cvm


# --- fixtures COTAHIST -------------------------------------------------------------


def _linha_cotahist(data: str, codneg: str, fechamento_centavos: int, codbdi: str = "12") -> str:
    """Registro tipo 01 no layout posicional oficial (PREULT em [108:121])."""
    linha = "01" + data + codbdi + codneg.ljust(12)
    linha = linha.ljust(108, "0")
    linha += f"{fechamento_centavos:013d}"
    return linha.ljust(245, "0")


def _zip_cotahist(linhas: list[str]) -> bytes:
    import io
    import zipfile

    corpo = "00COTAHIST.2026BOVESPA".ljust(245) + "\n" + "\n".join(linhas) + "\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("COTAHIST_TESTE.TXT", corpo.encode("latin-1"))
    return buffer.getvalue()


# --- parser ------------------------------------------------------------------------


def test_extrair_pregoes_filtra_fiis():
    conteudo = _zip_cotahist(
        [
            _linha_cotahist("20260115", "TSTE11", 9000),
            _linha_cotahist("20260130", "TSTE11", 10000),
            _linha_cotahist("20260130", "PETR4", 3000),      # codneg não é de FII
            _linha_cotahist("20260130", "TSTE12", 500),      # direito de subscrição
            _linha_cotahist("20260130", "ACAO11", 7000, codbdi="02"),  # BDI não é FII
        ]
    )
    pregoes = b3.extrair_pregoes(conteudo, codbdis=("12",))
    assert list(pregoes) == ["TSTE11"]
    assert pregoes["TSTE11"] == [("2026-01-15", 90.0, 0.0), ("2026-01-30", 100.0, 0.0)]


def test_gravar_pregoes_agrega_por_mes_ultimo_pregao(con):
    b3.gravar_pregoes(
        con,
        {"TSTE11": [("2026-01-15", 90.0), ("2026-01-30", 95.0), ("2026-02-17", 100.0)]},
    )
    linhas = con.execute(
        "SELECT competencia, fechamento, dia FROM cotacoes_b3 WHERE ticker='TSTE11' ORDER BY competencia"
    ).fetchall()
    assert [(l[0], l[1], l[2]) for l in linhas] == [
        ("2026-01", 95.0, "2026-01-30"),  # vale o último pregão do mês
        ("2026-02", 100.0, "2026-02-17"),
    ]


def test_arquivos_pendentes_anuais_e_mes_corrente(con):
    hoje = date(2026, 2, 10)
    pendentes = b3.arquivos_pendentes(con, hoje)
    assert pendentes[0] == "COTAHIST_A2011.ZIP"
    assert "COTAHIST_A2025.ZIP" in pendentes
    assert "COTAHIST_A2026.ZIP" not in pendentes  # ano corrente vai por mensais
    assert pendentes[-2:] == ["COTAHIST_M012026.ZIP", "COTAHIST_M022026.ZIP"]

    # depois de carregado, só o mês corrente segue pendente
    for nome in pendentes:
        con.execute("INSERT OR REPLACE INTO cargas (arquivo, carregado_em) VALUES (?, 'x')", (nome,))
    con.commit()
    assert b3.arquivos_pendentes(con, hoje) == ["COTAHIST_M022026.ZIP"]


# --- derivadas (ajustes) -----------------------------------------------------------


def test_recalcular_derivadas_ajusta_desdobramento_e_proventos(con, zip_cvm):
    cvm.carregar_zip(con, zip_cvm(True), "inf_mensal_fii_2026.zip")  # dy 0.008/0.007, vp 100.5/95.45
    b3.gravar_pregoes(
        con,
        {"TSTE11": [("2026-01-30", 90.0), ("2026-02-17", 100.0)]},
    )
    b3.recalcular_derivadas(con, agora=datetime(2026, 2, 18, 10, 0))
    serie = armazenamento.serie_cotacoes(con, "TSTE11")
    assert [(l["competencia"], l["fechamento"]) for l in serie] == [("2026-01", 90.0), ("2026-02", 100.0)]
    # retorno total: âncora no último = 100; prov fev = dy 0.011 × vp 95.45 ≈ 1.05
    # adj(jan) = 100 × 90 / (100 + 1.05) ≈ 89.06
    assert serie[0]["fechamento_ajustado"] == pytest.approx(89.06, abs=0.01)
    assert serie[1]["fechamento_ajustado"] == 100.0
    meta = armazenamento.cotacao_meta(con, "TSTE11")
    assert meta["preco_atual"] == 100.0
    assert meta["cotado_em"] == "2026-02-17"


def test_recalcular_derivadas_neutraliza_desdobramento(con):
    # resíduo de fonte anterior (Yahoo) deve sumir: a série vira 100% B3
    armazenamento.gravar_cotacoes(
        con, "NOVO11", [("2020-05", 55.0, 55.0)], 55.0, "2020-05-29", "2020-05-30"
    )
    # cota a R$ 1.000 desdobra 10:1 -> R$ 105 (sem informes CVM: sem proventos)
    b3.gravar_pregoes(
        con,
        {"NOVO11": [("2025-12-30", 1000.0), ("2026-01-30", 105.0), ("2026-02-17", 110.0)]},
    )
    b3.recalcular_derivadas(con, agora=datetime(2026, 2, 18, 10, 0))
    serie = armazenamento.serie_cotacoes(con, "NOVO11")
    assert len(serie) == 3  # o mês residual de 2020 (fonte antiga) sumiu
    # como no ajuste de VP, o mês pré-split é ancorado no valor pós-split
    assert serie[0]["fechamento"] == pytest.approx(105.0)
    assert serie[1]["fechamento"] == 105.0
    # sem salto falso: variação dez->jan vira 0%, não -89,5%
    assert serie[0]["fechamento_ajustado"] == pytest.approx(105.0)


# --- garantia diária ---------------------------------------------------------------


def test_garantir_mes_corrente_uma_vez_por_dia(con, monkeypatch):
    chamadas = []

    def _baixar_fake(nome, tentativas=3):
        chamadas.append(nome)
        return _zip_cotahist([_linha_cotahist("20260217", "TSTE11", 10100)])

    monkeypatch.setattr(b3, "_baixar", _baixar_fake)
    agora = datetime(2026, 2, 18, 10, 0)
    assert b3.garantir_mes_corrente(con, agora) is None
    assert chamadas == ["COTAHIST_M022026.ZIP"]
    # segunda chamada no mesmo dia: nada a fazer
    assert b3.garantir_mes_corrente(con, agora) is None
    assert chamadas == ["COTAHIST_M022026.ZIP"]
    meta = armazenamento.cotacao_meta(con, "TSTE11")
    assert meta["preco_atual"] == 101.0


def test_garantir_atualizada_avisa_sem_rede_e_sem_ticker(con, monkeypatch):
    def _falha(nome, tentativas=3):
        raise OSError("sem rede")

    monkeypatch.setattr(b3, "_baixar", _falha)
    # sem nada no cache: orienta a rodar o atualizar
    aviso = cotacoes.garantir_atualizada(con, "TSTE11", agora=datetime(2026, 2, 18, 10, 0))
    assert "indisponível" in aviso

    # com cache: avisa que está usando o preço antigo
    armazenamento.gravar_cotacoes(con, "TSTE11", [], 101.0, "2026-02-17", "2026-02-18T09:00:00")
    aviso = cotacoes.garantir_atualizada(con, "TSTE11", agora=datetime(2026, 2, 18, 10, 0))
    assert aviso is not None and "17/02/2026" in aviso


# --- séries e raio-x (inalterados na essência) --------------------------------------


def test_serie_vp_ajustada_neutraliza_desdobramento():
    from scout import series

    serie = [
        dict(competencia="2019-10", vp_cota=1600.0),
        dict(competencia="2019-11", vp_cota=1660.0),
        dict(competencia="2019-12", vp_cota=166.0),  # desdobramento 10:1
        dict(competencia="2020-01", vp_cota=168.0),
    ]
    ajustada = series.serie_vp_ajustada(serie)
    assert ajustada["2019-12"] == 166.0
    assert ajustada["2020-01"] == 168.0
    assert ajustada["2019-11"] == pytest.approx(166.0)
    assert ajustada["2019-10"] == pytest.approx(160.0)


def test_raio_x_com_cotacao_traz_pvp(con, zip_cvm):
    cvm.carregar_zip(con, zip_cvm(True), "inf_mensal_fii_2026.zip")
    armazenamento.gravar_cotacoes(
        con,
        "TSTE11",
        [("2026-01", 90.0, 90.0), ("2026-02", 100.0, 100.0)],
        100.0,
        "2026-02-17",
        "2026-02-18",
    )
    raiox = analise.montar_raio_x(con, "tste11")
    nomes = [linha.nome for linha in raiox.indicadores]
    assert nomes[0] == "Cotação"
    assert nomes[1] == "P/VP"
    cotacao = raiox.indicadores[0]
    assert cotacao.atual == "R$ 100,00"
    pvp = raiox.indicadores[1]
    # vp_cota atual da fixture = 95.45 -> P/VP = 100 / 95.45 = 1.05
    assert pvp.atual == "1,05"
    assert raiox.cotacao_em == "17/02/2026"


def test_raio_x_sem_cotacao_avisa_em_nota(con, zip_cvm):
    cvm.carregar_zip(con, zip_cvm(True), "inf_mensal_fii_2026.zip")
    raiox = analise.montar_raio_x(con, "tste11")
    assert not any(linha.nome == "Cotação" for linha in raiox.indicadores)
    assert any("sem cotação de bolsa" in nota for nota in raiox.notas)
