"""Resolvedor único de preço + reprecificação da carteira do ETF."""

from scout import armazenamento, precos


def test_reprecifica_acao_e_fii_e_deixa_rf_sem_preco(con):
    # já temos preço diário de ação e FII na base (COTAHIST)
    armazenamento.gravar_cotacoes(con, "PETR4", [("2026-06", 40.0, 40.0)], 40.9, "2026-07-17", "2026-07-17T20:00")
    armazenamento.gravar_cotacoes(con, "MXRF11", [("2026-06", 9.0, 9.0)], 9.73, "2026-07-17", "2026-07-17T20:00")

    posicoes = [
        {"codigo": "PETR4", "ticker_alvo": None, "pct": 50.0, "quantidade": 100},   # ação pelo código
        {"codigo": "", "ticker_alvo": "MXRF11", "pct": 30.0, "quantidade": 200},    # FII pelo alvo resolvido
        {"codigo": "TESOURO2029", "ticker_alvo": None, "pct": 20.0, "quantidade": 5},  # RF: sem preço por ativo
    ]
    enriquecidas, resumo = precos.reprecificar_posicoes(con, posicoes)

    assert enriquecidas[0]["preco_hoje"] == 40.9
    assert enriquecidas[0]["valor_hoje"] == 40.9 * 100
    assert enriquecidas[0]["cotado_em"] == "2026-07-17"
    assert enriquecidas[1]["preco_hoje"] == 9.73
    assert enriquecidas[1]["valor_hoje"] == 9.73 * 200
    # renda fixa não tem preço por ativo -> fica None (cai no valor do CDA)
    assert enriquecidas[2]["preco_hoje"] is None
    assert enriquecidas[2]["valor_hoje"] is None
    # cobertura = peso da carteira que tem preço de hoje (ação 50% + FII 30%)
    assert resumo["cobertura_pct"] == 80.0
    assert resumo["valor_hoje_total"] == 40.9 * 100 + 9.73 * 200


def test_ticker_para_preco_so_reconhece_acao_valida():
    assert precos.ticker_para_preco({"codigo": "VALE3", "ticker_alvo": None}) == "VALE3"
    assert precos.ticker_para_preco({"codigo": "", "ticker_alvo": "HGLG11"}) == "HGLG11"
    # código que não é padrão de ação e sem alvo -> None (não busca preço à toa)
    assert precos.ticker_para_preco({"codigo": "LTN 010129", "ticker_alvo": None}) is None
    assert precos.ticker_para_preco({"codigo": "", "ticker_alvo": None}) is None


def test_sem_cotacao_na_base_nao_inventa_preco(con):
    enriquecidas, resumo = precos.reprecificar_posicoes(
        con, [{"codigo": "PETR4", "ticker_alvo": None, "pct": 100.0, "quantidade": 10}]
    )
    assert enriquecidas[0]["preco_hoje"] is None  # ticker existe, mas não temos cotação
    assert resumo["cobertura_pct"] == 0.0
