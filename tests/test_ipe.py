"""Coletor IPE (fatos relevantes/comunicados de empresas) — formato FNET-compatível."""

from datetime import date

from scout.coleta import ipe


def _indice_falso():
    return [
        {"Codigo_CVM": "009512", "Categoria": "Fato Relevante", "Tipo": "",
         "Assunto": "Novo plano estratégico", "Data_Entrega": "2026-06-10",
         "Protocolo_Entrega": "123456", "Link_Download": "https://rad.cvm.gov.br/doc1"},
        {"Codigo_CVM": "009512", "Categoria": "Comunicado ao Mercado", "Tipo": "",
         "Assunto": "Resultado do trimestre", "Data_Entrega": "2026-07-01",
         "Protocolo_Entrega": "123457", "Link_Download": "https://rad.cvm.gov.br/doc2"},
        # categoria fora do escopo: não entra
        {"Codigo_CVM": "009512", "Categoria": "Assembleia", "Tipo": "AGO",
         "Assunto": "Edital", "Data_Entrega": "2026-05-01",
         "Protocolo_Entrega": "123458", "Link_Download": "https://rad.cvm.gov.br/doc3"},
        # outra empresa: não entra
        {"Codigo_CVM": "001023", "Categoria": "Fato Relevante", "Tipo": "",
         "Assunto": "X", "Data_Entrega": "2026-04-01",
         "Protocolo_Entrega": "123459", "Link_Download": "https://rad.cvm.gov.br/doc4"},
    ]


def test_listar_filtra_empresa_categoria_e_ordena(monkeypatch):
    monkeypatch.setitem(ipe._cache_indice, 2026, _indice_falso())
    monkeypatch.setitem(ipe._cache_indice, 2025, [])
    docs = ipe.listar("9512", hoje=date(2026, 7, 22))
    assert [d["categoria"] for d in docs] == ["Comunicado ao Mercado", "Fato Relevante"]
    assert docs[0]["data_entrega"] == "01/07/2026 00:00"  # formato do FNET
    assert docs[1]["tipo"] == "Novo plano estratégico"
    # id numérico estável e dentro de 64 bits (cache SQLite idempotente)
    assert isinstance(docs[0]["id"], int) and docs[0]["id"] < 2**63
    assert docs[0]["id"] != docs[1]["id"]
    # mesma entrada = mesmo id (hash determinístico do protocolo)
    docs2 = ipe.listar("009512", hoje=date(2026, 7, 22))
    assert [d["id"] for d in docs2] == [d["id"] for d in docs]


def test_listar_sem_indice_nao_quebra(monkeypatch):
    monkeypatch.setattr(ipe, "indice_do_ano", lambda ano: (_ for _ in ()).throw(OSError("fora do ar")))
    assert ipe.listar("9512", hoje=date(2026, 7, 22)) == []
