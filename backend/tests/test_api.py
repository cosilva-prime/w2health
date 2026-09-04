"""Testes dos endpoints críticos da API (contra o banco de testes seedado)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import create_app

pytestmark = pytest.mark.scenarios


@pytest.fixture
def api(seeded_sessionmaker) -> TestClient:
    app = create_app()

    def _get_db():
        s: Session = seeded_sessionmaker()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    return TestClient(app)


def test_meta_competencias(api):
    r = api.get("/api/meta/competencias")
    assert r.status_code == 200
    body = r.json()
    assert body["primeira"] == "2025-01-01"
    assert body["ultima"] == "2026-12-01"
    assert len(body["itens"]) == 24


def test_executive_overview(api):
    r = api.get("/api/executive/overview?competencia=2026-06")
    assert r.status_code == 200
    b = r.json()
    assert "kpis" in b and "serie" in b
    assert b["kpis"]["sinistralidade"] > 0
    assert len(b["serie"]) == 24
    assert isinstance(b["principais_fatores_atencao"], list)


def test_sinistralidade_indicador_e_decomposicao(api):
    r = api.get("/api/analytics/sinistralidade?competencia=2026-06&comparacao=mes_anterior")
    assert r.status_code == 200
    b = r.json()
    assert "variacao_pp" in b
    dec = b["decomposicao_receita_despesa"]
    assert abs(dec["efeito_despesa_pp"] + dec["efeito_receita_pp"] - dec["variacao_pp"]) < 0.01


def test_explain_procedimento_catarata(api, gabarito):
    g = gabarito["s1_catarata_freq"]
    r = api.get(
        f"/api/analytics/sinistralidade/explain?competencia={g['competencia_alvo']}"
        f"&comparacao=mes_anterior&dimensao=procedimento"
    )
    assert r.status_code == 200
    fatores = r.json()["principais_fatores"]
    cat = next((f for f in fatores if f["chave"] == g["chave_alvo"]), None)
    assert cat is not None
    assert cat["efeito_principal"] == "frequencia"


def test_explain_drill_onde_investigar(api, gabarito):
    g = gabarito["s1_catarata_freq"]
    r = api.get(
        f"/api/analytics/sinistralidade/explain/procedimento/{g['chave_alvo']}"
        f"?competencia={g['competencia_alvo']}"
    )
    assert r.status_code == 200
    b = r.json()
    assert b["fator"]["efeito_principal"] == "frequencia"
    assert b["onde_investigar"]["prestadores_maior_contribuicao_variacao"]


def test_prestadores_ranking_e_detalhe(api):
    r = api.get("/api/analytics/prestadores/ranking-variacao?competencia=2026-09&direcao=alta")
    assert r.status_code == 200
    itens = r.json()["itens"]
    assert itens and all(x["impacto"] > 0 for x in itens)
    pid = itens[0]["id_prestador"]
    d = api.get(f"/api/analytics/prestadores/{pid}?competencia=2026-09")
    assert d.status_code == 200
    assert "bridge" in d.json() and "comparacao_pares" in d.json()


def test_beneficiario_por_codigo_e_timeline(api):
    r = api.get("/api/analytics/beneficiarios/BEN-000001")
    assert r.status_code == 200
    assert r.json()["beneficiario"]["codigo"] == "BEN-000001"
    t = api.get("/api/analytics/beneficiarios/BEN-000001/timeline")
    assert t.status_code == 200
    assert "timeline" in t.json()


def test_insights_derivados(api):
    r = api.get("/api/analytics/insights?competencia=2026-09")
    assert r.status_code == 200
    itens = r.json()["itens"]
    assert itens
    assert all({"titulo", "score", "deep_link", "metodologia", "metricas"} <= set(i) for i in itens)
    # o primeiro insight é sempre a variação da sinistralidade
    assert any(i["tipo"] == "variacao_sinistralidade" for i in itens)


def test_concentracao(api):
    r = api.get("/api/analytics/concentracao?competencia=2026-06")
    assert r.status_code == 200
    c = r.json()["concentracao"]
    assert 0.0 <= c["gini"] <= 1.0


def test_composicao_financeira(api):
    r = api.get(
        "/api/analytics/sinistralidade/composicao"
        "?competencia=2026-02&comparacao=mes_anterior"
    )
    assert r.status_code == 200
    b = r.json()
    a = b["atual"]
    assert a["despesa_liquida"] == pytest.approx(
        a["despesa_bruta"] - a["glosas"] - a["coparticipacao"], abs=0.02
    )
    dec = b["decomposicao"]
    soma = (
        dec["efeito_bruta_pp"] + dec["efeito_glosa_pp"]
        + dec["efeito_coparticipacao_pp"] + dec["efeito_receita_pp"]
    )
    assert soma == pytest.approx(dec["variacao_pp"], abs=0.02)


def test_explain_causas_endpoint(api):
    r = api.get("/api/analytics/sinistralidade/explain/especialidade/1/causas?competencia=2026-09")
    assert r.status_code == 200
    b = r.json()
    assert "reconciliacao" in b
    assert b["reconciliacao"]["ok"] is True


def test_competencia_invalida_404(api):
    assert api.get("/api/analytics/sinistralidade?competencia=2030-01").status_code == 404
