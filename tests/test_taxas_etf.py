"""Taxa de administração de ETFs — curadoria (dados/taxas_etfs.csv)."""

from datetime import datetime

from scout.coleta import taxas_etf
from scout.relatorio import etf_html, site

from tests.test_etfs import _semear_etf


def _escrever_csv(tmp_path, conteudo: str):
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "taxas_etfs.csv").write_text(conteudo, encoding="utf-8-sig")
    return tmp_path


def test_carrega_ticker_maiusculo_virgula_e_ponto(tmp_path):
    raiz = _escrever_csv(
        tmp_path,
        "ticker;taxa_adm_aa;fonte;verificado_em\n"
        "bova11;0,10;https://x/reg.pdf;2026-07-20\n"
        "IVVB11;0.23;;\n",
    )
    taxas = taxas_etf.carregar(raiz)
    assert taxas["BOVA11"]["taxa_adm_aa"] == 0.10
    assert taxas["BOVA11"]["fonte"] == "https://x/reg.pdf"
    assert taxas["BOVA11"]["verificado_em"] == "2026-07-20"
    assert taxas["IVVB11"]["taxa_adm_aa"] == 0.23


def test_descarta_vazio_e_absurdo(tmp_path):
    raiz = _escrever_csv(
        tmp_path,
        "ticker;taxa_adm_aa;fonte;verificado_em\n"
        "AAAA11;;fonte;\n"       # sem valor -> fora
        "BBBB11;150;fonte;\n"    # 150% a.a. é lixo -> fora
        ";0,30;fonte;\n"          # sem ticker -> fora
        "CCCC11;0,30;fonte;\n",  # válido
    )
    taxas = taxas_etf.carregar(raiz)
    assert set(taxas) == {"CCCC11"}


def test_csv_ausente_nao_quebra(tmp_path):
    assert taxas_etf.carregar(tmp_path) == {}


def test_card_de_taxa_aparece_na_pagina_do_etf(con):
    _semear_etf(con)
    classificacoes = {
        "10406511000161": {"classificacao_scout": "Ações Brasil", "observacoes": "", "gestor": "BLACKROCK"}
    }
    dados = etf_html.montar_dados_etf(con, "BOVA11", classificacoes)
    # injeta a curadoria (independe do CSV do repo, que começa vazio)
    dados["taxa_adm"] = {
        "taxa_adm_aa": 0.10,
        "fonte": "https://fnet.example/reg.pdf",
        "verificado_em": "2026-07-20",
    }
    pagina = etf_html.gerar(dados, agora=datetime(2026, 7, 20, 11, 0))
    assert "Taxa de administração" in pagina
    assert "0,10% a.a." in pagina
    assert 'href="https://fnet.example/reg.pdf"' in pagina


def test_sem_taxa_nao_mostra_card(con):
    _semear_etf(con)
    dados = etf_html.montar_dados_etf(con, "BOVA11", {})
    assert dados["taxa_adm"] is None  # CSV do repo vazio
    pagina = etf_html.gerar(dados, agora=datetime(2026, 7, 20, 11, 0))
    assert "Taxa de administração" not in pagina


def test_extrai_taxa_do_regulamento_anual():
    texto = (
        "CAPÍTULO VII\nA taxa de administração é de 0,30% (trinta centésimos por cento) "
        "ao ano, calculada sobre o patrimônio líquido do Fundo."
    )
    r = taxas_etf.extrair_taxa_regulamento(texto)
    assert r["taxa_adm_aa"] == 0.30
    assert r["confianca"] == "alta"


def test_prefere_trecho_anual_e_pula_mensal():
    # aparece primeiro uma taxa "ao mês" (armadilha) e depois a anual de verdade
    texto = (
        "A provisão da taxa de administração de 0,025% ao mês é feita diariamente. "
        "A taxa de administração máxima é de 0,50% a.a."
    )
    r = taxas_etf.extrair_taxa_regulamento(texto)
    assert r["taxa_adm_aa"] == 0.50
    assert r["confianca"] == "alta"


def test_extrai_com_ponto_decimal_e_sem_ano():
    texto = "Taxa de Administração: 0.23% do patrimônio líquido."
    r = taxas_etf.extrair_taxa_regulamento(texto)
    assert r["taxa_adm_aa"] == 0.23
    assert r["confianca"] == "media"


def test_acha_regulamento_entre_os_documentos():
    from scout.coleta import fnet

    docs = [
        {"id": 1, "tipo": "Relatório Gerencial", "categoria": "Relatório", "data_entrega": ""},
        {"id": 2, "tipo": "Regulamento", "categoria": "Documentos do Fundo", "data_entrega": ""},
    ]
    assert fnet.ultimo_regulamento(docs)["id"] == 2
    assert fnet.ultimo_regulamento(docs[:1]) is None


def test_nao_extrai_de_texto_sem_taxa_ou_absurdo():
    assert taxas_etf.extrair_taxa_regulamento("") is None
    assert taxas_etf.extrair_taxa_regulamento("Documento sem menção a tarifas.") is None
    # 20% não é taxa de administração de ETF (provavelmente taxa de performance)
    assert taxas_etf.extrair_taxa_regulamento("taxa de administração de 20% ao ano") is None


def test_indice_etfs_tem_coluna_taxa(con):
    _semear_etf(con)
    dados = etf_html.montar_dados_etf(con, "BOVA11", {"10406511000161": {"classificacao_scout": "Ações Brasil"}})
    dados["taxa_adm"] = {"taxa_adm_aa": 0.10, "fonte": "", "verificado_em": ""}
    html = site._indice_etfs([dados], datetime(2026, 7, 20, 11, 0))
    assert "<th>taxa</th>" in html
    assert "0,10% a.a." in html
