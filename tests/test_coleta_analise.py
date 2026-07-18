import pytest

from scout import analise, armazenamento
from scout.coleta import cvm


@pytest.mark.parametrize("novo_schema", [True, False], ids=["pos_rcvm175", "pre_rcvm175"])
def test_carga_normaliza_os_dois_vocabularios(con, zip_cvm, novo_schema):
    gerais, complementos = cvm.carregar_zip(con, zip_cvm(novo_schema), "inf_mensal_fii_2026.zip")
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


def test_resolver_fundo_pelo_isin(con, zip_cvm):
    cvm.carregar_zip(con, zip_cvm(True), "inf_mensal_fii_2026.zip")
    fundo = armazenamento.resolver_fundo(con, "tste11")
    assert fundo is not None
    assert fundo.cnpj == "11.111.111/0001-11"
    assert fundo.nome == "FUNDO TESTE FII"
    assert fundo.segmento == "Shoppings"


def test_ticker_desconhecido_retorna_none(con, zip_cvm):
    cvm.carregar_zip(con, zip_cvm(True), "inf_mensal_fii_2026.zip")
    assert armazenamento.resolver_fundo(con, "XPTO11") is None
    assert analise.montar_raio_x(con, "XPTO11") is None


def test_montar_raio_x_com_dados_reais(con, zip_cvm):
    cvm.carregar_zip(con, zip_cvm(True), "inf_mensal_fii_2026.zip")
    raiox = analise.montar_raio_x(con, "tste11")
    assert raiox is not None
    assert raiox.ticker == "TSTE11"
    assert raiox.nome == "FUNDO TESTE FII"
    assert raiox.dados_ate == "02/2026"
    assert raiox.exemplo is False
    assert raiox.red_flags_avaliadas is True
    # com 2 meses de série, a maioria das regras fica como "não avaliada"
    assert any("não avaliadas" in nota for nota in raiox.notas)
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
    assert dy.doze_meses == "2,00% acumulado"


def test_cli_analisar_com_base_carregada(con, zip_cvm, tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from scout.cli import app
    from scout.coleta import cotacoes, indices

    cvm.carregar_zip(con, zip_cvm(True), "inf_mensal_fii_2026.zip")
    monkeypatch.setenv("SCOUT_DATA_DIR", str(tmp_path))
    # a CLI sincroniza cotações e índices antes de analisar; teste não vai à rede
    monkeypatch.setattr(cotacoes, "garantir_atualizada", lambda con, ticker: None)
    monkeypatch.setattr(indices, "garantir_atualizados", lambda con: None)
    resultado = CliRunner().invoke(app, ["analisar", "tste11"])
    assert resultado.exit_code == 0
    assert "TSTE11" in resultado.output
    assert "FUNDO TESTE FII" in resultado.output


def test_cli_analisar_base_vazia_orienta_atualizar(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from scout.cli import app

    monkeypatch.setenv("SCOUT_DATA_DIR", str(tmp_path / "vazio"))
    resultado = CliRunner().invoke(app, ["analisar", "tste11"])
    assert resultado.exit_code == 1
    assert "scout atualizar" in resultado.output


def test_cli_sem_argumentos_fora_de_terminal_mostra_ajuda():
    from typer.testing import CliRunner

    from scout.cli import app

    # stdin do CliRunner não é um TTY, então deve cair na ajuda, não no interativo
    resultado = CliRunner().invoke(app, [])
    assert resultado.exit_code == 0
    assert "analisar" in resultado.output


def test_baixar_url_com_retry(monkeypatch):
    import urllib.error
    import urllib.request

    tentativas = []
    monkeypatch.setattr(cvm.time, "sleep", lambda segundos: tentativas.append(f"sleep {segundos}"))

    def _urlopen_instavel(url, timeout=None):
        tentativas.append("tentou")
        if tentativas.count("tentou") < 3:
            raise urllib.error.URLError(OSError(101, "Network is unreachable"))
        import io

        class _Resposta(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return _Resposta(b"conteudo")

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_instavel)
    assert cvm._baixar_url("https://exemplo/x.zip") == b"conteudo"
    # 2 falhas com espera progressiva, sucesso na 3ª
    assert tentativas == ["tentou", "sleep 5", "tentou", "sleep 20", "tentou"]


def test_formatacao_ptbr():
    from scout import formato, series

    assert formato.decimal(1234.5) == "1.234,50"
    assert formato.percentual(7.649, sinal=True) == "+7,65%"
    assert formato.moeda_compacta(466_244_000) == "R$ 466,2M"
    assert formato.compacto(46_277_022) == "46,3M"
    assert series.competencia_menos_meses("2026-02", 12) == "2025-02"
    assert series.competencia_menos_meses("2026-01", 12) == "2025-01"
