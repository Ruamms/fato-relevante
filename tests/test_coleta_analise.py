import io
import zipfile

import pytest

from fato_relevante import analise, armazenamento
from fato_relevante.coleta import cvm


def _zip_cvm(novo_schema: bool, ano: int = 2026) -> bytes:
    cnpj_col = "CNPJ_Fundo_Classe" if novo_schema else "CNPJ_Fundo"
    nome_col = "Nome_Fundo_Classe" if novo_schema else "Nome_Fundo"
    geral = (
        f"{cnpj_col};Data_Referencia;Versao;{nome_col};Codigo_ISIN;"
        "Segmento_Atuacao;Tipo_Gestao;Quantidade_Cotas_Emitidas\n"
        f"11.111.111/0001-11;{ano}-01-01;1;FUNDO TESTE FII;BRTSTECTF004;Shoppings;Ativa;1000\n"
        f"11.111.111/0001-11;{ano}-02-01;1;FUNDO TESTE FII;BRTSTECTF004;Shoppings;Ativa;1100\n"
    )
    complemento = (
        f"{cnpj_col};Data_Referencia;Versao;Valor_Ativo;Patrimonio_Liquido;"
        "Cotas_Emitidas;Valor_Patrimonial_Cotas;Percentual_Rentabilidade_Patrimonial_Mes;"
        "Percentual_Dividend_Yield_Mes;Percentual_Amortizacao_Cotas_Mes;Total_Numero_Cotistas\n"
        f"11.111.111/0001-11;{ano}-01-01;1;1200000.50;1000000;1000;100.5;0.008;0.009;;500\n"
        f"11.111.111/0001-11;{ano}-02-01;1;1300000;1050000;1100;95.45;0.007;0.011;;520\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(f"inf_mensal_fii_geral_{ano}.csv", geral.encode("latin-1"))
        zf.writestr(f"inf_mensal_fii_complemento_{ano}.csv", complemento.encode("latin-1"))
    return buffer.getvalue()


@pytest.fixture()
def con(tmp_path):
    conexao = armazenamento.conectar(tmp_path)
    yield conexao
    conexao.close()


@pytest.mark.parametrize("novo_schema", [True, False], ids=["pos_rcvm175", "pre_rcvm175"])
def test_carga_normaliza_os_dois_vocabularios(con, novo_schema):
    gerais, complementos = cvm.carregar_zip(con, _zip_cvm(novo_schema), "inf_mensal_fii_2026.zip")
    assert (gerais, complementos) == (2, 2)
    linha = con.execute(
        "SELECT * FROM informes_complemento ORDER BY competencia DESC LIMIT 1"
    ).fetchone()
    assert linha["cnpj"] == "11.111.111/0001-11"
    assert linha["competencia"] == "2026-02"
    assert linha["patrimonio_liquido"] == 1050000
    assert linha["vp_cota"] == 95.45
    assert linha["amortizacao_mes"] is None  # campo vazio no CSV vira NULL
    assert not armazenamento.base_vazia(con)


def test_resolver_fundo_pelo_isin(con):
    cvm.carregar_zip(con, _zip_cvm(True), "inf_mensal_fii_2026.zip")
    fundo = armazenamento.resolver_fundo(con, "tste11")
    assert fundo is not None
    assert fundo.cnpj == "11.111.111/0001-11"
    assert fundo.nome == "FUNDO TESTE FII"
    assert fundo.segmento == "Shoppings"


def test_ticker_desconhecido_retorna_none(con):
    cvm.carregar_zip(con, _zip_cvm(True), "inf_mensal_fii_2026.zip")
    assert armazenamento.resolver_fundo(con, "XPTO11") is None
    assert analise.montar_raio_x(con, "XPTO11") is None


def test_montar_raio_x_com_dados_reais(con):
    cvm.carregar_zip(con, _zip_cvm(True), "inf_mensal_fii_2026.zip")
    raiox = analise.montar_raio_x(con, "tste11")
    assert raiox is not None
    assert raiox.ticker == "TSTE11"
    assert raiox.nome == "FUNDO TESTE FII"
    assert raiox.dados_ate == "02/2026"
    assert raiox.exemplo is False
    assert raiox.red_flags_avaliadas is False
    nomes = [linha.nome for linha in raiox.indicadores]
    assert "Patrimônio líquido" in nomes
    assert "VP/cota" in nomes
    pl = next(linha for linha in raiox.indicadores if linha.nome == "Patrimônio líquido")
    assert pl.atual == "R$ 1,1M"
    # com só 2 meses de série não há variação 12m
    assert pl.doze_meses == "—"
    # a CVM grava DY como fração (0.011 = 1,1%); exibição converte para %
    dy = next(linha for linha in raiox.indicadores if linha.nome == "DY mensal")
    assert dy.atual == "1,10%"
    assert dy.doze_meses == "2,00% 12m"


def test_cli_analisar_com_base_carregada(con, tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from fato_relevante.cli import app

    cvm.carregar_zip(con, _zip_cvm(True), "inf_mensal_fii_2026.zip")
    monkeypatch.setenv("FATO_DATA_DIR", str(tmp_path))
    resultado = CliRunner().invoke(app, ["analisar", "tste11"])
    assert resultado.exit_code == 0
    assert "TSTE11" in resultado.output
    assert "FUNDO TESTE FII" in resultado.output


def test_cli_analisar_base_vazia_orienta_atualizar(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from fato_relevante.cli import app

    monkeypatch.setenv("FATO_DATA_DIR", str(tmp_path / "vazio"))
    resultado = CliRunner().invoke(app, ["analisar", "tste11"])
    assert resultado.exit_code == 1
    assert "fato atualizar" in resultado.output


def test_cli_sem_argumentos_fora_de_terminal_mostra_ajuda():
    from typer.testing import CliRunner

    from fato_relevante.cli import app

    # stdin do CliRunner não é um TTY, então deve cair na ajuda, não no interativo
    resultado = CliRunner().invoke(app, [])
    assert resultado.exit_code == 0
    assert "analisar" in resultado.output


def test_formatacao_ptbr():
    assert analise._decimal(1234.5) == "1.234,50"
    assert analise._percentual(7.649, sinal=True) == "+7,65%"
    assert analise._moeda_compacta(466_244_000) == "R$ 466,2M"
    assert analise._compacto(46_277_022) == "46,3M"
    assert analise._competencia_menos_meses("2026-02", 12) == "2025-02"
    assert analise._competencia_menos_meses("2026-01", 12) == "2025-01"
