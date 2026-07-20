"""Taxa de administração efetiva (série do informe mensal da CVM)."""

import pytest

from scout import series


def _serie(*fracoes_mensais):
    return [{"taxa_adm_mes": v} for v in fracoes_mensais]


def test_anualiza_a_media_mensal():
    # 12 meses de 0,08% do PL/mês -> ~0,96% a.a.
    assert series.taxa_adm_efetiva(_serie(*([0.0008] * 12))) == pytest.approx(0.96, abs=0.01)
    # HGLG-like: 0,046%/mês -> ~0,55% a.a.
    assert series.taxa_adm_efetiva(_serie(*([0.000456] * 12))) == pytest.approx(0.547, abs=0.01)


def test_descarta_lixo_e_none():
    # None e valores absurdos (> 3%/mês) fora; média dos válidos × 12
    s = _serie(0.0008, 0.0008, 0.0008, None, 5.0)
    assert series.taxa_adm_efetiva(s) == pytest.approx(0.96, abs=0.01)


def test_poucos_meses_nao_anualiza_ruido():
    assert series.taxa_adm_efetiva(_serie(0.0008, None)) is None  # < 3 válidos
    assert series.taxa_adm_efetiva(_serie()) is None


def test_usa_so_a_janela_recente():
    # 20 meses, mas só os últimos 12 contam; aqui todos iguais -> mesmo valor
    assert series.taxa_adm_efetiva(_serie(*([0.0008] * 20))) == pytest.approx(0.96, abs=0.01)
