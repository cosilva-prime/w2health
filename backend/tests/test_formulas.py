"""Testes unitários das primitivas do motor analítico (Etapa 5 / G1)."""

import math

import pytest

from app.analytics import formulas as f


# ------------------------------------------------------------------- sinistralidade
def test_sinistralidade_basica():
    assert f.sinistralidade(750, 1000) == pytest.approx(75.0)


def test_sinistralidade_receita_zero():
    assert f.sinistralidade(500, 0) == 0.0


def test_variacao_pp():
    assert f.variacao_pp(82.4, 74.6) == pytest.approx(7.8)


def test_variacao_pct():
    assert f.variacao_pct(165, 120) == pytest.approx(37.5)
    assert f.variacao_pct(100, 0) is None


def test_acumulado_12m():
    d = [100.0] * 12
    r = [125.0] * 12
    assert f.acumulado_12m(d, r) == pytest.approx(80.0)


# ------------------------------------------- decomposição numerador x denominador
def test_decomposicao_sinistralidade_soma_exata():
    dec = f.decomposicao_sinistralidade(746.0, 1000.0, 824.0, 1000.0)
    # só a despesa mudou -> todo o efeito é de despesa
    assert dec.efeito_receita_pp == pytest.approx(0.0)
    assert dec.efeito_despesa_pp == pytest.approx(dec.variacao_pp)


def test_decomposicao_identidade_receita_muda():
    d0, r0, d1, r1 = 700.0, 1000.0, 780.0, 1040.0
    dec = f.decomposicao_sinistralidade(d0, r0, d1, r1)
    assert dec.efeito_despesa_pp + dec.efeito_receita_pp == pytest.approx(dec.variacao_pp, abs=1e-9)


def test_decomposicao_receita_cai_eleva_sinistralidade():
    # despesa constante, receita cai -> efeito_receita positivo (piora)
    dec = f.decomposicao_sinistralidade(700.0, 1000.0, 700.0, 900.0)
    assert dec.efeito_despesa_pp == pytest.approx(0.0)
    assert dec.efeito_receita_pp > 0


# ------------------------------------------------------------ contribuição
def test_contribuicoes_participacao_soma_100():
    ant = {"a": ("A", 100.0), "b": ("B", 200.0), "c": ("C", 50.0)}
    atu = {"a": ("A", 130.0), "b": ("B", 210.0), "c": ("C", 60.0)}
    cs = f.contribuicoes(ant, atu)
    assert sum(c.participacao_pct for c in cs) == pytest.approx(100.0, abs=1e-6)
    # ordenado por |delta| desc -> 'a' (delta 30) primeiro
    assert cs[0].chave == "a"


def test_contribuicoes_categoria_nova():
    ant = {"a": ("A", 100.0)}
    atu = {"a": ("A", 100.0), "novo": ("Novo", 40.0)}
    cs = f.contribuicoes(ant, atu)
    novo = next(c for c in cs if c.chave == "novo")
    assert novo.delta == pytest.approx(40.0)
    assert novo.participacao_pct == pytest.approx(100.0)


# ------------------------------------------------- bridge frequência x custo médio
def test_bennet_soma_exata():
    b = f.bennet_bridge(120, 4100, 165, 4250)
    assert b.efeito_frequencia + b.efeito_custo_medio == pytest.approx(b.delta_total, abs=1e-6)
    assert b.interacao == 0.0


def test_bennet_efeito_frequencia_dominante():
    # +37,5% de frequência, +3,7% de custo -> efeito principal = frequência
    b = f.bennet_bridge(120, 4100, 165, 4250)
    assert b.efeito_principal == "frequencia"
    assert b.efeito_frequencia > b.efeito_custo_medio


def test_bennet_efeito_custo_dominante():
    b = f.bennet_bridge(100, 1000, 102, 1400)  # freq quase estável, preço +40%
    assert b.efeito_principal == "custo_medio"


def test_bennet_misto():
    b = f.bennet_bridge(100, 1000, 130, 1300)  # +30% freq e +30% preço
    assert b.efeito_principal == "misto"


def test_laspeyres_soma_com_interacao():
    b = f.laspeyres_bridge(120, 4100, 165, 4250)
    assert (
        b.efeito_frequencia + b.efeito_custo_medio + b.interacao
        == pytest.approx(b.delta_total, abs=1e-6)
    )


def test_bennet_vs_laspeyres_mesmo_delta():
    be = f.bennet_bridge(120, 4100, 165, 4250)
    la = f.laspeyres_bridge(120, 4100, 165, 4250)
    assert be.delta_total == pytest.approx(la.delta_total)


