"""Testes de integração: os cenários sintéticos plantados devem ser detectados pelo motor.

Cada teste compara a saída do motor analítico com o `cenarios_gabarito` gravado pelo
gerador. Se um cenário conhecido não for detectado, o MVP não está pronto.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.analytics import beneficiaries, decomposition, providers, seasonality, sinistralidade
from app.analytics.periodo import parse_competencia
from app.repositories import analytics_repo as repo

_MAIOR_EFEITO_DESPESA = ("efeito_bruta_pp", "efeito_glosa_pp", "efeito_coparticipacao_pp")

pytestmark = pytest.mark.scenarios


def _competencia_alvo(g: dict) -> date:
    return parse_competencia(g["competencia_alvo"])


def _fator(explic: dict, chave: str) -> dict | None:
    todos = explic["principais_fatores"] + explic["fatores_reducao"]
    return next((f for f in todos if f["chave"] == chave), None)


# ------------------------------------------------------------------ S1 — CATARATA
def test_cataract_frequency_scenario_detected(db, gabarito):
    g = gabarito["s1_catarata_freq"]
    comp = _competencia_alvo(g)
    ex = decomposition.explicar(db, comp, "mes_anterior", "procedimento")

    fator = _fator(ex, g["chave_alvo"])
    assert fator is not None, "catarata não apareceu na decomposição por procedimento"
    # está entre os maiores fatores de alta
    top_chaves = [f["chave"] for f in ex["principais_fatores"][:3]]
    assert g["chave_alvo"] in top_chaves
    # efeito predominantemente de FREQUÊNCIA
    assert fator["efeito_principal"] == "frequencia"
    b = fator["bridge"]
    assert b["variacao_frequencia_pct"] >= 40
    assert abs(b["variacao_custo_medio_pct"]) <= 15


def test_cataract_concentrated_in_three_providers(db, gabarito):
    g = gabarito["s1_catarata_freq"]
    comp = _competencia_alvo(g)
    dr = decomposition.drill(db, comp, "procedimento", g["chave_alvo"], "mes_anterior")
    contribs = dr["onde_investigar"]["prestadores_maior_contribuicao_variacao"]
    positivos = [c["delta"] for c in contribs if c["delta"] > 0]
    total = sum(positivos)
    top3 = sum(sorted(positivos, reverse=True)[:3])
    assert total > 0
    assert top3 / total >= 0.55, "aumento de catarata não concentrado em ~3 prestadores"


# ---------------------------------------------------------------- S2 — INTERNAÇÕES
def test_internacoes_scenario_detected(db, gabarito):
    g = gabarito["s2_internacoes"]
    comp = _competencia_alvo(g)
    ex = decomposition.explicar(db, comp, "mes_anterior", "tipo_atendimento")
    fator = _fator(ex, "internacao")
    assert fator is not None
    assert fator["impacto_financeiro"] > 0
    assert fator["bridge"]["variacao_frequencia_pct"] >= 18


# ------------------------------------------------------ S3 — PRESTADOR FORA DO PADRÃO
def test_anomalous_provider_scenario_detected(db, gabarito):
    g = gabarito["s3_prestador_anomalo"]
    comp = _competencia_alvo(g)
    id_alvo = int(g["params"]["id_prestador"])
    achados = {a["id_prestador"] for a in providers.anomalia_prestadores(db, comp)}
    assert id_alvo in achados, "prestador fora do padrão não sinalizado"
    det = providers.detalhe(db, id_alvo, comp)
    assert abs(det["comparacao_pares"]["zscores"]["custo_medio"]) >= 2.0


# --------------------------------------------------------------- S4 — ALTO CUSTO
def test_high_cost_concentration_scenario_detected(db, gabarito):
    g = gabarito["s4_alto_custo"]
    comp = _competencia_alvo(g)
    conc = beneficiaries.concentracao(db, comp)
    c = conc["concentracao"]
    # os 1% maiores concentram parcela relevante da despesa
    assert c["top_k_share"].get(20, 0) >= 0.30 or c["gini"] >= 0.6


# --------------------------------------------------------- S5 — SAZONALIDADE (não anômala)
def test_seasonality_not_flagged_as_anomaly(db, gabarito):
    g = gabarito["s5_sazonalidade_resp"]
    comp = _competencia_alvo(g)
    serie = [(r["competencia"], float(r["eventos"]))
             for r in repo.dimensao_serie(db, "especialidade", g["chave_alvo"])]
    cls = seasonality.classificar(serie, comp)
    # inverno se repete nos dois anos -> deve ser 'sazonal' ou 'normal', nunca 'anomalo'
    assert cls["classificacao"] != "anomalo"


# ------------------------------------------------------ S6 — PRONTO-SOCORRO RECORRENTE
def test_recurrent_er_use_scenario_detected(db, gabarito):
    from sqlalchemy import text

    comp = _competencia_alvo(gabarito["s6_ps_recorrente"])
    n = db.execute(
        text(
            """
            SELECT COUNT(*) FROM (
              SELECT id_beneficiario
              FROM eventos_assistenciais
              WHERE tipo_atendimento = 'pronto_socorro' AND competencia = :c
              GROUP BY id_beneficiario HAVING COUNT(*) >= 3
            ) z
            """
        ),
        {"c": comp},
    ).scalar_one()
    assert n >= 30, "grupo de uso recorrente de pronto-socorro não identificável"


# --------------------------------------------------------------- S7 — CUSTO MÉDIO
def test_average_cost_scenario_detected(db, gabarito):
    g = gabarito["s7_custo_medio"]
    comp = _competencia_alvo(g)
    dr = decomposition.drill(db, comp, "procedimento", g["chave_alvo"], "mes_anterior")
    fator = dr["fator"]
    assert fator["efeito_principal"] == "custo_medio"
    b = fator["bridge"]
    assert b["variacao_custo_medio_pct"] >= 15
    assert abs(b["variacao_frequencia_pct"] or 0) <= 12
    # e aparece na explicação geral por procedimento entre os fatores relevantes
    ex = decomposition.explicar(db, comp, "mes_anterior", "procedimento")
    assert _fator(ex, g["chave_alvo"]) is not None


# --------------------------------------------------------- S8 — MELHORA / REDUÇÃO
def test_improvement_scenario_detected(db, gabarito):
    g = gabarito["s8_melhora_fisioterapia"]
    comp = _competencia_alvo(g)
    dr = decomposition.drill(db, comp, "procedimento", g["chave_alvo"], "mes_anterior")
    fator = dr["fator"]
    assert fator["impacto_financeiro"] < 0, "fisioterapia não reduziu"
    assert fator["efeito_principal"] == "frequencia"
    assert fator["bridge"]["variacao_frequencia_pct"] <= -25
    # e aparece entre os fatores de REDUÇÃO da explicação por especialidade
    ex = decomposition.explicar(db, comp, "mes_anterior", "especialidade")
    reducoes = [f["categoria"] for f in ex["fatores_reducao"]]
    assert any("Fisio" in c for c in reducoes)


# --------------------------------------------------- S10 — GLOSA AUMENTA (Cenário A)
def test_glosa_increase_scenario_detected(db, gabarito):
    g = gabarito["s10_glosa_aumenta"]
    comp = _competencia_alvo(g)
    c = sinistralidade.composicao(db, comp, "mes_anterior")
    dec = c["decomposicao"]
    assert dec["variacao_pp"] < 0, "sinistralidade líquida deveria melhorar (glosa sobe)"
    dominante = max(_MAIOR_EFEITO_DESPESA, key=lambda k: abs(dec[k]))
    assert dominante == "efeito_glosa_pp"
    # reconciliação exata
    soma = sum(dec[k] for k in (*_MAIOR_EFEITO_DESPESA, "efeito_receita_pp"))
    assert soma == pytest.approx(dec["variacao_pp"], abs=0.01)


# ----------------------------------------- S11 — COPARTICIPAÇÃO AUMENTA (Cenário B)
def test_coparticipacao_increase_scenario_detected(db, gabarito):
    g = gabarito["s11_coparticipacao_aumenta"]
    comp = _competencia_alvo(g)
    c = sinistralidade.composicao(db, comp, "mes_anterior")
    dec = c["decomposicao"]
    dominante = max(_MAIOR_EFEITO_DESPESA, key=lambda k: abs(dec[k]))
    assert dominante == "efeito_coparticipacao_pp"
    assert c["atual"]["coparticipacao"] > c["comparacao_valores"]["coparticipacao"]


# ------------------------------------------------- S12 — EFEITO COMBINADO (Cenário C)
def test_combined_glosa_coparticipacao_scenario_detected(db, gabarito):
    g = gabarito["s12_glosa_copart_combinado"]
    comp = _competencia_alvo(g)
    c = sinistralidade.composicao(db, comp, "mes_anterior")
    dec = c["decomposicao"]
    financeiro = abs(dec["efeito_glosa_pp"]) + abs(dec["efeito_coparticipacao_pp"])
    assert financeiro > abs(dec["efeito_bruta_pp"]), (
        "glosa+coparticipação combinadas deveriam superar o efeito da despesa bruta"
    )


# --------------------------------------- S13 — RECEITA CAI MAIS (Cenário D)
def test_revenue_dominant_worsening_scenario_detected(db, gabarito):
    g = gabarito["s13_receita_cai_mais"]
    comp = _competencia_alvo(g)
    c = sinistralidade.composicao(db, comp, "mes_anterior")
    dec = c["decomposicao"]
    assert dec["variacao_pp"] > 0, "sinistralidade líquida deveria piorar"
    todos = {k: abs(dec[k]) for k in (*_MAIOR_EFEITO_DESPESA, "efeito_receita_pp")}
    assert max(todos, key=lambda k: todos[k]) == "efeito_receita_pp"


# =====================================================================================
# v1.2 — S14..S19: contrato como unidade de análise
# =====================================================================================
def _contrato_alvo(g: dict) -> int:
    return int(g["params"]["id_contrato"])


def test_s14_contract_concentration_detected(db, gabarito):
    from app.analytics import contratos, decomposition

    g = gabarito["s14_contrato_concentracao"]
    comp, cid = _competencia_alvo(g), int(g["chave_alvo"])
    cc = repo.contrato_competencia(db, cid, comp)
    assert cc is not None and cc["despesa_liquida"] > 0
    # concentração alta no contrato E na variação
    assert cc["top5_share"] >= 0.45 or cc["gini"] >= 0.6
    cv = decomposition.concentracao_variacao_beneficiarios(db, comp, "mes_anterior", cid)
    assert cv["n_para_credito_50pct"] <= 5


def test_s15_contract_homogeneous_increase_detected(db, gabarito):
    from app.analytics import decomposition

    g = gabarito["s15_contrato_homogeneo"]
    comp, cid = _competencia_alvo(g), int(g["chave_alvo"])
    cv = decomposition.concentracao_variacao_beneficiarios(db, comp, "mes_anterior", cid)
    g19 = gabarito["s19_contrato_concentracao_extrema"]
    cv19 = decomposition.concentracao_variacao_beneficiarios(
        db, _competencia_alvo(g19), "mes_anterior", int(g19["chave_alvo"])
    )
    # o aumento do contrato "homogêneo" é bem menos concentrado que o do "extremo"
    assert cv["n_beneficiarios_com_aumento"] >= 30
    assert cv["top5_share_do_aumento"] < cv19["top5_share_do_aumento"]
    assert cv["n_para_credito_50pct"] >= 6


def test_s16_new_high_cost_case_detected(db, gabarito):
    from app.analytics import beneficiaries

    g = gabarito["s16_contrato_novo_alto_custo"]
    comp, cid = _competencia_alvo(g), _contrato_alvo(g)
    res = beneficiaries.novos_casos_alto_custo(db, comp, "mes_anterior", contrato_id=cid)
    assert res["total"] >= 1
    novo = res["itens"][0]
    assert novo["despesa_liquida"] >= res["limiar"]
    assert novo["maior_despesa_anterior"] < res["limiar"] * 0.25


def test_s17_recurring_group_detected(db, gabarito):
    g = gabarito["s17_contrato_recorrente"]
    comp, cid = _competencia_alvo(g), int(g["chave_alvo"])
    from app.analytics.beneficiaries import JANELA_RECORRENCIA

    recor = {r["id"]: r["meses_com_evento"]
             for r in repo.recorrencia_beneficiarios_mes(db, comp, JANELA_RECORRENCIA)}
    ids_ctr = {b["id"] for b in repo.beneficiarios_liquida_contrato_mes(db, comp, cid)}
    frequentes = [i for i in ids_ctr if recor.get(i, 0) >= 4]
    assert len(frequentes) >= 10, "grupo recorrente do contrato não identificável"


def test_s18_one_off_event_hypothesis(db, gabarito):
    from app.analytics import cohorts

    g = gabarito["s18_contrato_evento_pontual"]
    # o cenário injeta em nov/2026 e NÃO repete em dez -> coorte de dez classifica HIPÓTESE
    comp = date(2026, 12, 1)
    res = cohorts.analisar_causas(db, "procedimento", g["chave_alvo"], comp, "mes_anterior")
    permanece = next(
        (c for c in res["coortes"] if c["codigo"] == "permaneceram_sem_evento"), None
    )
    assert permanece is not None
    tipos = {e["tipo_evidencia"] for e in permanece["evidencias"]}
    assert "HIPOTESE" in tipos, "colecistectomia (pontual) deveria gerar HIPÓTESE de episódio concluído"


def test_s19_extreme_concentration_detected(db, gabarito):
    g = gabarito["s19_contrato_concentracao_extrema"]
    comp, cid = _competencia_alvo(g), int(g["chave_alvo"])
    cc = repo.contrato_competencia(db, cid, comp)
    assert cc is not None
    assert cc["gini"] >= 0.75 or cc["top5_share"] >= 0.7


# ------------------------------------------------------ S9 — RECEITA ESTAGNADA
def test_revenue_behavior_scenario_detected(db, gabarito):
    serie = sinistralidade.serie(db)
    por_comp = {r["competencia"]: r for r in serie}
    dez25 = por_comp["2025-12-01"]["receita_media_beneficiario"]
    dez26 = por_comp["2026-12-01"]["receita_media_beneficiario"]
    crescimento = dez26 / dez25 - 1.0
    # 2026 sem reajuste anual -> receita per capita cresce bem abaixo do reajuste (~11%)
    assert crescimento < 0.06, f"receita per capita cresceu {crescimento:.1%} (esperava < 6%)"
