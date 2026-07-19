"""Reclassificação automática de ETF (cda.reclassificar) — determinístico,
palavra-chave nas posições e IA local como último recurso, com rastro."""

from datetime import date

from scout.coleta import cda


def _pos(nome, codigo="", pct=10.0):
    return {"nome": nome, "codigo": codigo, "cnpj_emissor": "", "pct": pct}


# --- alvo determinístico (função pura) ---------------------------------------

def test_alvo_por_segmento_manda():
    # ETF-RF classificado como ação: vira renda fixa (ou RF intl se for exterior)
    assert cda._alvo_deterministico("Ações Brasil", {"Renda Fixa": 90}, "ETF-RF", []) == (
        "Renda Fixa", "segmento oficial da B3 é ETF-RF",
    )
    alvo, _ = cda._alvo_deterministico("Ações Brasil", {"Exterior": 90}, "ETF-RF", [])
    assert alvo == "Renda Fixa Internacional"


def test_alvo_por_grupo_1_para_1():
    assert cda._alvo_deterministico("Ações Brasil", {"Renda Fixa": 88}, "ETF", [])[0] == "Renda Fixa"
    assert cda._alvo_deterministico("Ações Brasil", {"Cotas de Fundos": 75}, "ETF", [])[0] == "FIIs (índice)"


def test_alvo_por_palavra_chave_nas_posicoes():
    # grupo Exterior é ambíguo — o NOME da posição desempata
    cripto = cda._alvo_deterministico(
        "Ações Brasil", {"Exterior": 95}, "ETF", [_pos("HASHDEX BITCOIN")]
    )
    assert cripto[0] == "Cripto" and "BITCOIN".lower() in cripto[1].lower()
    acoes = cda._alvo_deterministico(
        "Ações Brasil", {"Exterior": 95}, "ETF", [_pos("ISHARES CORE S&P 500")]
    )
    assert acoes[0] == "Ações Internacionais"
    commod = cda._alvo_deterministico("Ações Brasil", {"Exterior": 95}, "ETF", [_pos("SPDR GOLD")])
    assert commod[0] == "Commodities"


def test_exterior_sem_palavra_chave_fica_ambiguo():
    # sem pista no nome, o determinístico não chuta (vira caso da IA)
    assert cda._alvo_deterministico("Ações Brasil", {"Exterior": 95}, "ETF", [_pos("FUNDO XPTO")]) is None


# --- orquestrador reclassificar (com rastro em disco) ------------------------

def _isolar_dados(monkeypatch, tmp_path):
    monkeypatch.setenv("SCOUT_DATA_DIR", str(tmp_path))


def test_reclassifica_segmento_e_grava_rastro(monkeypatch, tmp_path):
    _isolar_dados(monkeypatch, tmp_path)
    classificacoes = {
        "1": {"cnpj": "1", "ticker": "AUPO11", "classificacao_scout": "Ações Brasil", "segmento_b3": "ETF-RF"},
    }
    mudancas = cda.reclassificar(
        {"1": {"Renda Fixa": 92}}, {"1": []}, classificacoes,
        hoje=date(2026, 7, 20), usar_ia=False,
    )
    assert mudancas == [
        {"ticker": "AUPO11", "de": "Ações Brasil", "para": "Renda Fixa",
         "origem": "auto", "motivo": "segmento oficial da B3 é ETF-RF"}
    ]
    # rastro persistido e recuperável
    reg = cda.carregar_reclassificacoes()
    assert reg["1"]["classe_anterior"] == "Ações Brasil"
    assert reg["1"]["classe_nova"] == "Renda Fixa"
    assert reg["1"]["origem"] == "auto"
    assert reg["1"]["data"] == "2026-07-20"


def test_decide_uma_vez_nao_re_rola(monkeypatch, tmp_path):
    _isolar_dados(monkeypatch, tmp_path)
    classificacoes = {"1": {"cnpj": "1", "ticker": "AUPO11", "classificacao_scout": "Ações Brasil", "segmento_b3": "ETF-RF"}}
    comp = {"1": {"Renda Fixa": 92}}
    assert len(cda.reclassificar(comp, {"1": []}, classificacoes, hoje=date(2026, 7, 20), usar_ia=False)) == 1
    # segunda rodada: já tem rastro -> não mexe de novo
    assert cda.reclassificar(comp, {"1": []}, classificacoes, hoje=date(2026, 8, 20), usar_ia=False) == []


