"""Dependências FastAPI de autenticação/autorização — a cadeia obrigatória:

    JWT → User → Tenant Membership → TenantContext → RBAC → Feature Guard → Repository → Banco

* `get_principal`      — valida o access token e RELÊ do banco: usuário ativo, `token_version`
                         igual, sessão não revogada/expirada. Nada do token é autoridade de
                         papel.
* `get_tenant_context` — tenant ativo da sessão + vínculo ATIVO (ou SUPER_ADMIN em acesso
                         explícito) + tenant ACTIVE + features efetivas. Amarra o tenant à
                         sessão do banco (`bind_tenant` → app + RLS).
* `get_tenant_db`      — a sessão já amarrada; é a ÚNICA forma de rotas de dados obterem
                         uma sessão.
* `require_permission(...)`, `require_feature(...)`, `require_platform(...)` — guards
                         reutilizáveis; nenhuma rota compara nome de papel ou de plano.

O tenant efetivo **nunca** vem de parâmetro/corpo/cabeçalho enviado pelo cliente.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.tenant_scope import bind_tenant
from app.models import AuthSession, Tenant, User, UserTenant
from app.saas import audit
from app.saas.features import enabled_features
from app.security.errors import ApiError
from app.security.rbac import PLATFORM_PERMS, Perm, Role, tenant_permissions
from app.security.tokens import TokenError, decode_access_token


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    email: str
    name: str
    platform_role: str | None
    session_id: uuid.UUID
    tenant_id: str | None  # tenant ativo da sessão (pode ser None para SUPER_ADMIN)

    @property
    def is_super_admin(self) -> bool:
        return self.platform_role == Role.SUPER_ADMIN

    def actor(self, role: str | None = None) -> audit.Actor:
        return audit.Actor(user_id=self.user_id, email=self.email,
                           role=role or self.platform_role)


@dataclass(frozen=True)
class TenantContext:
    principal: Principal
    tenant_id: str
    tenant_name: str
    is_synthetic: bool
    role: Role
    permissions: frozenset[Perm]
    features: frozenset[str] = field(default_factory=frozenset)
    # True quando um SUPER_ADMIN opera o tenant sem vínculo (acesso de plataforma auditado)
    platform_access: bool = False

    def can(self, perm: Perm) -> bool:
        return perm in self.permissions

    def has_feature(self, key: str) -> bool:
        return key in self.features

    @property
    def actor(self) -> audit.Actor:
        return self.principal.actor(self.role.value)


def _bearer(request: Request) -> str | None:
    h = request.headers.get("authorization") or ""
    scheme, _, token = h.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def get_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    token = _bearer(request)
    if token is None:
        raise ApiError("not_authenticated")
    try:
        claims = decode_access_token(token)
        user_id = uuid.UUID(claims["sub"])
        session_id = uuid.UUID(claims["sid"])
    except TokenError as e:
        raise ApiError("session_expired" if str(e) == "expired" else "not_authenticated") from e
    except (ValueError, KeyError) as e:
        raise ApiError("not_authenticated") from e

    user = db.get(User, user_id)
    if user is None or user.status != "ACTIVE" or user.token_version != claims.get("ver"):
        raise ApiError("session_expired")
    if user.must_change_password:
        raise ApiError("session_expired")
    sess = db.get(AuthSession, session_id)
    agora = datetime.now(UTC)
    if (
        sess is None or sess.user_id != user.id or sess.revoked_at is not None
        or sess.expires_at <= agora
    ):
        raise ApiError("session_expired")
    # o tenant da sessão é a referência; o claim só precisa concordar
    if (claims.get("tid") or None) != (sess.tenant_id or None):
        raise ApiError("session_expired")

    principal = Principal(
        user_id=user.id, email=user.email, name=user.name, platform_role=user.platform_role,
        session_id=sess.id, tenant_id=sess.tenant_id,
    )
    request.state.principal = principal
    return principal


def get_tenant_context(
    request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
) -> TenantContext:
    tid = principal.tenant_id
    if not tid:
        raise ApiError("tenant_required")
    tenant = db.get(Tenant, tid)
    if tenant is None:
        raise ApiError("forbidden")
    if tenant.status != "ACTIVE":
        raise ApiError("tenant_suspended")

    platform_access = False
    if principal.is_super_admin:
        role = Role.SUPER_ADMIN
        platform_access = db.get(UserTenant, (principal.user_id, tid)) is None
    else:
        m = db.get(UserTenant, (principal.user_id, tid))
        if m is None or m.status != "ACTIVE":
            raise ApiError("forbidden")
        role = Role(m.role)

    ctx = TenantContext(
        principal=principal, tenant_id=tenant.id, tenant_name=tenant.name,
        is_synthetic=tenant.is_synthetic, role=role, permissions=tenant_permissions(role),
        features=enabled_features(db, tenant), platform_access=platform_access,
    )
    bind_tenant(db, tenant.id)
    request.state.tenant_ctx = ctx
    return ctx


def get_tenant_db(
    _ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> Session:
    """Sessão amarrada ao tenant do contexto autenticado (aplicação + RLS)."""
    return db


def _negar(request: Request, db: Session, actor: audit.Actor, tenant_id: str | None,
           motivo: str, alvo: str) -> None:
    audit.record_independent(
        db.get_bind(), "access.denied", actor=actor, tenant_id=tenant_id, outcome="denied",
        details={"motivo": motivo, "alvo": alvo, "rota": request.url.path,
                 "metodo": request.method},
    )


def require_permission(*perms: Perm):
    """Guard: o papel do usuário NO TENANT do contexto concede todas as `perms`."""

    def dep(request: Request, ctx: TenantContext = Depends(get_tenant_context),
            db: Session = Depends(get_db)) -> TenantContext:
        faltando = [p for p in perms if not ctx.can(p)]
        if faltando:
            _negar(request, db, ctx.actor, ctx.tenant_id, "permission", ",".join(faltando))
            raise ApiError("forbidden")
        return ctx

    return dep


def require_feature(*keys: str):
    """Guard: todas as capabilities habilitadas para o tenant (backend é a autoridade)."""

    def dep(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        faltando = [k for k in keys if not ctx.has_feature(k)]
        if faltando:
            raise ApiError("feature_unavailable", extra={"feature": faltando[0]})
        return ctx

    return dep


def require_platform(perm: Perm):
    """Guard de plataforma: somente SUPER_ADMIN (independe de tenant selecionado)."""
    assert perm in PLATFORM_PERMS

    def dep(request: Request, principal: Principal = Depends(get_principal),
            db: Session = Depends(get_db)) -> Principal:
        if not principal.is_super_admin:
            _negar(request, db, principal.actor(), principal.tenant_id, "platform", perm.value)
            raise ApiError("forbidden")
        return principal

    return dep
