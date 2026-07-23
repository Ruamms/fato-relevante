"""O que o FII tem dentro — relação de ativos do informe ANUAL (FoF/papel)."""

import io
import zipfile
from datetime import datetime

from conftest import montar_zip_universo

from scout import analise, armazenamento
from scout.coleta import cvm
from scout.relatorio import html as relatorio_html


def _zip_anual(ano: int = 2025) -> bytes:
    csv = (
        "CNPJ_Fundo_Classe;Data_Referencia;Versao;Nome_Ativo;Valor;Valor_Justo;"
        "Percentual_Valorizacao_Desvalorizacao\n"
        # versão 1 é substituída pela reapresentação (versão 2) abaixo
        "22.222.222/0001-22;2025-06-01;1;ALFA11;700000;S;-0.08\n"
        "22.222.222/0001-22;2025-06-01;1;23H1700896;300000;S;0.01\n"
        "22.222.222/0001-22;2025-06-01;2;ALFA11;800000;S;-0.08\n"
        "22.222.222/0001-22;2025-06-01;2;23H1700896;200000;S;0.01\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(f"inf_anual_fii_ativo_valor_contabil_{ano}.csv", csv.encode("latin-1"))
    return buffer.getvalue()


def _preparar_fof(con):
    """BETA11 vira FoF: série do universo + composição fof + relação anual."""
    cvm.carregar_zip(con, montar_zip_universo(), "inf_mensal_fii_2026.zip")
    con.execute(
        "INSERT INTO informes_ativo (cnpj, competencia, tijolo, papel, fof, outros, total)"
        " VALUES ('22.222.222/0001-22', '2026-06', 0, 200000, 800000, 0, 1000000)"
    )
    con.commit()
    assert cvm.carregar_zip_anual(con, _zip_anual(), "inf_anual_fii_2025.zip") == 2


def test_carga_anual_fica_com_a_ultima_versao(con):
    _preparar_fof(con)
    linhas = armazenamento.posicoes_anuais_fii(con, "22.222.222/0001-22")
    assert len(linhas) == 2  # a versão 1 foi descartada, sem duplicar
    assert linhas[0]["nome_ativo"] == "ALFA11" and linhas[0]["valor"] == 800000


def test_fof_lista_o_que_tem_dentro_com_selo_cruzado(con):
    _preparar_fof(con)
    raiox = analise.montar_raio_x(con, "BETA11")
    assert len(raiox.posicoes) == 2 and raiox.posicoes_em
    alfa, cri = raiox.posicoes
    assert alfa.ticker == "ALFA11" and alfa.selo is not None  # fundo que analisamos
    assert alfa.pct == 80.0  # 800k sobre 1M declarado
    assert cri.ticker == "" and cri.selo is None  # CRI: fato listado, sem selo

    completo = analise.montar_completo(con, "BETA11")
    pagina = relatorio_html.gerar(
        completo, agora=datetime(2026, 7, 23, 12, 0), publicados={"ALFA11", "BETA11"}
    )
    assert "O que o fundo tem dentro (2)" in pagina
    assert 'href="ALFA11.html"' in pagina  # a página do FoF conversa com a do alvo
    assert "<th>alerta</th>" in pagina
    assert "informe ANUAL" in pagina and "pode estar diferente" in pagina


def test_fundo_de_tijolo_nao_repete_os_imoveis(con):
    _preparar_fof(con)
    # o MESMO fundo reclassificado como tijolo puro: a seção some (os imóveis
    # já aparecem, mais frescos, na seção do informe trimestral)
    con.execute(
        "UPDATE informes_ativo SET tijolo = 1000000, papel = 0, fof = 0"
        " WHERE cnpj = '22.222.222/0001-22'"
    )
    con.commit()
    raiox = analise.montar_raio_x(con, "BETA11")
    assert raiox.posicoes == [] and raiox.posicoes_em == ""


def test_sem_informe_anual_sem_secao(con):
    cvm.carregar_zip(con, montar_zip_universo(), "inf_mensal_fii_2026.zip")
    raiox = analise.montar_raio_x(con, "BETA11")
    assert raiox.posicoes == []
    pagina = relatorio_html.gerar(
        analise.montar_completo(con, "BETA11"), agora=datetime(2026, 7, 23, 12, 0)
    )
    assert "O que o fundo tem dentro" not in pagina
