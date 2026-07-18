from datetime import datetime

from scout import armazenamento
from scout.coleta import cvm
from scout.relatorio import site
from conftest import montar_zip_universo


def _base(con):
    cvm.carregar_zip(con, montar_zip_universo(), "inf_mensal_fii_2026.zip")
    armazenamento.gravar_cotacoes(
        con,
        "ALFA11",
        [("2026-01", 90.0, 90.0), ("2026-02", 100.0, 100.0)],
        100.0,
        "2026-02-17",
        "2026-02-18",
    )
    return con


def test_gerar_site_completo(con, tmp_path):
    _base(con)
    resumo = site.gerar(
        con, tmp_path / "site", com_cotacoes=False, agora=datetime(2026, 7, 18, 7, 0)
    )
    pasta = tmp_path / "site"
    assert resumo["paginas"] == 3
    assert (pasta / "index.html").exists()
    assert (pasta / "ALFA11.html").exists()
    assert (pasta / "BETA11.html").exists()
    assert (pasta / "apoie.html").exists()

    indice = (pasta / "index.html").read_text(encoding="utf-8")
    assert "3 fundos negociáveis" in indice
    assert 'href="ALFA11.html"' in indice
    assert "atualizado em 18/07/2026 07:00" in indice
    # busca client-side e rankings
    assert 'id="busca"' in indice
    assert "function filtrar" in indice
    assert "Rankings do dia" in indice
    assert "Maiores patrimônios" in indice
    assert "não recomendação" in indice
    # linha com dados de busca em minúsculas
    assert 'data-busca="alfa11 alfa fii shoppings"' in indice
    # botão de atualização manual + status ao vivo via API pública do GitHub
    assert "Atualizar agora" in indice
    assert "actions/workflows/site.yml" in indice
    assert "async function statusAtualizacao" in indice
    assert 'id="atu-barra"' in indice


def test_gerar_site_com_callback_de_progresso(con, tmp_path):
    _base(con)
    chamadas = []
    site.gerar(
        con,
        tmp_path / "site",
        com_cotacoes=False,
        ao_item=lambda fase, atual, total: chamadas.append((fase, atual, total)),
    )
    assert ("páginas", 1, 3) in chamadas
    assert ("páginas", 3, 3) in chamadas


def test_gerar_site_com_limite(con, tmp_path):
    _base(con)
    resumo = site.gerar(con, tmp_path / "site", com_cotacoes=False, limite=1)
    # só o maior fundo por PL (BETA) vira página
    assert resumo["paginas"] == 1
    assert (tmp_path / "site" / "BETA11.html").exists()
    assert not (tmp_path / "site" / "ALFA11.html").exists()


def test_pagina_do_fundo_no_site_tem_pares_via_varredura(con, tmp_path):
    _base(con)
    site.gerar(con, tmp_path / "site", com_cotacoes=False)
    pagina = (tmp_path / "site" / "ALFA11.html").read_text(encoding="utf-8")
    # pares do segmento calculados a partir da varredura pré-computada
    assert "Pares do segmento" in pagina
    assert 'href="BETA11.html"' in pagina