def test_ponto_de_atencao_nao_reclassifica(monkeypatch, tmp_path):
    _isolar_dados(monkeypatch, tmp_path)
    # fundo novo ~100% RF em captação é "atenção", não divergência dura
    classificacoes = {"1": {"cnpj": "1", "ticker": "XPTO11", "classificacao_scout": "Ações Brasil", "segmento_b3": "ETF"}}
    mudancas = cda.reclassificar({"1": {"Renda Fixa": 98}}, {"1": []}, classificacoes, hoje=date(2026, 7, 20), usar_ia=False)
    assert mudancas == []


def test_ia_desempata_o_exterior_ambiguo(monkeypatch, tmp_path):
    _isolar_dados(monkeypatch, tmp_path)
    from scout import ia as modulo_ia

    chamadas = {"n": 0}

    def _fake_classificar(ticker, posicoes, candidatas, modelo=None):
        chamadas["n"] += 1
        assert set(candidatas) == set(cda._CANDIDATAS_EXTERIOR)
        return "Cripto", "as posições são fundos de bitcoin"

    monkeypatch.setattr(modulo_ia, "classificar_etf", _fake_classificar)
    classificacoes = {"1": {"cnpj": "1", "ticker": "QBTC11", "classificacao_scout": "Ações Brasil", "segmento_b3": "ETF"}}
    # Exterior sem palavra-chave -> cai na IA
    mudancas = cda.reclassificar(
        {"1": {"Exterior": 96}}, {"1": [_pos("FUNDO OPACO LTDA")]}, classificacoes,
        hoje=date(2026, 7, 20), usar_ia=True,
    )
    assert chamadas["n"] == 1
    assert mudancas[0]["para"] == "Cripto" and mudancas[0]["origem"] == "ia"
    assert cda.carregar_reclassificacoes()["1"]["origem"] == "ia"


def test_sem_ia_o_ambiguo_fica_para_revisao(monkeypatch, tmp_path):
    _isolar_dados(monkeypatch, tmp_path)
    classificacoes = {"1": {"cnpj": "1", "ticker": "QBTC11", "classificacao_scout": "Ações Brasil", "segmento_b3": "ETF"}}
    mudancas = cda.reclassificar(
        {"1": {"Exterior": 96}}, {"1": [_pos("FUNDO OPACO LTDA")]}, classificacoes,
        hoje=date(2026, 7, 20), usar_ia=False,
    )
    assert mudancas == []  # não chuta; segue como divergência de revisão manual


def test_overlay_reflete_na_curadoria_carregada(monkeypatch, tmp_path):
    _isolar_dados(monkeypatch, tmp_path)
    # pega um CNPJ real da curadoria e reclassifica -> carregar_classificacoes reflete
    base = cda.carregar_classificacoes()
    cnpj = next(iter(base))
    cda.registrar_reclassificacao(cnpj, base[cnpj].get("ticker", ""), "X", "Cripto", "auto", "motivo", "2026-07-20")
    recarregado = cda.carregar_classificacoes()
    assert recarregado[cnpj]["classificacao_scout"] == "Cripto"
    assert recarregado[cnpj]["reclassificado"]["origem"] == "auto"


def test_selo_de_reclassificacao_aparece_na_pagina(con, monkeypatch, tmp_path):
    _isolar_dados(monkeypatch, tmp_path)
    from tests.test_etfs import _semear_etf
    from scout.relatorio import etf_html

    _semear_etf(con)  # BOVA11, cnpj 10406511000161
    cda.registrar_reclassificacao(
        "10406511000161", "BOVA11", "Ações Brasil", "Ações Internacionais",
        "ia", "posição “ISHARES S&P 500” indica ações internacionais", "2026-07-20",
    )
    classificacoes = {
        "10406511000161": {"ticker": "BOVA11", "classificacao_scout": "Ações Brasil", "segmento_b3": "ETF"}
    }
    # overlay manual (a curadoria de teste não tem a linha): simula o loader
    entrada = cda.carregar_reclassificacoes()["10406511000161"]
    classificacoes["10406511000161"]["classificacao_scout"] = entrada["classe_nova"]
    classificacoes["10406511000161"]["reclassificado"] = entrada
    dados = etf_html.montar_dados_etf(con, "BOVA11", classificacoes)
    assert dados["reclassificado"]["origem"] == "ia"
    pagina = etf_html.gerar(dados)
    assert "reclassificado em 20/07/2026 por leitura das posições pela IA" in pagina
    assert "antes: Ações Brasil" in pagina
