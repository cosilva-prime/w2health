"""Features/capabilities: resolução (global → override → plano), bloqueio no backend
(mesmo com o frontend "escondendo" o menu), override e kill switch global, e saneamento das
respostas compostas (explicação, drill, insights, visão executiva)."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.models import Feature, Plan, Tenant, TenantFeature
from app.saas.feature_filters import filter_insights, sanitize
from app.saas.features import resolve_all
from tests.conftest import create_tenant, create_user, iso_client

pytestmark = pytest.mark.scenarios

T_BASIC = "tenant-basic"  # sem dados: só para gating de rotas


@pytest.fixture
def basic_client(iso_env):
    """MANAGER do tenant-b com plano BASIC (restaura ENTERPRISE ao final)."""
    with iso_env.owner() as s:
        t = s.get(Tenant, "tenant-b")
        t.plan_id = s.execute(select(Plan.id).where(Plan.code == "BASIC")).scalar_one()
        s.commit()
    try:
        yield iso_client(iso_env, "b.manager@iso.example", "tenant-b")
    finally:
        with iso_env.owner() as s:
            t = s.get(Tenant, "tenant-b")
            t.plan_id = s.execute(select(Plan.id).where(Plan.code == "ENTERPRISE")).scalar_one()
            s.execute(text("DELETE FROM tenant_features WHERE tenant_id = 'tenant-b'"))
            s.commit()


def test_resolucao_global_override_plano(iso_env):
    create_tenant(iso_env, T_BASIC, plan="BASIC")
    with iso_env.owner() as s:
        t = s.get(Tenant, T_BASIC)
        r = {x.key: x for x in resolve_all(s, t)}
        assert r["executive_overview"].enabled and r["executive_overview"].source == "plan"
        assert not r["provider_intelligence"].enabled and r["provider_intelligence"].source == "not_in_plan"
        s.add(TenantFeature(tenant_id=T_BASIC, feature_key="provider_intelligence", enabled=True, reason="teste"))
        s.add(TenantFeature(tenant_id=T_BASIC, feature_key="executive_overview", enabled=False, reason="teste"))
        s.flush()
        r = {x.key: x for x in resolve_all(s, t)}
        assert r["provider_intelligence"].enabled and r["provider_intelligence"].source == "tenant_override"
        assert not r["executive_overview"].enabled
        s.get(Feature, "provider_intelligence").is_active = False  # kill switch vence o override
        s.flush()
        r = {x.key: x for x in resolve_all(s, t)}
        assert not r["provider_intelligence"].enabled and r["provider_intelligence"].source == "global_disabled"
        t.plan_id = None
        s.flush()
        r = {x.key: x for x in resolve_all(s, t)}
        assert r["alerts"].source == "no_plan" and not r["alerts"].enabled
        s.rollback()


def test_feature_bloqueada_no_backend_mesmo_sem_menu(basic_client):
    for rota in ("/api/analytics/prestadores?competencia=2026-06",
                 "/api/analytics/prestadores/1?competencia=2026-06",
                 "/api/analytics/beneficiarios?competencia=2026-06",
                 "/api/analytics/beneficiarios/BEN-000001",
                 "/api/analytics/sinistralidade/explain?competencia=2026-06&dimensao=prestador",
                 "/api/analytics/sinistralidade/concentracao-variacao?competencia=2026-06",
                 "/api/analytics/concentracao?competencia=2026-06&base=beneficiario",
                 "/api/config/regras-alerta",
                 "/api/analytics/alertas?competencia=2026-06",
                 "/api/tenant/branding"):
        r = basic_client.get(rota)
        assert r.status_code == 403, rota
        assert r.json()["code"] in ("feature_unavailable", "forbidden"), rota
    r = basic_client.get("/api/analytics/prestadores?competencia=2026-06")
    assert r.json()["code"] == "feature_unavailable" and r.json()["feature"] == "provider_intelligence"


def test_feature_permitida_no_basic(basic_client):
    for rota in ("/api/executive/overview?competencia=2026-06",
                 "/api/analytics/sinistralidade?competencia=2026-06",
                 "/api/analytics/contratos?competencia=2026-06",
                 "/api/analytics/insights?competencia=2026-06"):
        assert basic_client.get(rota).status_code == 200, rota
    me = basic_client.get("/api/auth/me").json()
    assert "provider_intelligence" not in me["features"] and "executive_overview" in me["features"]


def test_respostas_compostas_sao_saneadas_no_basic(basic_client):
    r = basic_client.get("/api/analytics/sinistralidade/explain?competencia=2026-06&dimensao=procedimento")
    assert r.status_code == 200
    b = r.json()
    assert b["concentracao_variacao_beneficiarios"] is None
    assert "beneficiary_intelligence" in b["restricoes_plano"]
    chave = b["principais_fatores"][0]["chave"]
    d = basic_client.get(f"/api/analytics/sinistralidade/explain/procedimento/{chave}?competencia=2026-06").json()
    oi = d["onde_investigar"]
    assert oi["prestadores_maior_despesa"] == [] and oi["beneficiarios_maior_despesa"] == []
    assert set(d["restricoes_plano"]) >= {"beneficiary_intelligence", "provider_intelligence"}
    for comp in ("2026-06", "2026-07", "2026-09"):
        for i in basic_client.get(f"/api/analytics/insights?competencia={comp}&limit=100").json()["itens"]:
            assert not i["deep_link"]["rota"].startswith(("/prestadores", "/beneficiarios"))
    ex = basic_client.get("/api/executive/overview?competencia=2026-06").json()
    for i in ex["principais_fatores_atencao"]:
        assert not i["deep_link"]["rota"].startswith(("/prestadores", "/beneficiarios"))


def test_override_habilita_e_remocao_volta_ao_plano(iso_env, basic_client):
    sa = iso_client(iso_env, "superadmin@iso.example", None)
    url = "/api/admin/tenants/tenant-b/features/provider_intelligence"
    assert sa.put(url, json={"enabled": True, "reason": "piloto"}).status_code == 200
    assert basic_client.get("/api/analytics/prestadores?competencia=2026-06").status_code == 200
    assert sa.put(url, json={"enabled": None, "reason": "fim do piloto"}).status_code == 200
    assert basic_client.get("/api/analytics/prestadores?competencia=2026-06").status_code == 403
    with iso_env.owner() as s:
        n = s.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'tenant.feature_override' "
                           "AND tenant_id = 'tenant-b'")).scalar_one()
    assert n >= 2


def test_kill_switch_global_vale_inclusive_para_enterprise(iso_env):
    sa = iso_client(iso_env, "superadmin@iso.example", None)
    c = iso_client(iso_env, "a.manager@iso.example", "tenant-a")
    assert sa.patch("/api/admin/features/executive_overview", json={"is_active": False}).status_code == 200
    try:
        r = c.get("/api/executive/overview?competencia=2026-06")
        assert r.status_code == 403 and r.json()["code"] == "feature_unavailable"
    finally:
        sa.patch("/api/admin/features/executive_overview", json={"is_active": True})
    assert c.get("/api/executive/overview?competencia=2026-06").status_code == 200


def test_tenant_admin_nao_habilita_feature_nem_troca_plano(iso_env):
    create_user(iso_env, "b.admin2@iso.example", tenant="tenant-b", role="TENANT_ADMIN")
    c = iso_client(iso_env, "b.admin2@iso.example", "tenant-b")
    assert c.put("/api/admin/tenants/tenant-b/features/custom_branding",
                 json={"enabled": True, "reason": "x"}).status_code == 403
    assert c.put("/api/admin/tenants/tenant-b/plan", json={"plan_code": "ENTERPRISE"}).status_code == 403
    # não existe rota de plano/feature na área do tenant
    assert c.put("/api/tenant/plan", json={"plan_code": "ENTERPRISE"}).status_code in (404, 405)
    assert c.put("/api/tenant/features/custom_branding", json={"enabled": True}).status_code in (404, 405)


def test_sanitize_unitario():
    payload = {"a": 1, "concentracao_variacao_beneficiarios": {"x": 1},
               "onde_investigar": {"prestadores_maior_despesa": [1], "beneficiarios_maior_despesa": [2]}}
    out = sanitize(payload, frozenset({"provider_intelligence"}))
    assert out["concentracao_variacao_beneficiarios"] is None
    assert out["onde_investigar"]["prestadores_maior_despesa"] == [1]
    assert out["onde_investigar"]["beneficiarios_maior_despesa"] == []
    assert out["restricoes_plano"] == ["beneficiary_intelligence"]
    itens = [{"deep_link": {"rota": "/prestadores/1"}}, {"deep_link": {"rota": "/sinistralidade"}}]
    assert len(filter_insights(itens, frozenset({"loss_ratio_intelligence"}))) == 1