# ------------------------------------------------------------------ concentração
def test_gini_igualdade():
    assert f.gini([10, 10, 10, 10]) == pytest.approx(0.0, abs=1e-9)


def test_gini_concentracao_alta():
    g = f.gini([0, 0, 0, 0, 100])
    assert g > 0.7


def test_concentracao_top_k():
    valores = [100, 50, 30, 10, 5, 3, 2]  # total 200
    c = f.concentracao(valores, ks=(1, 3))
    assert c.top_k_share[1] == pytest.approx(0.5)
    assert c.top_k_share[3] == pytest.approx(0.9)
    assert c.total == pytest.approx(200)


def test_concentracao_pareto():
    valores = [80, 10, 5, 3, 2]  # 80 já é 80% do total (100)
    c = f.concentracao(valores)
    assert c.pareto_k == 1


def test_classificar_efeito_limiar():
    assert f.classificar_efeito(90, 10) == "frequencia"
    assert f.classificar_efeito(10, 90) == "custo_medio"
    assert f.classificar_efeito(50, 50) == "misto"
    assert f.classificar_efeito(0, 0) == "misto"


def test_severidade():
    assert f.severidade_por_impacto(7.8) == "alta"
    assert f.severidade_por_impacto(3.0) == "media"
    assert f.severidade_por_impacto(-3.0) == "positiva"
    assert f.severidade_por_impacto(0.5) == "baixa"


# ------------------------------------------- decomposição financeira (bruta/glosa/copart)
def test_decomposicao_financeira_soma_exata():
    dec = f.decomposicao_financeira(
        10_000_000, 500_000, 700_000, 11_000_000,   # anterior: bruta, glosa, copart, receita
        9_500_000, 650_000, 750_000, 11_200_000,    # atual
    )
    soma = (
        dec.efeito_bruta_pp + dec.efeito_glosa_pp
        + dec.efeito_coparticipacao_pp + dec.efeito_receita_pp
    )
    assert soma == pytest.approx(dec.variacao_pp, abs=1e-9)


def test_decomposicao_financeira_exemplo_enunciado():
    # Receita 11mi, despesa bruta 10mi, glosas 500k, copart 700k -> líquida 8,8mi
    # Sinistralidade bruta 90,9% / líquida 80,0% (conforme exemplo do consultor)
    dec = f.decomposicao_financeira(
        10_000_000, 500_000, 700_000, 11_000_000,
        10_000_000, 500_000, 700_000, 11_000_000,
    )
    assert dec.variacao_pp == pytest.approx(0.0)
    assert f.sinistralidade(10_000_000, 11_000_000) == pytest.approx(90.909, abs=0.01)
    liquida = 10_000_000 - 500_000 - 700_000
    assert f.sinistralidade(liquida, 11_000_000) == pytest.approx(80.0, abs=0.01)


def test_decomposicao_financeira_glosa_domina():
    # bruta estável, só a glosa sobe -> efeito_glosa deve ser o maior em módulo
    dec = f.decomposicao_financeira(
        10_000_000, 300_000, 400_000, 11_000_000,
        10_050_000, 900_000, 420_000, 11_050_000,
    )
    efeitos_despesa = {"bruta": abs(dec.efeito_bruta_pp), "glosa": abs(dec.efeito_glosa_pp),
                        "copart": abs(dec.efeito_coparticipacao_pp)}
    assert max(efeitos_despesa, key=lambda k: efeitos_despesa[k]) == "glosa"


def test_decomposicao_financeira_receita_domina_quando_pior():
    # despesa líquida cai, mas receita cai muito mais -> sinistralidade piora e o efeito
    # receita deve ser o maior em módulo entre os 4
    dec = f.decomposicao_financeira(
        10_000_000, 500_000, 700_000, 11_000_000,
        9_500_000, 500_000, 700_000, 9_000_000,
    )
    assert dec.variacao_pp > 0  # piorou
    todos = [abs(dec.efeito_bruta_pp), abs(dec.efeito_glosa_pp),
             abs(dec.efeito_coparticipacao_pp), abs(dec.efeito_receita_pp)]
    assert abs(dec.efeito_receita_pp) == max(todos)


def test_bridge_dispatch():
    assert f.bridge(1, 2, 3, 4, "bennet").metodo == "bennet"
    assert f.bridge(1, 2, 3, 4, "laspeyres").metodo == "laspeyres"
    assert not math.isnan(f.bridge(0, 0, 0, 0).delta_total)
