"""Coletor FRE — administradores e partes relacionadas (estruturado, sem IA)."""

import io
import zipfile

from scout.coleta import fre


def _zip_fre() -> bytes:
    adm = (
        "CNPJ_Companhia;Data_Referencia;Versao;Nome_Companhia;Orgao_Administracao;Nome;"
        "Cargo_Eletivo_Ocupado;Profissao;Eleito_Controlador;Data_Inicio_Primeiro_Mandato;"
        "Numero_Mandatos_Consecutivos;Percentual_Participacao_Reunioes;Experiencia_Profissional\n"
        # versão 1 (superada) e versão 2 (vigente) da mesma companhia
        "11.222.333/0001-44;2026-12-31;1;TESTECO;Diretoria;FULANO ANTIGO;10 - Diretor;Eng;Não;2020-01-01;2;90;antigo\n"
        "11.222.333/0001-44;2026-12-31;2;TESTECO;Pertence apenas ao Conselho de Administração;"
        "MARIA SILVA;20 - Presidente do Conselho;Economista;Sim;2018-04-01;4;95.5;30 anos de mercado\n"
        "99.888.777/0001-66;2026-12-31;1;OUTRA;Diretoria;JOAO FORA DO ESCOPO;10 - Diretor;Adv;Não;2021-01-01;1;80;x\n"
    )
    partes = (
        "CNPJ_Companhia;Data_Referencia;Versao;Nome_Companhia;Parte_Relacionada;Relacao_Emissor;"
        "Data_Transacao;Objeto_Contrato;Montante_Envolvido;Saldo_Existente;Taxa_Juros\n"
        "11.222.333/0001-44;2026-12-31;2;TESTECO;Controladora XYZ;Acionista controlador;"
        "2026-03-10;Contrato de mútuo;3973062.88;2.270.399;CDI + 1%\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("fre_cia_aberta_administrador_membro_conselho_fiscal_2026.csv", adm.encode("latin-1"))
        zf.writestr("fre_cia_aberta_transacao_parte_relacionada_2026.csv", partes.encode("latin-1"))
    return buffer.getvalue()


def test_carregar_zip_versao_vigente_escopo_e_decimal(con):
    n_adm, n_partes = fre.carregar_zip(con, _zip_fre(), {"11222333000144": "9999"})
    assert (n_adm, n_partes) == (1, 1)  # só a versão vigente, só o escopo
    adm = con.execute("SELECT * FROM administradores").fetchone()
    assert adm["nome"] == "MARIA SILVA" and adm["cod_cvm"] == "9999"
    assert adm["controlador"] == 1 and adm["primeiro_mandato"] == "2018-04-01"
    assert adm["presenca"] == 95.5
    parte = con.execute("SELECT * FROM partes_relacionadas").fetchone()
    assert parte["parte"] == "Controladora XYZ"
    assert parte["montante"] == 3973062.88  # ponto decimal NÃO é milhar (bug 100×)
    assert parte["juros"] == "CDI + 1%"
