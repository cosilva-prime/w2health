"""Administração Works2Data (/api/admin) e do tenant (/api/tenant): confinamento,
tenants, planos, usuários, branding, configurações, segredos e auditoria."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.models import TenantSecret, User, UserTenant
from tests.conftest import (
    TENANT_A,
    TENANT_B,
    TEST_PASSWORD,
    create_user,
    iso_client,
    login,
    make_client,
)

pytestmark = pytest.mark.scenarios

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


@pytest.fixture
def sa(iso_env):
    return iso_client(iso_env, "superadmin@iso.example", None)


@pytest.fixture
def ta(iso_env):
    return iso_client(iso_env, "a.admin@iso.example", TENANT_A)


def _auditado(iso_env, acao: str, **filtros) -> int:
    where = " AND ".join(f"{k} = :{k}" for k in filtros)
    sql = "SELECT count(*) FROM audit_logs WHERE action = :acao" + (f" AND {where}" if where else "")
    with iso_env.owner() as s:
        return s.execute(text(sql), {"acao": acao, **filtros}).scalar_one()


# ========================================================================= SUPER_ADMIN
def test_ciclo_de_vida_do_tenant(iso_env, sa):
    r = sa.post("/api/admin/tenants", json={"code": "tenant-novo", "name": "Operadora Nova",
                                           "plan_code": "BUSINESS"})
    assert r.status_code == 201 and r.json()["plan"]["code"] == "BUSINESS"
    assert sa.post("/api/admin/tenants", json={"code": "tenant-novo", "name": "x y"}).status_code == 422
    assert sa.post("/api/admin/tenants", json={"code": "Inválido!", "name": "x y"}).status_code == 422
    ov = sa.get("/api/admin/tenants/tenant-novo").json()
    assert set(ov) >= {"tenant", "features", "users", "branding", "settings", "secrets", "recent_audit"}
    assert sa.post("/api/admin/tenants/tenant-novo/status",
                   json={"status": "SUSPENDED", "reason": "inadimplência"}).json()["status"] == "SUSPENDED"
    assert sa.put("/api/admin/tenants/tenant-novo/plan", json={"plan_code": "ENTERPRISE"}).status_code == 200
    assert _auditado(iso_env, "tenant.created", tenant_id="tenant-novo") == 1
    assert _auditado(iso_env, "tenant.status_changed", tenant_id="tenant-novo") == 1
    assert _auditado(iso_env, "tenant.plan_changed", tenant_id="tenant-novo") == 1
    sa.post("/api/admin/tenants/tenant-novo/status", json={"status": "ACTIVE", "reason": "regularizado"})


def test_matriz_de_planos_e_configuravel(iso_env, sa):
    m = sa.get("/api/admin/plans").json()
    basic = next(p for p in m["plans"] if p["code"] == "BASIC")
    assert "provider_intelligence" not in basic["features"]
    r = sa.put("/api/admin/plans/BASIC/features/provider_intelligence", json={"included": True})
    assert "provider_intelligence" in next(p for p in r.json()["plans"] if p["code"] == "BASIC")["features"]
    sa.put("/api/admin/plans/BASIC/features/provider_intelligence", json={"included": False})
    assert _auditado(iso_env, "plan.feature_changed") >= 2


def test_usuarios_criacao_com_senha_temporaria_e_reset(iso_env, sa):
    r = sa.post(f"/api/admin/tenants/{TENANT_B}/users",
                json={"email": "Novo.B@ISO.example", "name": "Novo B", "role": "VIEWER"})
    assert r.status_code == 201
    temp = r.json()["temporary_password"]
    assert temp and r.json()["member"]["email"] == "novo.b@iso.example"
    anon = make_client(iso_env.app)
    assert login(anon, "novo.b@iso.example", temp).json()["status"] == "password_change_required"
    with iso_env.owner() as s:
        uid = s.execute(select(User.id).where(User.email == "novo.b@iso.example")).scalar_one()
        auditoria = " ".join(str(d) for d in s.execute(text("SELECT details FROM audit_logs")).scalars())
    assert temp not in auditoria  # senha temporária nunca na trilha
    r = sa.post(f"/api/admin/users/{uid}/reset-password", json={"reason": "esqueceu"})
    assert r.status_code == 200 and r.json()["temporary_password"] != temp
    assert sa.post(f"/api/admin/tenants/{TENANT_B}/users",
                   json={"email": "x@iso.example", "name": "Xis", "role": "SUPER_ADMIN"}).status_code == 403


def test_super_admin_nao_altera_o_proprio_status(iso_env, sa):
    with iso_env.owner() as s:
        uid = s.execute(select(User.id).where(User.email == "superadmin@iso.example")).scalar_one()
    assert sa.patch(f"/api/admin/users/{uid}", json={"status": "INACTIVE"}).status_code == 403


def test_segredos_sao_write_only_e_cifrados(iso_env, sa):
    valor = "s3nh4-do-banco-do-cliente"
    r = sa.put(f"/api/admin/tenants/{TENANT_A}/secrets/mv.db_password", json={"value": valor})
    assert r.status_code == 200 and valor not in r.text
    listagem = sa.get(f"/api/admin/tenants/{TENANT_A}/secrets")
    assert valor not in listagem.text and listagem.json()["itens"][0]["key"] == "mv.db_password"
    assert valor not in sa.get(f"/api/admin/tenants/{TENANT_A}").text
    with iso_env.owner() as s:
        row = s.get(TenantSecret, (TENANT_A, "mv.db_password"))
        from app.saas.secrets import reveal

        assert valor not in row.ciphertext and reveal(s, TENANT_A, "mv.db_password") == valor
    assert sa.put(f"/api/admin/tenants/{TENANT_A}/secrets/Chave Inválida", json={"value": "x"}).status_code == 422
    assert _auditado(iso_env, "secret.created", tenant_id=TENANT_A) == 1


def test_auditoria_da_plataforma_filtra_por_tenant(iso_env, sa):
    r = sa.get(f"/api/admin/audit?tenant_id={TENANT_A}&limit=50")
    assert r.status_code == 200 and all(a["tenant_id"] == TENANT_A for a in r.json()["itens"])


# ======================================================================= TENANT_ADMIN
def test_tenant_admin_gerencia_usuarios_do_proprio_tenant(iso_env, ta):
    r = ta.post("/api/tenant/users", json={"email": "contratado@iso.example", "name": "Contratado",
                                          "role": "MANAGER"})
    assert r.status_code == 201 and r.json()["temporary_password"]
    uid = r.json()["member"]["user_id"]
    r = ta.patch(f"/api/tenant/users/{uid}", json={"role": "VIEWER"})
    assert r.status_code == 200 and r.json()["role"] == "VIEWER"
    assert ta.post(f"/api/tenant/users/{uid}/reset-password", json={"reason": "pedido"}).status_code == 200
    assert _auditado(iso_env, "user.membership_changed", tenant_id=TENANT_A) >= 1


def test_tenant_admin_confinado(iso_env, ta):
    # não promove a SUPER_ADMIN
    r = ta.post("/api/tenant/users", json={"email": "esc@iso.example", "name": "Esc", "role": "SUPER_ADMIN"})
    assert r.status_code == 403
    # não alcança usuário de outro tenant (indistinguível de inexistente)
    with iso_env.owner() as s:
        uid_b = s.execute(select(User.id).where(User.email == "b.manager@iso.example")).scalar_one()
    assert ta.patch(f"/api/tenant/users/{uid_b}", json={"role": "VIEWER"}).status_code == 404
    assert ta.post(f"/api/tenant/users/{uid_b}/reset-password", json={"reason": "x x"}).status_code == 404
    # não altera o próprio acesso
    with iso_env.owner() as s:
        uid_self = s.execute(select(User.id).where(User.email == "a.admin@iso.example")).scalar_one()
    assert ta.patch(f"/api/tenant/users/{uid_self}", json={"role": "VIEWER"}).status_code == 403
    # não edita limite contratual
    r = ta.put("/api/tenant/settings/limits.max_users", json={"value": 9999})
    assert r.status_code == 403
    # configuração desconhecida é rejeitada
    assert ta.put("/api/tenant/settings/qualquer.coisa", json={"value": 1}).status_code == 422
    assert _auditado(iso_env, "access.denied", tenant_id=TENANT_A) >= 1


def test_tenant_admin_nao_reseta_conta_compartilhada_com_outro_tenant(iso_env, ta):
    uid = create_user(iso_env, "compartilhado@iso.example", tenant=TENANT_A, role="VIEWER")
    with iso_env.owner() as s:
        s.add(UserTenant(user_id=uid, tenant_id=TENANT_B, role="VIEWER"))
        s.commit()
    r = ta.post(f"/api/tenant/users/{uid}/reset-password", json={"reason": "tentativa"})
    assert r.status_code == 403
    assert ta.post(f"/api/tenant/users/{uid}/reset-mfa", json={"reason": "tentativa"}).status_code == 403


def test_ultimo_tenant_admin_nao_pode_ser_rebaixado(iso_env):
    import uuid

    from app.saas import users as users_svc
    from tests.conftest import create_tenant

    create_tenant(iso_env, "tenant-solo")
    uid1 = create_user(iso_env, "solo.admin@iso.example", tenant="tenant-solo", role="TENANT_ADMIN")
    uid2 = create_user(iso_env, "solo.admin2@iso.example", tenant="tenant-solo", role="TENANT_ADMIN")
    c = iso_client(iso_env, "solo.admin@iso.example", "tenant-solo")
    # rebaixar OUTRO admin é permitido (ainda resta um) e derruba as sessões dele no tenant
    c2 = iso_client(iso_env, "solo.admin2@iso.example", "tenant-solo")
    assert c.patch(f"/api/tenant/users/{uid2}", json={"role": "VIEWER"}).status_code == 200
    assert c2.get("/api/tenant/users").status_code == 401
    # o único admin não altera o próprio acesso
    assert c.patch(f"/api/tenant/users/{uid1}", json={"role": "VIEWER"}).status_code == 403
    # invariante no serviço: o último TENANT_ADMIN ativo não pode ser rebaixado/desativado
    with iso_env.owner() as s:
        with pytest.raises(users_svc.UserAdminError):
            users_svc.update_member(s, "tenant-solo", uid1, actor_id=uuid.uuid4(), role="VIEWER",
                                    status=None, by_platform=False)
        s.rollback()


def test_limite_de_usuarios_e_respeitado(iso_env, sa):
    from tests.conftest import create_tenant

    create_tenant(iso_env, "tenant-limite")
    assert sa.put("/api/admin/tenants/tenant-limite/settings/limits.max_users", json={"value": 1}).status_code == 200
    assert sa.post("/api/admin/tenants/tenant-limite/users",
                   json={"email": "l1@iso.example", "name": "L1", "role": "TENANT_ADMIN"}).status_code == 201
    r = sa.post("/api/admin/tenants/tenant-limite/users",
                json={"email": "l2@iso.example", "name": "L2", "role": "VIEWER"})
    assert r.status_code == 422 and "limite" in r.json()["detail"]


# ============================================================================ branding
def test_branding_validado_e_auditado(iso_env, ta):
    assert ta.put("/api/tenant/branding", json={"primary_color": "red"}).status_code == 422
    assert ta.put("/api/tenant/branding", json={"primary_color": "#ffff00"}).status_code == 422  # contraste
    assert ta.put("/api/tenant/branding", json={"product_name": "<script>x</script>"}).status_code == 422
    r = ta.put("/api/tenant/branding", json={"product_name": "Vida+ Analytics", "primary_color": "#1E3A8A"})
    assert r.status_code == 200 and r.json()["effective"]["primary_color"] == "#1e3a8a"
    assert ta.post("/api/tenant/branding/logo", files={"file": ("x.svg", b"<svg onload=alert(1)>", "image/svg+xml")}).status_code == 422
    assert ta.post("/api/tenant/branding/logo", files={"file": ("x.png", b"GIF89a" + b"0" * 20, "image/png")}).status_code == 422
    r = ta.post("/api/tenant/branding/logo", files={"file": ("logo.png", PNG_1PX, "image/png")})
    assert r.status_code == 200 and r.json()["content_type"] == "image/png"
    me = ta.get("/api/auth/me").json()
    assert me["branding"]["product_name"] == "Vida+ Analytics" and me["branding"]["logo_url"]
    pub = make_client(iso_env.app)
    img = pub.get("/api" + me["branding"]["logo_url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert img.headers["x-content-type-options"] == "nosniff"
    assert _auditado(iso_env, "branding.updated", tenant_id=TENANT_A) >= 1
    ta.put("/api/tenant/branding", json={"product_name": None, "primary_color": None})
    ta.delete("/api/tenant/branding/logo")


def test_branding_publico_nao_enumera_tenants(iso_env):
    pub = make_client(iso_env.app)
    padrao = pub.get("/api/public/branding?tenant=nao-existe").json()
    assert pub.get("/api/public/branding").json() == padrao
    assert padrao["product_name"] == "W2Health Intelligence"


def test_viewer_nao_altera_branding_nem_configuracao(iso_env):
    c = iso_client(iso_env, "a.viewer@iso.example", TENANT_A)
    assert c.put("/api/tenant/branding", json={"product_name": "x"}).status_code == 403
    assert c.put("/api/tenant/settings/analysis.default_comparison", json={"value": "ano_anterior"}).status_code == 403


def test_configuracao_funcional_do_tenant(iso_env, ta):
    r = ta.put("/api/tenant/settings/analysis.default_comparison", json={"value": "ano_anterior"})
    assert r.status_code == 200
    assert ta.get("/api/auth/me").json()["settings"]["analysis.default_comparison"] == "ano_anterior"
    assert ta.put("/api/tenant/settings/analysis.default_comparison", json={"value": "invalida"}).status_code == 422
    ta.put("/api/tenant/settings/analysis.default_comparison", json={"value": "mes_anterior"})


def test_auditoria_do_tenant_so_mostra_o_proprio(iso_env, ta):
    itens = ta.get("/api/tenant/audit?limit=200").json()["itens"]
    assert itens and all(a["tenant_id"] == TENANT_A for a in itens)


def test_auditoria_nunca_contem_senha(iso_env):
    with iso_env.owner() as s:
        texto = " ".join(str(d) for d in s.execute(text("SELECT details FROM audit_logs")).scalars())
    assert TEST_PASSWORD not in texto
