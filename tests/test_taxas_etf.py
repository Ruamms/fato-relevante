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


def test_indice_etfs_tem_coluna_taxa(con):
    _semear_etf(con)
    dados = etf_html.montar_dados_etf(con, "BOVA11", {"10406511000161": {"classificacao_scout": "Ações Brasil"}})
    dados["taxa_adm"] = {"taxa_adm_aa": 0.10, "fonte": "", "verificado_em": ""}
    html = site._indice_etfs([dados], datetime(2026, 7, 20, 11, 0))
    assert "<th>taxa</th>" in html
    assert "0,10% a.a." in html
