"""MFA (TOTP): setup, QR Code, confirmação, desafio no login, anti-replay, MFA obrigatório
por tenant e para SUPER_ADMIN, desabilitação controlada, reset administrativo auditado e
segredo nunca exposto (banco cifrado, auditoria e logs)."""

from __future__ import annotations

import logging
import time

import pyotp
import pytest
from sqlalchemy import select, text

from app.models import User
from tests.conftest import (
    SUPERADMIN_EMAIL,
    TENANT_A,
    TEST_PASSWORD,
    create_tenant,
    create_user,
    iso_client,
    login,
    make_client,
)

pytestmark = pytest.mark.scenarios


def _code(secret: str, offset: int = 0) -> str:
    return pyotp.TOTP(secret).at(time.time() + offset)


def _habilitar(client, headers=None, challenge=None) -> tuple[str, dict]:
    body = {"challenge_token": challenge} if challenge else {}
    r = client.post("/api/auth/mfa/setup", json=body, headers=headers or {})
    assert r.status_code == 200, r.text
    setup = r.json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    assert setup["qr_svg"].startswith("data:image/svg+xml")
    r = client.post("/api/auth/mfa/confirm", json={"code": _code(setup["secret"]), **body}, headers=headers or {})
    assert r.status_code == 200, r.text
    return setup["secret"], r.json()


def test_setup_confirmacao_e_login_com_desafio(iso_env, caplog):
    caplog.set_level(logging.DEBUG)
    create_user(iso_env, "mfa.user@iso.example", tenant=TENANT_A, role="MANAGER")
    c = iso_client(iso_env, "mfa.user@iso.example", TENANT_A)
    secret, res = _habilitar(c)
    assert res["mfa_enabled"] is True

    anon = make_client(iso_env.app)
    r = login(anon, "mfa.user@iso.example")
    assert r.json()["status"] == "mfa_required" and "access_token" not in r.json()
    chall = r.json()["challenge_token"]
    assert anon.post("/api/auth/mfa/verify", json={"challenge_token": chall, "code": "000000"}).status_code == 401
    # próximo passo de tempo (o atual já foi consumido na confirmação — anti-replay)
    codigo = _code(secret, 30)
    r = anon.post("/api/auth/mfa/verify", json={"challenge_token": chall, "code": codigo})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    # o MESMO código não pode ser reutilizado
    r2 = login(make_client(iso_env.app), "mfa.user@iso.example")
    r3 = make_client(iso_env.app).post("/api/auth/mfa/verify",
                                       json={"challenge_token": r2.json()["challenge_token"], "code": codigo})
    assert r3.status_code == 401

    # segredo nunca em claro: banco cifrado, auditoria e logs limpos
    with iso_env.owner() as s:
        u = s.execute(select(User).where(User.email == "mfa.user@iso.example")).scalar_one()
        auditoria = " ".join(str(d) for d in s.execute(text("SELECT details FROM audit_logs")).scalars())
    assert u.mfa_secret_enc and secret not in u.mfa_secret_enc and u.mfa_pending_secret_enc is None
    assert secret not in auditoria
    assert secret not in caplog.text


def test_mfa_obrigatorio_no_tenant_forca_configuracao_no_login(iso_env):
    create_tenant(iso_env, "tenant-mfa")
    create_user(iso_env, "obrig@iso.example", tenant="tenant-mfa", role="TENANT_ADMIN")
    admin = iso_client(iso_env, "obrig@iso.example", "tenant-mfa")
    r = admin.put("/api/tenant/settings/security.require_mfa", json={"value": True})
    assert r.status_code == 200
    create_user(iso_env, "obrig2@iso.example", tenant="tenant-mfa", role="VIEWER")
    anon = make_client(iso_env.app)
    r = login(anon, "obrig2@iso.example")
    assert r.json()["status"] == "mfa_setup_required"
    chall = r.json()["challenge_token"]
    # o challenge de setup não acessa dados
    assert anon.get("/api/meta/competencias", headers={"Authorization": f"Bearer {chall}"}).status_code == 401
    _secret, res = _habilitar(anon, challenge=chall)
    assert res["status"] == "ok" and res["access_token"]  # login concluído após confirmar
    # com MFA obrigatório, o usuário não pode desabilitar
    h = {"Authorization": f"Bearer {res['access_token']}"}
    r = anon.post("/api/auth/mfa/disable", headers=h, json={"password": TEST_PASSWORD, "code": _code(_secret, 30)})
    assert r.status_code == 403


def test_super_admin_e_obrigado_a_configurar_mfa(iso_env):
    anon = make_client(iso_env.app)
    with iso_env.owner() as s:
        u = s.execute(select(User).where(User.email == SUPERADMIN_EMAIL)).scalar_one()
        ja_tem = u.mfa_enabled
    r = login(anon, SUPERADMIN_EMAIL)
    assert r.json()["status"] == ("mfa_required" if ja_tem else "mfa_setup_required")


def test_desabilitar_exige_senha_e_codigo(iso_env):
    create_user(iso_env, "desab@iso.example", tenant=TENANT_A, role="VIEWER")
    c = iso_client(iso_env, "desab@iso.example", TENANT_A)
    secret, _ = _habilitar(c)
    r = c.post("/api/auth/mfa/disable", json={"password": "errada", "code": _code(secret, 30)})
    assert r.status_code == 422
    r = c.post("/api/auth/mfa/disable", json={"password": TEST_PASSWORD, "code": _code(secret, 30)})
    assert r.status_code == 200 and r.json()["mfa_enabled"] is False


def test_reset_administrativo_e_auditado_e_derruba_sessoes(iso_env):
    uid = create_user(iso_env, "reset.mfa@iso.example", tenant=TENANT_A, role="VIEWER")
    c = iso_client(iso_env, "reset.mfa@iso.example", TENANT_A)
    _habilitar(c)
    admin = iso_client(iso_env, "a.admin@iso.example", TENANT_A)
    r = admin.post(f"/api/tenant/users/{uid}/reset-mfa", json={"reason": "perdeu o celular"})
    assert r.status_code == 200
    assert c.get("/api/meta/competencias").status_code == 401  # sessões revogadas
    with iso_env.owner() as s:
        u = s.get(User, uid)
        n = s.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'mfa.admin_reset' "
                           "AND entity_id = :e"), {"e": str(uid)}).scalar_one()
    assert not u.mfa_enabled and u.mfa_secret_enc is None and n == 1


def test_setup_quando_ja_habilitado_e_conflito(iso_env):
    create_user(iso_env, "dup.mfa@iso.example", tenant=TENANT_A, role="VIEWER")
    c = iso_client(iso_env, "dup.mfa@iso.example", TENANT_A)
    _habilitar(c)
    assert c.post("/api/auth/mfa/setup", json={}).status_code == 409
