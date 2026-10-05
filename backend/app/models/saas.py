"""Control plane da Fundação SaaS V1 — identidade, acesso, comercial, personalização e auditoria.

Todas as tabelas aqui usam `ControlBase` (não recebem RLS): o isolamento é responsabilidade
das dependências de autorização (`app/security/deps.py`) e dos serviços (`app/saas/`), que
sempre recebem o tenant do contexto autenticado — nunca do corpo/parâmetro da requisição.

Grupos:
  * Identidade e acesso — `users`, `user_tenants`, `auth_sessions`, `refresh_tokens`
  * Comercial            — `plans`, `features`, `plan_features`, `tenant_features`
  * Personalização       — `tenant_branding`, `tenant_branding_assets`, `tenant_settings`
  * Segredos             — `tenant_secrets` (valores cifrados, nunca devolvidos pela API)
  * Auditoria            — `audit_logs` (append-only para o papel de runtime)
"""

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import ControlBase

# ------------------------------------------------------------------------ vocabulários
USER_STATUS = ("ACTIVE", "INACTIVE")
MEMBERSHIP_STATUS = ("ACTIVE", "INACTIVE")
TENANT_STATUS = ("ACTIVE", "SUSPENDED", "INACTIVE")
PLATFORM_ROLES = ("SUPER_ADMIN",)
TENANT_ROLES = ("TENANT_ADMIN", "MANAGER", "VIEWER")
BRANDING_ASSET_KINDS = ("logo", "favicon")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


def _ts_created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _ts_updated() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============================================================== identidade e acesso
class User(ControlBase):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in("status", USER_STATUS), name="status_valido"),
        CheckConstraint(
            f"platform_role IS NULL OR {_in('platform_role', PLATFORM_ROLES)}",
            name="platform_role_valido",
        ),
        CheckConstraint("email = lower(email)", name="email_minusculo"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    # argon2id (app/security/passwords.py). Nunca senha em claro.
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    # Papel de PLATAFORMA (equipe Works2Data). Papéis de tenant ficam em `user_tenants`.
    platform_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # MFA (TOTP). Segredos cifrados com Fernet (app/security/crypto.py) — nunca em claro.
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    mfa_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_pending_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Último time-step TOTP aceito — impede reuso do mesmo código (replay).
    mfa_last_used_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Proteção de força bruta (por conta).
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Incrementar invalida TODOS os access tokens emitidos (troca de senha, reset, desativação).
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _ts_created()
    updated_at: Mapped[datetime] = _ts_updated()

    @property
    def is_super_admin(self) -> bool:
        return self.platform_role == "SUPER_ADMIN"


class UserTenant(ControlBase):
    """Vínculo usuário × tenant com o papel do usuário NAQUELE tenant."""

    __tablename__ = "user_tenants"
    __table_args__ = (
        CheckConstraint(_in("role", TENANT_ROLES), name="role_valido"),
        CheckConstraint(_in("status", MEMBERSHIP_STATUS), name="status_valido"),
    )

    user_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = _ts_created()
    updated_at: Mapped[datetime] = _ts_updated()


class AuthSession(ControlBase):
    """Uma sessão de login (família de refresh tokens). Revogar = derrubar a sessão inteira."""

    __tablename__ = "auth_sessions"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    user_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Tenant ativo da sessão (NULL = SUPER_ADMIN sem tenant selecionado).
    tenant_id: Mapped[str | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = _ts_created()
    last_seen_at: Mapped[datetime] = _ts_created()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)


class RefreshToken(ControlBase):
    """Refresh token opaco — só o hash SHA-256 é persistido. Rotação a cada uso;
    reapresentar um token já usado revoga a sessão (detecção de roubo/replay)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    session_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _ts_created()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ============================================================================ comercial
class Plan(ControlBase):
    """Plano comercial = conjunto PADRÃO de features. Nenhuma regra de negócio consulta o
    código do plano — só `app/saas/features.has_feature`."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(400), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = _ts_created()
    updated_at: Mapped[datetime] = _ts_updated()


class Feature(ControlBase):
    """Capability do produto. `is_active=false` é o kill switch GLOBAL (vale para todos)."""

    __tablename__ = "features"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(400), default="", server_default="")
    module: Mapped[str] = mapped_column(String(60), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = _ts_created()
    updated_at: Mapped[datetime] = _ts_updated()


class PlanFeature(ControlBase):
    __tablename__ = "plan_features"

    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True)
    feature_key: Mapped[str] = mapped_column(
        ForeignKey("features.key", ondelete="CASCADE"), primary_key=True
    )


class TenantFeature(ControlBase):
    """Override EXPLÍCITO por tenant (habilita ou desabilita), sempre com motivo."""

    __tablename__ = "tenant_features"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    feature_key: Mapped[str] = mapped_column(
        ForeignKey("features.key", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(300), default="", server_default="")
    updated_by: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = _ts_updated()


# ======================================================================= personalização
class TenantBranding(ControlBase):
    """White-label LIMITADO: nome de produto, 2 cores validadas (hex) e textos de login.
    Nenhum CSS/HTML/JS arbitrário é aceito ou armazenado."""

    __tablename__ = "tenant_branding"
    __table_args__ = (
        CheckConstraint(
            "primary_color IS NULL OR primary_color ~ '^#[0-9a-f]{6}$'", name="primary_hex"
        ),
        CheckConstraint(
            "accent_color IS NULL OR accent_color ~ '^#[0-9a-f]{6}$'", name="accent_hex"
        ),
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    product_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    login_title: Mapped[str | None] = mapped_column(String(80), nullable=True)
    login_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_by: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = _ts_updated()


class TenantBrandingAsset(ControlBase):
    """Logo/favicon validados (PNG/JPEG/WebP por assinatura de bytes, ≤ 256 KB).
    SVG não é aceito (pode carregar script)."""

    __tablename__ = "tenant_branding_assets"
    __table_args__ = (CheckConstraint(_in("kind", BRANDING_ASSET_KINDS), name="kind_valido"),)

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(40))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    updated_by: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = _ts_updated()


class TenantSetting(ControlBase):
    """Configuração FUNCIONAL (não sensível). Chaves e validação vêm do catálogo fechado
    `app/saas/settings_catalog.py` — chave desconhecida é rejeitada."""

    __tablename__ = "tenant_settings"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_by: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = _ts_updated()


class TenantSecret(ControlBase):
    """Credencial/segredo de integração — cifrado (Fernet). A API nunca devolve o valor."""

    __tablename__ = "tenant_secrets"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = _ts_created()
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ============================================================================ auditoria
class AuditLog(ControlBase):
    """Trilha de auditoria. Append-only para o papel de runtime (sem UPDATE/DELETE — grants
    da migration). `details` passa por `app/saas/audit.sanitize` (sem senha/token/segredo)."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(_in("outcome", ("success", "failure", "denied")), name="outcome_valido"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor_user_id: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    actor_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Sem FK: a trilha sobrevive à remoção do tenant.
    tenant_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    outcome: Mapped[str] = mapped_column(String(10), default="success")
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
