"""Autenticação (Fundação SaaS V1): login, erros genéricos, usuário inativo, tenant suspenso,
tokens inválidos/expirados/forjados, refresh com rotação e detecção de reuso, logout,
bloqueio por força bruta, limite por IP, troca de senha e troca obrigatória."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select, text

from app.core.config import get_settings
from app.models import User
from app.security.passwords import hash_password, verify_password
from tests.conftest import (
    TENANT_A,
    TEST_PASSWORD,
    create_tenant,
    create_user,
    iso_client,
    login,
    make_client,
)

pytestmark = pytest.mark.scenarios

NOVA_SENHA = "Nova-Senha-Forte-2026!"


@pytest.fixture
def anon(iso_env):
    return make_client(iso_env.app)


# ================================================================================= login
def test_login_valido_emite_access_e_cookie_httponly(iso_env, anon):
    create_user(iso_env, "login.ok@iso.example", tenant=TENANT_A, role="VIEWER")
    r = login(anon, "login.ok@iso.example")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["token_type"] == "bearer" and body["expires_in"] > 0
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/auth" in cookie
    me = anon.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["tenant"]["id"] == TENANT_A and me.json()["role"] == "VIEWER"


def test_senha_invalida_e_email_inexistente_tem_a_mesma_resposta(iso_env, anon):
    create_user(iso_env, "login.err@iso.example", tenant=TENANT_A, role="VIEWER")
    r1 = login(anon, "login.err@iso.example", "senha-errada-123")
    r2 = login(anon, "nao.existe@iso.example", "senha-errada-123")
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"] and r1.json()["code"] == "invalid_credentials"


def test_usuario_inativo_nao_entra(iso_env, anon):
    create_user(iso_env, "inativo@iso.example", tenant=TENANT_A, role="VIEWER", status="INACTIVE")
    r = login(anon, "inativo@iso.example")
    assert r.status_code == 403 and "access_token" not in r.json()


def test_tenant_suspenso_bloqueia_login_e_token_existente(iso_env, anon):
    create_tenant(iso_env, "tenant-suspenso", status="ACTIVE")
    create_user(iso_env, "susp@iso.example", tenant="tenant-suspenso", role="MANAGER")
    c = iso_client(iso_env, "susp@iso.example", "tenant-suspenso")
    create_tenant(iso_env, "tenant-suspenso", status="SUSPENDED")
    r = c.get("/api/meta/competencias")
    assert r.status_code == 403 and r.json()["code"] == "tenant_suspended"
    r = login(anon, "susp@iso.example")
    assert r.status_code == 403 and r.json()["code"] == "tenant_suspended"


def test_usuario_sem_vinculo_nao_tem_acesso(iso_env, anon):
    create_user(iso_env, "sem.vinculo@iso.example")
    r = login(anon, "sem.vinculo@iso.example")
    assert r.status_code == 403 and r.json()["code"] == "no_tenant_access"


# ================================================================================ tokens
def test_sem_token_e_token_invalido(iso_env, anon):
    assert anon.get("/api/executive/overview").json()["code"] == "not_authenticated"
    r = anon.get("/api/executive/overview", headers={"Authorization": "Bearer lixo.lixo.lixo"})
    assert r.status_code == 401 and r.json()["code"] == "not_authenticated"


def test_token_assinado_com_outra_chave_ou_alg_none_e_rejeitado(iso_env, anon):
    s = get_settings()
    claims = {"sub": "00000000-0000-0000-0000-000000000000", "sid": "00000000-0000-0000-0000-000000000000",
              "tid": TENANT_A, "ver": 0, "typ": "access", "iss": s.jwt_issuer, "aud": s.jwt_audience,
              "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(minutes=5)}
    for tok in (jwt.encode(claims, "outra-chave-" * 4, algorithm="HS256"),
                jwt.encode(claims, None, algorithm="none")):
        r = anon.get("/api/executive/overview", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401


def test_token_expirado_retorna_sessao_expirada(iso_env, anon):
    from app.security import tokens

    s = get_settings()
    claims = {"sub": "00000000-0000-0000-0000-000000000000", "sid": "00000000-0000-0000-0000-000000000000",
              "tid": TENANT_A, "ver": 0, "typ": "access", "iss": s.jwt_issuer, "aud": s.jwt_audience,
              "iat": datetime.now(UTC) - timedelta(hours=1), "exp": datetime.now(UTC) - timedelta(minutes=1)}
    tok = jwt.encode(claims, tokens._signing_key(), algorithm="HS256")
    r = anon.get("/api/executive/overview", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401 and r.json()["code"] == "session_expired"


def test_challenge_token_nao_da_acesso_a_dados(iso_env, anon):
    from app.security.tokens import create_challenge_token

    uid = create_user(iso_env, "chall@iso.example", tenant=TENANT_A, role="MANAGER")
    tok = create_challenge_token(user_id=uid, typ="mfa", token_version=0)
    r = anon.get("/api/executive/overview", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


# ======================================================================= refresh / logout
def test_refresh_rotaciona_e_reuso_revoga_a_sessao(iso_env, anon):
    create_user(iso_env, "refresh@iso.example", tenant=TENANT_A, role="VIEWER")
    r = login(anon, "refresh@iso.example")
    cookie_antigo = anon.cookies.get(get_settings().refresh_cookie_name)
    r2 = anon.post("/api/auth/refresh")
    assert r2.status_code == 200
    novo = r2.json()["access_token"]
    assert anon.get("/api/meta/competencias", headers={"Authorization": f"Bearer {novo}"}).status_code == 200
    # reapresentar o refresh já consumido = roubo → sessão inteira revogada
    atacante = make_client(iso_env.app)
    atacante.cookies.set(get_settings().refresh_cookie_name, cookie_antigo, path="/api/auth")
    assert atacante.post("/api/auth/refresh").status_code == 401
    assert anon.get("/api/meta/competencias", headers={"Authorization": f"Bearer {novo}"}).status_code == 401
    assert anon.post("/api/auth/refresh").status_code == 401
    with iso_env.owner() as s:
        n = s.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'auth.refresh_reuse_detected'")).scalar_one()
    assert n >= 1
    assert r.status_code == 200


def test_refresh_sem_cookie(anon):
    r = anon.post("/api/auth/refresh")
    assert r.status_code == 401 and r.json()["code"] == "session_expired"


def test_logout_revoga_access_e_refresh(iso_env, anon):
    create_user(iso_env, "logout@iso.example", tenant=TENANT_A, role="VIEWER")
    tok = login(anon, "logout@iso.example").json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert anon.post("/api/auth/logout", headers=h).status_code == 204
    assert anon.get("/api/meta/competencias", headers=h).status_code == 401
    assert anon.post("/api/auth/refresh").status_code == 401


# ============================================================================ força bruta
def test_bloqueio_apos_falhas_consecutivas(iso_env, anon):
    create_user(iso_env, "bruta@iso.example", tenant=TENANT_A, role="VIEWER")
    for _ in range(get_settings().login_max_failures):
        assert login(anon, "bruta@iso.example", "errada-errada-1").status_code == 401
    r = login(anon, "bruta@iso.example")  # senha correta, mas bloqueado
    assert r.status_code == 401 and r.json()["code"] == "invalid_credentials"
    with iso_env.owner() as s:
        acoes = set(s.execute(text("SELECT action FROM audit_logs WHERE actor_email = 'bruta@iso.example'")).scalars())
    assert {"auth.login_failed", "auth.account_locked", "auth.login_blocked"} <= acoes


def test_limite_por_ip(iso_env, anon):
    from app.api.v1.routes.auth import auth_limiter

    original = auth_limiter.limit
    auth_limiter.limit = 3
    try:
        codigos = [login(anon, "x@iso.example", "y-y-y-y-y-y-y").status_code for _ in range(4)]
    finally:
        auth_limiter.limit = original
    assert codigos[:3] == [401, 401, 401] and codigos[3] == 429


# ==================================================================================== senha
def test_troca_de_senha_exige_atual_e_revoga_outras_sessoes(iso_env, anon):
    create_user(iso_env, "troca@iso.example", tenant=TENANT_A, role="VIEWER")
    outra = make_client(iso_env.app)
    tok_outra = login(outra, "troca@iso.example").json()["access_token"]
    tok = login(anon, "troca@iso.example").json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = anon.post("/api/auth/password", headers=h, json={"current_password": "errada", "new_password": NOVA_SENHA})
    assert r.status_code == 422
    r = anon.post("/api/auth/password", headers=h, json={"current_password": TEST_PASSWORD, "new_password": "curta"})
    assert r.status_code == 422
    r = anon.post("/api/auth/password", headers=h, json={"current_password": TEST_PASSWORD, "new_password": NOVA_SENHA})
    assert r.status_code == 200
    h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert anon.get("/api/meta/competencias", headers=h2).status_code == 200
    assert outra.get("/api/meta/competencias", headers={"Authorization": f"Bearer {tok_outra}"}).status_code == 401
    assert login(make_client(iso_env.app), "troca@iso.example", NOVA_SENHA).status_code == 200


def test_troca_obrigatoria_no_primeiro_acesso(iso_env, anon):
    create_user(iso_env, "primeiro@iso.example", tenant=TENANT_A, role="VIEWER", must_change_password=True)
    r = login(anon, "primeiro@iso.example")
    assert r.json()["status"] == "password_change_required" and "access_token" not in r.json()
    r = anon.post("/api/auth/password/required-change",
                  json={"challenge_token": r.json()["challenge_token"], "new_password": NOVA_SENHA})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    with iso_env.owner() as s:
        u = s.execute(select(User).where(User.email == "primeiro@iso.example")).scalar_one()
    assert not u.must_change_password and verify_password(u.password_hash, NOVA_SENHA)


def test_senha_armazenada_com_argon2id(iso_env):
    create_user(iso_env, "hash@iso.example")
    with iso_env.owner() as s:
        h = s.execute(select(User.password_hash).where(User.email == "hash@iso.example")).scalar_one()
    assert h.startswith("$argon2id$") and TEST_PASSWORD not in h
    assert hash_password(TEST_PASSWORD) != h  # salt aleatório
