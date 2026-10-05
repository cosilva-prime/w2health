"""Autenticação: login (+MFA, troca obrigatória de senha), refresh com rotação, logout,
seleção de tenant, `/me`, troca de senha e ciclo de vida do MFA (TOTP).

Princípios:
* Mensagens de erro genéricas (sem enumeração de contas); custo de hash igual para e-mail
  inexistente (`DUMMY_HASH`).
* Bloqueio por conta (N falhas → bloqueio temporário) + limite por IP.
* Access token curto no corpo (o frontend mantém em memória); refresh token opaco em
  cookie httpOnly/SameSite=strict restrito ao caminho `/api/auth`.
* Etapas intermediárias usam *challenge tokens* de 5 min que não dão acesso a dados.
* Nenhum segredo (senha, token, código, segredo TOTP) é logado ou auditado.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import AuthSession, Plan, Tenant, User, UserTenant
from app.saas import audit, branding, settings_catalog
from app.saas.features import enabled_features
from app.security import crypto, mfa, sessions
from app.security.deps import Principal, get_principal
from app.security.errors import ApiError
from app.security.passwords import (
    DUMMY_HASH,
    hash_password,
    needs_rehash,
    password_policy_errors,
    verify_password,
)
from app.security.rate_limit import SlidingWindowLimiter
from app.security.rbac import PLATFORM_PERMS, Role, tenant_permissions
from app.security.tokens import TokenError, create_challenge_token, decode_challenge_token

router = APIRouter(prefix="/auth", tags=["Autenticação"])

auth_limiter = SlidingWindowLimiter(get_settings().auth_rate_limit_per_minute)


# =================================================================== schemas de entrada
class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    tenant: str | None = Field(default=None, max_length=40)

    @field_validator("email")
    @classmethod
    def _norm(cls, v: str) -> str:
        return v.strip().lower()


class MfaVerifyIn(BaseModel):
    challenge_token: str = Field(max_length=2048)
    code: str = Field(min_length=6, max_length=10)


class RequiredPasswordIn(BaseModel):
    challenge_token: str = Field(max_length=2048)
    new_password: str = Field(min_length=1, max_length=256)


class SwitchTenantIn(BaseModel):
    tenant_id: str | None = Field(default=None, max_length=40)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class MfaSetupIn(BaseModel):
    challenge_token: str | None = Field(default=None, max_length=2048)


class MfaConfirmIn(BaseModel):
    code: str = Field(min_length=6, max_length=10)
    challenge_token: str | None = Field(default=None, max_length=2048)


class MfaDisableIn(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    code: str = Field(min_length=6, max_length=10)


# ============================================================================= helpers
def _now() -> datetime:
    return datetime.now(UTC)


def _ip() -> str:
    return audit.current_request_meta().ip or "?"


def _email_ref(email: str) -> str:
    """Referência não reversível ao e-mail tentado (evita gravar senha digitada no campo errado)."""
    return hashlib.sha256(email.encode()).hexdigest()[:16]


def _limitar() -> None:
    if not auth_limiter.hit(_ip()):
        raise ApiError("rate_limited")


def _set_refresh_cookie(response: Response, raw: str, expires_at: datetime) -> None:
    s = get_settings()
    response.set_cookie(
        key=s.refresh_cookie_name, value=raw,
        max_age=max(1, int((expires_at - _now()).total_seconds())),
        httponly=True, secure=s.cookie_secure, samesite=s.cookie_samesite,
        path=f"{s.api_v1_prefix}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(key=s.refresh_cookie_name, path=f"{s.api_v1_prefix}/auth",
                           httponly=True, secure=s.cookie_secure, samesite=s.cookie_samesite)


def _actor(user: User, role: str | None = None) -> audit.Actor:
    return audit.Actor(user_id=user.id, email=user.email, role=role or user.platform_role)


def _registrar_falha(db: Session, user: User) -> None:
    s = get_settings()
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= s.login_max_failures:
        user.locked_until = _now() + timedelta(minutes=s.login_lockout_minutes)
        user.failed_login_count = 0
        audit.add(db, "auth.account_locked", actor=_actor(user), entity_type="user",
                  entity_id=user.id, outcome="failure",
                  details={"minutos": s.login_lockout_minutes})


def _bloqueado(user: User) -> bool:
    return user.locked_until is not None and user.locked_until > _now()


def _tenants_acessiveis(db: Session, user: User) -> list[tuple[Tenant, str]]:
    rows = db.execute(
        select(Tenant, UserTenant.role)
        .join(UserTenant, UserTenant.tenant_id == Tenant.id)
        .where(UserTenant.user_id == user.id, UserTenant.status == "ACTIVE")
        .order_by(Tenant.name)
    ).all()
    return [(t, r) for t, r in rows]


def _escolher_tenant(db: Session, user: User, hint: str | None) -> tuple[Tenant | None, bool]:
    """(tenant, acesso_de_plataforma). Nunca confia no hint além de um vínculo válido."""
    vinculos = _tenants_acessiveis(db, user)
    ativos = [t for t, _ in vinculos if t.status == "ACTIVE"]
    if hint:
        for t in ativos:
            if t.id == hint:
                return t, False
        if user.is_super_admin:
            t = db.get(Tenant, hint)
            if t is not None and t.status == "ACTIVE":
                return t, True
    if ativos:
        return ativos[0], False
    if user.is_super_admin:
        return None, False  # modo plataforma (sem tenant)
    if vinculos:
        raise ApiError("tenant_suspended")
    raise ApiError("no_tenant_access")


def _tenant_exige_mfa(db: Session, tenant: Tenant | None) -> bool:
    return bool(tenant and settings_catalog.get_value(db, tenant.id, "security.require_mfa"))


def _precisa_configurar_mfa(db: Session, user: User, tenant: Tenant | None) -> bool:
    if user.mfa_enabled:
        return False
    return (user.is_super_admin and get_settings().super_admin_require_mfa) or _tenant_exige_mfa(db, tenant)


def _challenge(user: User, typ: str, tenant_hint: str | None) -> dict[str, Any]:
    status = {"mfa": "mfa_required", "password_change": "password_change_required",
              "mfa_setup": "mfa_setup_required"}[typ]
    return {"status": status,
            "challenge_token": create_challenge_token(user_id=user.id, typ=typ,
                                                      token_version=user.token_version,
                                                      tenant_hint=tenant_hint)}


def _finalizar_login(
    db: Session, request: Request, response: Response, user: User, *,
    tenant_hint: str | None, mfa_ok: bool,
) -> dict[str, Any]:
    if user.must_change_password:
        db.commit()
        return _challenge(user, "password_change", tenant_hint)
    if user.mfa_enabled and not mfa_ok:
        db.commit()
        return _challenge(user, "mfa", tenant_hint)

    tenant, acesso_plataforma = _escolher_tenant(db, user, tenant_hint)
    if _precisa_configurar_mfa(db, user, tenant):
        db.commit()
        return _challenge(user, "mfa_setup", tenant.id if tenant else None)

    meta = audit.current_request_meta()
    emitido = sessions.create_session(db, user, tenant.id if tenant else None,
                                      ip=meta.ip, user_agent=meta.user_agent)
    user.last_login_at = _now()
    user.failed_login_count = 0
    user.locked_until = None
    audit.add(db, "auth.login", actor=_actor(user), tenant_id=tenant.id if tenant else None,
              entity_type="session", entity_id=emitido.session_id,
              details={"mfa": user.mfa_enabled})
    if acesso_plataforma:
        audit.add(db, "platform.tenant_access", actor=_actor(user), tenant_id=tenant.id,
                  entity_type="tenant", entity_id=tenant.id, details={"via": "login"})
    db.commit()
    _set_refresh_cookie(response, emitido.refresh_token, emitido.session_expires_at)
    return {"status": "ok", "access_token": emitido.access_token, "token_type": "bearer",
            "expires_in": emitido.expires_in}


def _user_from_challenge(db: Session, token: str, expected: set[str]) -> tuple[User, dict]:
    try:
        claims = decode_challenge_token(token, expected=expected)
        user = db.get(User, uuid.UUID(claims["sub"]))
    except (TokenError, ValueError, KeyError) as e:
        raise ApiError("session_expired", "Etapa de login expirada. Entre novamente.") from e
    if user is None or user.status != "ACTIVE" or user.token_version != claims.get("ver"):
        raise ApiError("session_expired", "Etapa de login expirada. Entre novamente.")
    return user, claims


# ================================================================================ login
@router.post("/login", summary="Login com e-mail e senha")
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    _limitar()
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None:
        verify_password(DUMMY_HASH, payload.password)
        audit.record_independent(db.get_bind(), "auth.login_failed",
                                 details={"motivo": "credenciais", "email_ref": _email_ref(payload.email)})
        raise ApiError("invalid_credentials")
    if _bloqueado(user):
        verify_password(DUMMY_HASH, payload.password)
        audit.record_independent(db.get_bind(), "auth.login_blocked", actor=_actor(user),
                                 entity_type="user", entity_id=user.id)
        raise ApiError("invalid_credentials")
    if not verify_password(user.password_hash, payload.password):
        _registrar_falha(db, user)
        db.commit()
        audit.record_independent(db.get_bind(), "auth.login_failed", actor=_actor(user),
                                 entity_type="user", entity_id=user.id,
                                 details={"motivo": "credenciais"})
        raise ApiError("invalid_credentials")
    if user.status != "ACTIVE":
        audit.record_independent(db.get_bind(), "auth.login_failed", actor=_actor(user),
                                 entity_type="user", entity_id=user.id,
                                 details={"motivo": "usuario_inativo"})
        raise ApiError("forbidden", "Conta desativada. Procure o administrador do ambiente.")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    return _finalizar_login(db, request, response, user, tenant_hint=payload.tenant, mfa_ok=False)


@router.post("/mfa/verify", summary="Segunda etapa do login: código TOTP")
def mfa_verify(payload: MfaVerifyIn, request: Request, response: Response,
               db: Session = Depends(get_db)) -> dict:
    _limitar()
    user, claims = _user_from_challenge(db, payload.challenge_token, {"mfa"})
    if _bloqueado(user):
        raise ApiError("invalid_credentials")
    if not user.mfa_enabled or not user.mfa_secret_enc:
        raise ApiError("session_expired", "Etapa de login expirada. Entre novamente.")
    try:
        passo = mfa.verify(crypto.decrypt(user.mfa_secret_enc), payload.code, user.mfa_last_used_step)
    except crypto.EncryptionUnavailable as e:
        raise ApiError("service_unavailable", "MFA indisponível: configuração de criptografia ausente.") from e
    if passo is None:
        _registrar_falha(db, user)
        db.commit()
        audit.record_independent(db.get_bind(), "auth.mfa_failed", actor=_actor(user),
                                 entity_type="user", entity_id=user.id)
        raise ApiError("invalid_credentials", "Código inválido.")
    user.mfa_last_used_step = passo
    return _finalizar_login(db, request, response, user, tenant_hint=claims.get("tnh"), mfa_ok=True)


@router.post("/password/required-change", summary="Troca obrigatória de senha (primeiro acesso / reset)")
def required_password_change(payload: RequiredPasswordIn, request: Request, response: Response,
                             db: Session = Depends(get_db)) -> dict:
    _limitar()
    user, claims = _user_from_challenge(db, payload.challenge_token, {"password_change"})
    erros = password_policy_errors(payload.new_password, email=user.email)
    if verify_password(user.password_hash, payload.new_password):
        erros.append("A nova senha deve ser diferente da atual.")
    if erros:
        raise ApiError("invalid_request", " ".join(erros))
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.password_changed_at = _now()
    user.token_version += 1
    sessions.revoke_all_for_user(db, user.id, "password_changed")
    audit.add(db, "user.password_changed", actor=_actor(user), entity_type="user",
              entity_id=user.id, details={"tipo": "obrigatoria"})
    db.flush()
    return _finalizar_login(db, request, response, user, tenant_hint=claims.get("tnh"), mfa_ok=False)


# ======================================================================= sessão / tokens
@router.post("/refresh", summary="Novo access token a partir do refresh token (cookie httpOnly)")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    _limitar()
    raw = request.cookies.get(get_settings().refresh_cookie_name)
    if not raw:
        raise ApiError("session_expired")
    try:
        sess, user, novo = sessions.rotate(db, raw)
    except sessions.RefreshFailure as f:
        if f.reason == "reuse" and f.session is not None:
            audit.add(db, "auth.refresh_reuse_detected", actor=audit.Actor(user_id=f.session.user_id),
                      tenant_id=f.session.tenant_id, entity_type="session",
                      entity_id=f.session.id, outcome="denied")
        db.commit()
        _clear_refresh_cookie(response)
        raise ApiError("session_expired") from None

    # o tenant da sessão continua acessível?
    if sess.tenant_id is not None:
        t = db.get(Tenant, sess.tenant_id)
        m = db.get(UserTenant, (user.id, sess.tenant_id))
        valido = t is not None and t.status == "ACTIVE" and (
            user.is_super_admin or (m is not None and m.status == "ACTIVE"))
        if not valido:
            sessions.revoke_session(db, sess, "tenant_access_lost")
            db.commit()
            _clear_refresh_cookie(response)
            raise ApiError("session_expired")
    access, ttl = sessions.access_for(sess, user)
    db.commit()
    _set_refresh_cookie(response, novo, sess.expires_at)
    return {"status": "ok", "access_token": access, "token_type": "bearer", "expires_in": ttl}


@router.post("/logout", status_code=204, response_model=None, summary="Encerra a sessão")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> Response:
    raw = request.cookies.get(get_settings().refresh_cookie_name)
    sess = None
    if raw:
        from app.models import RefreshToken
        from app.security.tokens import hash_refresh_token

        rt = db.execute(select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(raw))).scalar_one_or_none()
        sess = db.get(AuthSession, rt.session_id) if rt else None
    if sess is None:
        try:
            sess = db.get(AuthSession, get_principal(request, db).session_id)
        except ApiError:
            sess = None
    if sess is not None and sess.revoked_at is None:
        sessions.revoke_session(db, sess, "logout")
        audit.add(db, "auth.logout", actor=audit.Actor(user_id=sess.user_id),
                  tenant_id=sess.tenant_id, entity_type="session", entity_id=sess.id)
        db.commit()
    resp = Response(status_code=204)
    _clear_refresh_cookie(resp)
    return resp


@router.post("/switch-tenant", summary="Troca o tenant ativo da sessão (validado por vínculo)")
def switch_tenant(payload: SwitchTenantIn, principal: Principal = Depends(get_principal),
                  db: Session = Depends(get_db)) -> dict:
    user = db.get(User, principal.user_id)
    sess = db.get(AuthSession, principal.session_id)
    alvo = payload.tenant_id
    acesso_plataforma = False
    if alvo is None:
        if not principal.is_super_admin:
            raise ApiError("forbidden")
        tenant = None
    else:
        tenant = db.get(Tenant, alvo)
        m = db.get(UserTenant, (user.id, alvo))
        if principal.is_super_admin:
            if tenant is None:
                raise ApiError("not_found")
            acesso_plataforma = m is None
        elif tenant is None or m is None or m.status != "ACTIVE":
            audit.record_independent(db.get_bind(), "access.denied", actor=principal.actor(),
                                     tenant_id=principal.tenant_id, outcome="denied",
                                     details={"motivo": "switch_tenant", "alvo": alvo})
            raise ApiError("forbidden")
        if tenant.status != "ACTIVE":
            raise ApiError("tenant_suspended")
        if _precisa_configurar_mfa(db, user, tenant):
            raise ApiError("mfa_setup_required")

    sess.tenant_id = tenant.id if tenant else None
    audit.add(db, "platform.tenant_access" if acesso_plataforma else "auth.tenant_switch",
              actor=principal.actor(), tenant_id=sess.tenant_id, entity_type="tenant",
              entity_id=sess.tenant_id, details={"de": principal.tenant_id})
    access, ttl = sessions.access_for(sess, user)
    db.commit()
    return {"status": "ok", "access_token": access, "token_type": "bearer", "expires_in": ttl}


# ================================================================================== /me
@router.get("/me", summary="Usuário, tenant ativo, papel, permissões, features e branding")
def me(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, principal.user_id)
    vinculos = _tenants_acessiveis(db, user)
    out: dict[str, Any] = {
        "user": {"id": str(user.id), "email": user.email, "name": user.name,
                 "platform_role": user.platform_role, "mfa_enabled": user.mfa_enabled},
        "memberships": [{"tenant_id": t.id, "tenant_name": t.name, "role": r,
                         "tenant_status": t.status} for t, r in vinculos],
        "platform_permissions": sorted(p.value for p in PLATFORM_PERMS) if principal.is_super_admin else [],
        "tenant": None, "role": None, "permissions": [], "features": [],
        "settings": {}, "branding": branding.effective(db, None),
    }
    if principal.tenant_id:
        t = db.get(Tenant, principal.tenant_id)
        if t is not None:
            plano = db.get(Plan, t.plan_id) if t.plan_id else None
            out["tenant"] = {"id": t.id, "name": t.name, "status": t.status,
                             "is_synthetic": t.is_synthetic,
                             "plan": {"code": plano.code, "name": plano.name} if plano else None}
            out["branding"] = branding.effective(db, t)
            if t.status == "ACTIVE":
                if principal.is_super_admin:
                    role = Role.SUPER_ADMIN.value
                else:
                    m = db.get(UserTenant, (user.id, t.id))
                    role = m.role if m is not None and m.status == "ACTIVE" else None
                if role:
                    out["role"] = role
                    out["permissions"] = sorted(p.value for p in tenant_permissions(role))
                    out["features"] = sorted(enabled_features(db, t))
                    out["settings"] = settings_catalog.public_values(db, t.id)
    return out


# ====================================================================== senha (logado)
@router.post("/password", summary="Troca a própria senha (exige a senha atual)")
def change_password(payload: PasswordChangeIn, principal: Principal = Depends(get_principal),
                    db: Session = Depends(get_db)) -> dict:
    _limitar()
    user = db.get(User, principal.user_id)
    if not verify_password(user.password_hash, payload.current_password):
        _registrar_falha(db, user)
        db.commit()
        raise ApiError("invalid_request", "Senha atual incorreta.")
    erros = password_policy_errors(payload.new_password, email=user.email)
    if payload.new_password == payload.current_password:
        erros.append("A nova senha deve ser diferente da atual.")
    if erros:
        raise ApiError("invalid_request", " ".join(erros))
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = _now()
    user.token_version += 1
    # derruba as OUTRAS sessões; a atual continua com um token novo
    for s in db.execute(select(AuthSession).where(
            AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None),
            AuthSession.id != principal.session_id)).scalars():
        sessions.revoke_session(db, s, "password_changed")
    audit.add(db, "user.password_changed", actor=principal.actor(), tenant_id=principal.tenant_id,
              entity_type="user", entity_id=user.id, details={"tipo": "voluntaria"})
    sess = db.get(AuthSession, principal.session_id)
    access, ttl = sessions.access_for(sess, user)
    db.commit()
    return {"status": "ok", "access_token": access, "token_type": "bearer", "expires_in": ttl}


# ================================================================================== MFA
def _usuario_mfa(request: Request, db: Session, challenge: str | None) -> tuple[User, dict | None]:
    """Usuário do fluxo de MFA: via challenge `mfa_setup` (login) ou access token (conta)."""
    if challenge:
        return _user_from_challenge(db, challenge, {"mfa_setup"})
    principal = get_principal(request, db)
    return db.get(User, principal.user_id), None


@router.post("/mfa/setup", summary="Inicia a configuração de MFA (gera segredo e QR Code)")
def mfa_setup(payload: MfaSetupIn, request: Request, db: Session = Depends(get_db)) -> dict:
    _limitar()
    user, _claims = _usuario_mfa(request, db, payload.challenge_token)
    if user.mfa_enabled:
        raise ApiError("conflict", "MFA já está habilitado nesta conta.")
    if not crypto.encryption_available():
        raise ApiError("service_unavailable", "MFA indisponível: configuração de criptografia ausente.")
    segredo = mfa.new_secret()
    user.mfa_pending_secret_enc = crypto.encrypt(segredo)
    uri = mfa.provisioning_uri(segredo, user.email)
    audit.add(db, "mfa.setup_started", actor=_actor(user), entity_type="user", entity_id=user.id)
    db.commit()
    # o segredo é exibido UMA vez (entrada manual no app autenticador); nunca é logado
    return {"otpauth_uri": uri, "qr_svg": mfa.qr_svg_data_uri(uri), "secret": segredo}


@router.post("/mfa/confirm", summary="Confirma o MFA com o primeiro código do aplicativo")
def mfa_confirm(payload: MfaConfirmIn, request: Request, response: Response,
                db: Session = Depends(get_db)) -> dict:
    _limitar()
    user, claims = _usuario_mfa(request, db, payload.challenge_token)
    if user.mfa_enabled or not user.mfa_pending_secret_enc:
        raise ApiError("conflict", "Nenhuma configuração de MFA pendente.")
    segredo = crypto.decrypt(user.mfa_pending_secret_enc)
    passo = mfa.verify(segredo, payload.code, None)
    if passo is None:
        _registrar_falha(db, user)
        db.commit()
        raise ApiError("invalid_request", "Código inválido. Confira o horário do dispositivo.")
    user.mfa_secret_enc = user.mfa_pending_secret_enc
    user.mfa_pending_secret_enc = None
    user.mfa_enabled = True
    user.mfa_last_used_step = passo
    audit.add(db, "mfa.enabled", actor=_actor(user), entity_type="user", entity_id=user.id)
    if claims is not None:  # fluxo de login com MFA obrigatório: conclui o login
        return _finalizar_login(db, request, response, user, tenant_hint=claims.get("tnh"), mfa_ok=True)
    db.commit()
    return {"status": "ok", "mfa_enabled": True}


@router.post("/mfa/disable", summary="Desabilita o MFA (exige senha + código; bloqueado se obrigatório)")
def mfa_disable(payload: MfaDisableIn, principal: Principal = Depends(get_principal),
                db: Session = Depends(get_db)) -> dict:
    _limitar()
    user = db.get(User, principal.user_id)
    if not user.mfa_enabled or not user.mfa_secret_enc:
        raise ApiError("conflict", "MFA não está habilitado.")
    tenant = db.get(Tenant, principal.tenant_id) if principal.tenant_id else None
    obrigatorio = (user.is_super_admin and get_settings().super_admin_require_mfa) or any(
        _tenant_exige_mfa(db, t) for t, _ in _tenants_acessiveis(db, user)) or _tenant_exige_mfa(db, tenant)
    if obrigatorio:
        raise ApiError("forbidden", "MFA é obrigatório para esta conta.")
    passo = mfa.verify(crypto.decrypt(user.mfa_secret_enc), payload.code, user.mfa_last_used_step)
    if not verify_password(user.password_hash, payload.password) or passo is None:
        _registrar_falha(db, user)
        db.commit()
        raise ApiError("invalid_request", "Senha ou código inválido.")
    user.mfa_enabled = False
    user.mfa_secret_enc = None
    user.mfa_last_used_step = None
    audit.add(db, "mfa.disabled", actor=principal.actor(), tenant_id=principal.tenant_id,
              entity_type="user", entity_id=user.id)
    db.commit()
    return {"status": "ok", "mfa_enabled": False}
