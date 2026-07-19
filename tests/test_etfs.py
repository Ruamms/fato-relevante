from datetime import date

from scout.coleta import b3fundos


def _lista_fake(tipo: str) -> list[dict]:
    if tipo == "ETF":
        return [
            {"id": 9253, "acronym": "BMMT", "fundName": "B-INDEX MOMENTO FUNDO DE ÍNDICE", "tradingName": "B INDEX MOME"},
            {"id": 1234, "acronym": "BOVA", "fundName": "ISHARES IBOVESPA FUNDO DE ÍNDICE", "tradingName": "ISHARES BOVA"},
        ]
    if tipo == "ETF-RF":
        return [
            {"id": 5678, "acronym": "IMAB", "fundName": "IT NOW IMA-B FUNDO DE ÍNDICE RF", "tradingName": "IT NOW IMAB"},
        ]
    if tipo == "ETF-Cripto":
        return [
            {"id": 9012, "acronym": "HASH", "fundName": "HASHDEX NASDAQ CRYPTO INDEX FUNDO DE ÍNDICE", "tradingName": "HASHDEX NCI"},
        ]
    return []


_DETALHES = {
    9253: {"tradingCode": "BMMT11", "cnpj": "48.643.091/0001-00"},
    1234: {"tradingCode": "BOVA11", "cnpj": "10.406.511/0001-61"},
    5678: {"tradingCode": "IMAB11", "cnpj": "30.360.294/0001-56"},
    9012: {"tradingCode": "HASH11", "cnpj": "40.101.777/0001-72"},
}


def test_atualizar_etfs_grava_ticker_cnpj_e_tipo(con, monkeypatch):
    chamadas_detalhe = []

    def _detalhar_fake(id_fnet, radical, tipo):
        chamadas_detalhe.append(id_fnet)
        return _DETALHES[id_fnet]

    monkeypatch.setattr(b3fundos, "listar", _lista_fake)
    monkeypatch.setattr(b3fundos, "detalhar", _detalhar_fake)
    monkeypatch.setattr(b3fundos.time, "sleep", lambda s: None)

    mensagem = b3fundos.atualizar_etfs(con, hoje=date(2026, 7, 19))
    assert "4 no total" in mensagem
    linhas = {
        linha["ticker"]: linha
        for linha in con.execute("SELECT * FROM etfs").fetchall()
    }
    assert linhas["BOVA11"]["cnpj"] == "10406511000161"
    assert linhas["BOVA11"]["tipo_b3"] == "ETF"
    assert linhas["IMAB11"]["tipo_b3"] == "ETF-RF"
    assert linhas["HASH11"]["tipo_b3"] == "ETF-Cripto"
    assert linhas["BMMT11"]["radical"] == "BMMT"

    # mesma semana: não consulta a rede de novo
    chamadas_detalhe.clear()
    assert b3fundos.atualizar_etfs(con, hoje=date(2026, 7, 20)) is None
    assert chamadas_detalhe == []

    # semana seguinte: refresh, mas detalhe só de quem for NOVO
    assert b3fundos.atualizar_etfs(con, hoje=date(2026, 7, 27)) is not None
    assert chamadas_detalhe == []


def test_cotahist_codbdi_14_entra_como_etf(con):
    from tests.test_cotacoes import _linha_cotahist, _zip_cotahist

    conteudo = _zip_cotahist(
        [
            _linha_cotahist("20260630", "TSTE11", 10000, codbdi="12"),
            _linha_cotahist("20260630", "BOVA11", 16912, codbdi="14"),
            _linha_cotahist("20260630", "PETR4", 3000, codbdi="02"),
        ]
    )
    from scout.coleta import b3

    pregoes = b3.extrair_pregoes(conteudo)
    assert set(pregoes) == {"TSTE11", "BOVA11"}
    assert pregoes["BOVA11"] == [("2026-06-30", 169.12)]
