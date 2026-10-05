"""Testes dos endpoints críticos da API (contra o banco de testes seedado)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import create_app

pytestmark = pytest.mark.scenarios


@pytest.fixture
def api(seeded_sessionmaker, auth_headers) -> TestClient:
    app = create_app()

    def _get_db():
        s: Session = seeded_sessionmaker()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    return TestClient(app, headers=auth_headers)  # V1 SaaS: rotas exigem autenticação


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


# =====================================================================================
# v1.2 — contratos, concentração da variação, escopo de contrato
# =====================================================================================
def test_lista_contratos_endpoint(api):
    r = api.get("/api/analytics/contratos?competencia=2026-09")
    assert r.status_code == 200
    b = r.json()
    assert b["receita_disponivel"] is False
    assert b["total"] >= 1 and len(b["itens"]) == b["total"]
    it = b["itens"][0]
    assert "despesa_liquida" in it and "gini" in it and "sinistralidade" not in it


def test_detalhe_contrato_endpoint(api):
    lista = api.get("/api/analytics/contratos?competencia=2026-09").json()["itens"]
    cid = lista[0]["id_contrato"]
    r = api.get(f"/api/analytics/contratos/{cid}?competencia=2026-09")
    assert r.status_code == 200
    b = r.json()
    assert b["receita_disponivel"] is False
    assert "Receita por contrato ainda não disponível" in b["aviso"]
    assert "concentracao" in b and "evolucao" in b
    assert api.get("/api/analytics/contratos/999999?competencia=2026-09").status_code == 404


def test_concentracao_variacao_endpoint(api):
    r = api.get("/api/analytics/sinistralidade/concentracao-variacao?competencia=2026-09")
    assert r.status_code == 200
    b = r.json()
    assert "top" in b and "n_para_credito_50pct" in b and "gini_do_aumento" in b


def test_explain_com_contrato_id(api):
    cid = api.get("/api/analytics/contratos?competencia=2026-09").json()["itens"][0]["id_contrato"]
    r = api.get(f"/api/analytics/sinistralidade/explain?competencia=2026-09&contrato_id={cid}")
    assert r.status_code == 200
    b = r.json()
    assert b["sinistralidade_atual"] is None
    assert b["efeito_receita_pp"] is None
    assert b["escopo"]["id_contrato"] == cid
    # contrato inexistente -> 404
    assert api.get(
        "/api/analytics/sinistralidade/explain?competencia=2026-09&contrato_id=999999"
    ).status_code == 404


def test_composicao_por_dimensao_endpoint(api):
    r = api.get(
        "/api/analytics/sinistralidade/composicao?competencia=2026-09&dimensao=especialidade&chave=1"
    )
    assert r.status_code == 200
    b = r.json()
    assert b["decomposicao"] is None  # sem receita no escopo de dimensão
    a = b["atual"]
    assert a["despesa_liquida"] == pytest.approx(
        a["despesa_bruta"] - a["glosas"] - a["coparticipacao"], abs=0.5
    )


def test_catalogo_contratos(api):
    r = api.get("/api/catalogos/contratos")
    assert r.status_code == 200
    assert len(r.json()["itens"]) >= 40


def test_beneficiario_detalhe_tem_comportamento(api):
    r = api.get("/api/analytics/beneficiarios/BEN-000001?competencia=2026-09")
    assert r.status_code == 200
    b = r.json()
    assert "comportamento" in b
    if b["comportamento"]:
        assert "recorrencia" in b["comportamento"]
        assert "participacao_variacao" in b["comportamento"]


def test_novos_casos_alto_custo_endpoint(api):
    r = api.get("/api/analytics/beneficiarios/novos-casos-alto-custo?competencia=2026-09")
    assert r.status_code == 200
    b = r.json()
    assert "total" in b and "itens" in b and "limiar" in b
