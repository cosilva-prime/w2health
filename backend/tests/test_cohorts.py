"""Testes da análise de coortes — "o porquê do porquê" (v1.1, Etapa A).

Cobrem: identidade matemática (reconciliação exata), genericidade por dimensão, e a
regra obrigatória FATO x HIPÓTESE x A_INVESTIGAR (nunca inventar causalidade).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.analytics import cohorts, decomposition

pytestmark = pytest.mark.scenarios

TIPOS_VALIDOS = {cohorts.FATO, cohorts.HIPOTESE, cohorts.A_INVESTIGAR}
CONFIANCAS_VALIDAS = {cohorts.ALTA, cohorts.MEDIA, cohorts.BAIXA}


def _fator(explic: dict, chave: str) -> dict | None:
    todos = explic["principais_fatores"] + explic["fatores_reducao"]
    return next((f for f in todos if f["chave"] == chave), None)


@pytest.mark.parametrize("dimensao", ["especialidade", "procedimento", "grupo_despesa", "contrato"])
def test_reconciliacao_exata_generica(db, dimensao):
    """A soma das coortes reconcilia exatamente com Δdespesa, para qualquer dimensão."""
    comp = date(2026, 9, 1)
    ex = decomposition.explicar(db, comp, "mes_anterior", dimensao, top=20)
    fatores = ex["principais_fatores"] + ex["fatores_reducao"]
    assert fatores, f"sem fatores para {dimensao}"
    verificados = 0
    for fator in fatores[:5]:
        r = cohorts.analisar_causas(db, dimensao, fator["chave"], comp, "mes_anterior")
        assert r["reconciliacao"]["ok"], r["reconciliacao"]
        assert r["reconciliacao"]["soma_coortes"] == pytest.approx(r["delta_total"], abs=0.02)
        verificados += 1
    assert verificados > 0


def test_evidencias_tipos_e_confianca_validos(db):
    comp = date(2026, 9, 1)
    ex = decomposition.explicar(db, comp, "mes_anterior", "especialidade")
    fator = (ex["fatores_reducao"] or ex["principais_fatores"])[0]
    r = cohorts.analisar_causas(db, "especialidade", fator["chave"], comp, "mes_anterior")
    assert r["coortes"]
    for coorte in r["coortes"]:
        assert coorte["evidencias"], "toda coorte deve ter ao menos 1 evidência"
        for ev in coorte["evidencias"]:
            assert ev["tipo_evidencia"] in TIPOS_VALIDOS
            assert ev["nivel_confianca"] in CONFIANCAS_VALIDAS


def test_cohort_buckets_esperados(gabarito, db):
    """Cardápio mínimo de coortes: novos, recorrentes, saída de utilização."""
    g = gabarito["s1_catarata_freq"]
    comp_pico = date(2026, 9, 1)  # mês seguinte ao fim do pico (S1 é jul-ago)
    ex = decomposition.explicar(db, comp_pico, "mes_anterior", "procedimento")
    fator = _fator(ex, g["chave_alvo"])
    assert fator is not None and fator["impacto_financeiro"] < 0
    r = cohorts.analisar_causas(db, "procedimento", g["chave_alvo"], comp_pico, "mes_anterior")
    codigos = {c["codigo"] for c in r["coortes"]}
    assert "permaneceram_sem_evento" in codigos or "saida_carteira" in codigos
    assert any(c["codigo"].startswith("novos") for c in r["coortes"])


def test_hipotese_para_procedimento_pontual_catarata(gabarito, db):
    """Catarata (perfil 'pontual') deve gerar HIPÓTESE ao explicar quem parou de utilizar."""
    g = gabarito["s1_catarata_freq"]
    comp = date(2026, 9, 1)  # mês em que o pico de jul-ago termina
    r = cohorts.analisar_causas(db, "procedimento", g["chave_alvo"], comp, "mes_anterior")
    sem_evento = next((c for c in r["coortes"] if c["codigo"] == "permaneceram_sem_evento"), None)
    assert sem_evento is not None, "esperava beneficiários sem novo evento após o pico de catarata"
    tipos = {e["tipo_evidencia"] for e in sem_evento["evidencias"]}
    assert cohorts.HIPOTESE in tipos, "catarata é pontual — deveria ser elegível a hipótese"


def test_a_investigar_para_procedimento_recorrente_fisioterapia(gabarito, db):
    """Fisioterapia (perfil 'recorrente') NÃO deve inventar hipótese de conclusão de
    tratamento — cai em A_INVESTIGAR quando beneficiários param de utilizar."""
    g = gabarito["s8_melhora_fisioterapia"]
    comp = date(2026, 10, 1)
    r = cohorts.analisar_causas(db, "procedimento", g["chave_alvo"], comp, "mes_anterior")
    sem_evento = next((c for c in r["coortes"] if c["codigo"] == "permaneceram_sem_evento"), None)
    assert sem_evento is not None
    tipos = {e["tipo_evidencia"] for e in sem_evento["evidencias"]}
    assert cohorts.HIPOTESE not in tipos
    assert cohorts.A_INVESTIGAR in tipos


def test_saida_da_carteira_e_fato(db):
    """Quando há beneficiários que saíram da carteira, a evidência é sempre FATO/ALTA."""
    comp = date(2026, 9, 1)
    ex = decomposition.explicar(db, comp, "mes_anterior", "especialidade")
    for fator in (ex["fatores_reducao"] + ex["principais_fatores"])[:6]:
        r = cohorts.analisar_causas(db, "especialidade", fator["chave"], comp, "mes_anterior")
        saida = next((c for c in r["coortes"] if c["codigo"] == "saida_carteira"), None)
        if saida:
            assert saida["evidencias"][0]["tipo_evidencia"] == cohorts.FATO
            assert saida["evidencias"][0]["nivel_confianca"] == cohorts.ALTA
            return
    pytest.skip("nenhum fator com saída de carteira nesta amostra")
