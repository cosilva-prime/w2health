"""Segurança transversal: headers, cache, erros sem estrutura interna, fail-closed sem
tenant, redação da auditoria, política de senha e configuração de produção."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.tenant import TenantContextMissing
from app.main import create_app
from app.saas.audit import sanitize
from app.security.passwords import password_policy_errors


def test_headers_de_seguranca_e_no_store(client: TestClient):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-request-id"]


def test_erro_nao_tratado_e_generico_sem_stack_trace():
    app = create_app()

    @app.get("/api/__boom")
    def boom():
        raise RuntimeError("detalhe interno: tabela secreta xyz")

    r = TestClient(app, raise_server_exceptions=False).get("/api/__boom")
    assert r.status_code == 500
    assert r.json()["code"] == "internal_error" and "xyz" not in r.text and "Traceback" not in r.text
    assert r.json()["request_id"]


@pytest.mark.scenarios
def test_repositorio_sem_tenant_falha_fechado(seeded_sessionmaker):
    from app.repositories import analytics_repo as repo

    with seeded_sessionmaker() as s, pytest.raises(TenantContextMissing):
        repo.competencias(s)


@pytest.mark.scenarios
def test_sessao_nao_troca_de_tenant(seeded_sessionmaker):
    from app.db.tenant_scope import bind_tenant

    with seeded_sessionmaker() as s:
        bind_tenant(s, "w2h-demo")
        with pytest.raises(TenantContextMissing):
            bind_tenant(s, "outro-tenant")


def test_auditoria_redige_segredos():
    out = sanitize({"password": "x", "nested": {"refresh_token": "y", "Authorization": "z"},
                    "mfa_code": "123456", "ok": "visivel", "lista": [{"secret": 1}]})
    assert out["password"] == "[REDACTED]" and out["nested"]["refresh_token"] == "[REDACTED]"
    assert out["nested"]["Authorization"] == "[REDACTED]" and out["mfa_code"] == "[REDACTED]"
    assert out["ok"] == "visivel" and out["lista"][0]["secret"] == "[REDACTED]"


def test_politica_de_senha():
    assert password_policy_errors("curta")
    assert password_policy_errors("123456789012")
    assert password_policy_errors("maria.silva-2026!", email="maria.silva@x.example")
    assert not password_policy_errors("Uma-Senha-Bem-Forte-42")


def test_producao_exige_segredos():
    s = Settings(environment="production", jwt_secret_key=None, data_encryption_key=None, cookie_secure=False)
    problemas = s.validate_for_runtime()
    # os 3 problemas originais continuam detectados (Fase 3 acrescentou regras — ver
    # test_phase3_security.py::test_producao_fail_closed_*)
    assert any("JWT_SECRET_KEY" in p for p in problemas)
    assert any("DATA_ENCRYPTION_KEY" in p for p in problemas)
    assert any("COOKIE_SECURE" in p for p in problemas)


def test_rotas_de_dados_exigem_autenticacao(client: TestClient):
    """Toda rota fora de /health, /public e /auth (login/refresh/logout) exige token."""
    abertas = {"/", "/api/health", "/health/live", "/health/ready", "/api/auth/login", "/api/auth/refresh", "/api/auth/logout",
               "/api/auth/mfa/verify", "/api/auth/password/required-change",
               "/api/auth/mfa/setup", "/api/auth/mfa/confirm"}
    spec = client.get("/openapi.json").json()["paths"]
    for path, ops in spec.items():
        if path in abertas or path.startswith("/api/public"):
            continue
        for metodo in ops:
            url = path.replace("{", "").replace("}", "")
            r = client.request(metodo.upper(), url)
            assert r.status_code in (401, 422), f"{metodo.upper()} {path} -> {r.status_code}"
