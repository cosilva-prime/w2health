"""Fase 2 — MFA recovery codes, rate limit compartilhado (banco), logs estruturados sem
segredo e linhagem do caminho sintético (Caminho A)."""

from __future__ import annotations

import json
import logging
import time

import pyotp
import pytest
from sqlalchemy import select, text

from app.core.logging import JsonFormatter, log_context
from app.models import UserRecoveryCode
from app.security.rate_limit import DatabaseRateLimiter
from tests.conftest import TENANT_A, create_user, iso_client, login, make_client

pytestmark = pytest.mark.scenarios


def _habilitar_mfa(c) -> tuple[str, list[str]]:
    setup = c.post("/api/auth/mfa/setup", json={}).json()
    r = c.post("/api/auth/mfa/confirm", json={"code": pyotp.TOTP(setup["secret"]).now()})
    assert r.status_code == 200, r.text
    return setup["secret"], r.json()["recovery_codes"]


def test_recovery_codes_gerados_uma_vez_hash_e_uso_unico(iso_env):
    uid = create_user(iso_env, "rec@iso.example", tenant=TENANT_A, role="VIEWER")
    secret, codigos = _habilitar_mfa(iso_client(iso_env, "rec@iso.example", TENANT_A))
    assert len(codigos) == 10 and len(set(codigos)) == 10
    with iso_env.owner() as s:
        hashes = s.execute(select(UserRecoveryCode.code_hash).where(UserRecoveryCode.user_id == uid)).scalars().all()
        auditoria = " ".join(str(d) for d in s.execute(text("SELECT details FROM audit_logs")).scalars())
    assert len(hashes) == 10 and all(h.startswith("$argon2id$") for h in hashes)
    assert all(c not in "".join(hashes) and c not in auditoria for c in codigos)

    anon = make_client(iso_env.app)
    chall = login(anon, "rec@iso.example").json()["challenge_token"]
    r = anon.post("/api/auth/mfa/verify", json={"challenge_token": chall, "recovery_code": codigos[0]})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    # o mesmo código não vale duas vezes
    chall = login(make_client(iso_env.app), "rec@iso.example").json()["challenge_token"]
    r = make_client(iso_env.app).post("/api/auth/mfa/verify",
                                      json={"challenge_token": chall, "recovery_code": codigos[0]})
    assert r.status_code == 401
    me = iso_client(iso_env, "rec@iso.example", TENANT_A).get("/api/auth/me").json()
    assert me["user"]["recovery_codes_remaining"] == 9


def test_regerar_invalida_os_anteriores(iso_env):
    create_user(iso_env, "regen@iso.example", tenant=TENANT_A, role="VIEWER")
    c = iso_client(iso_env, "regen@iso.example", TENANT_A)
    secret, antigos = _habilitar_mfa(c)
    r = c.post("/api/auth/mfa/recovery-codes", json={"code": pyotp.TOTP(secret).at(time.time() + 30)})
    assert r.status_code == 200
    novos = r.json()["recovery_codes"]
    assert not set(antigos) & set(novos)
    chall = login(make_client(iso_env.app), "regen@iso.example").json()["challenge_token"]
    r = make_client(iso_env.app).post("/api/auth/mfa/verify",
                                      json={"challenge_token": chall, "recovery_code": antigos[1]})
    assert r.status_code == 401
    with iso_env.owner() as s:
        n = s.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'mfa.recovery_codes_generated' "
                           "AND actor_email = 'regen@iso.example'")).scalar_one()
    assert n == 1


def test_reset_administrativo_apaga_recovery_codes(iso_env):
    uid = create_user(iso_env, "rec.reset@iso.example", tenant=TENANT_A, role="VIEWER")
    _habilitar_mfa(iso_client(iso_env, "rec.reset@iso.example", TENANT_A))
    admin = iso_client(iso_env, "a.admin@iso.example", TENANT_A)
    assert admin.post(f"/api/tenant/users/{uid}/reset-mfa", json={"reason": "perdeu o celular"}).status_code == 200
    with iso_env.owner() as s:
        n = s.execute(select(UserRecoveryCode).where(UserRecoveryCode.user_id == uid)).all()
    assert n == []


def test_rate_limit_compartilhado_no_banco(iso_env):
    lim = DatabaseRateLimiter(3, lambda: iso_env.app_engine)
    lim.reset()
    assert [lim.hit("10.0.0.1") for _ in range(4)] == [True, True, True, False]
    outro = DatabaseRateLimiter(3, lambda: iso_env.app_engine)  # outro "processo/réplica"
    assert outro.hit("10.0.0.1") is False and outro.hit("10.0.0.2") is True
    with iso_env.owner() as s:
        chaves = s.execute(text("SELECT key FROM auth_rate_limits")).scalars().all()
    assert all("10.0.0" not in k and len(k) == 64 for k in chaves)  # IP nunca em claro
    lim.reset()


def test_log_estruturado_com_correlacao_e_sem_segredo():
    rec = logging.LogRecord("app.pipeline", logging.INFO, "", 0, "pipeline.step", (), None)
    rec.password = "nao-pode"
    rec.stage = "silver"
    with log_context(tenant_id="tenant-a", pipeline_run_id=7, ingestion_run_id=9):
        out = json.loads(JsonFormatter().format(rec))
    assert out["tenant_id"] == "tenant-a" and out["pipeline_run_id"] == 7 and out["ingestion_run_id"] == 9
    assert out["password"] == "[REDACTED]" and out["stage"] == "silver"


def test_caminho_sintetico_tem_a_mesma_linhagem(iso_env):
    """Caminho A: o gerador é uma FONTE registrada (SYNTHETIC), com ingestão publicada e
    linhagem nas linhas canônicas — igual a uma fonte externa."""
    with iso_env.owner() as s:
        conn = s.execute(text("SELECT id, source_type FROM source_connections WHERE tenant_id = :t "
                              "AND source_type = 'SYNTHETIC'"), {"t": TENANT_A}).one()
        run = s.execute(text("SELECT status, stage FROM ingestion_runs WHERE tenant_id = :t "
                             "AND source_connection_id = :c ORDER BY id DESC LIMIT 1"),
                        {"t": TENANT_A, "c": conn[0]}).one()
        origens = s.execute(text("SELECT DISTINCT source_system, source_connection_id FROM eventos_assistenciais "
                                 "WHERE tenant_id = :t"), {"t": TENANT_A}).all()
        contratos_sem_codigo = s.execute(text("SELECT count(*) FROM contratos WHERE tenant_id = :t "
                                              "AND codigo IS NULL"), {"t": TENANT_A}).scalar_one()
    assert tuple(run) == ("SUCCESS", "AVAILABLE")
    assert origens == [("synthetic_generator", conn[0])]
    assert contratos_sem_codigo == 0
