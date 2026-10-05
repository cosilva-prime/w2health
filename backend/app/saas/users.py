"""Usuários e vínculos — regras de negócio de administração de acesso.

Regras de confinamento (valem para QUALQUER chamador; as rotas só escolhem o escopo):
* TENANT_ADMIN só enxerga/altera vínculos do PRÓPRIO tenant e só atribui
  TENANT_ADMIN/MANAGER/VIEWER — nunca SUPER_ADMIN (papel de plataforma, fora de
  `user_tenants`).
* Reset de senha/MFA por TENANT_ADMIN só para contas **exclusivas** do tenant (sem vínculo
  em outro tenant e sem papel de plataforma) — senão um admin de A tomaria uma conta que
  também acessa B.
* Ninguém altera o próprio papel/status pela administração (evita auto-bloqueio/escalada).
* O último TENANT_ADMIN ativo de um tenant não pode ser rebaixado/desativado pelo tenant.
* Limite contratual `limits.max_users` (configuração de plataforma) é respeitado.
* Senha temporária: gerada no servidor, devolvida UMA vez, troca obrigatória no 1º login.
"""

from __future__ import annotations

import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Tenant, User, UserTenant
from app.saas import settings_catalog
from app.security import sessions
from app.security.passwords import hash_password
from app.security.rbac import ASSIGNABLE_BY_TENANT_ADMIN, Role

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,}$")


class UserAdminError(ValueError):
    """Violação de regra (mensagem segura para exibir)."""


class UserAdminForbidden(PermissionError):
    pass


@dataclass
class CreatedMembership:
    user: User
    membership: UserTenant
    temporary_password: str | None  # None quando a conta já existia
    existing_account: bool


def normalize_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not _EMAIL.match(e):
        raise UserAdminError("e-mail inválido")
    return e


def temporary_password() -> str:
    return secrets.token_urlsafe(12)  # 16 caracteres, ~96 bits


def _check_role(role: str, *, by_platform: bool) -> Role:
    try:
        r = Role(role)
    except ValueError as e:
        raise UserAdminError("papel inválido") from e
    if r == Role.SUPER_ADMIN:
        raise UserAdminForbidden("SUPER_ADMIN não é um papel de tenant")
    if not by_platform and r not in ASSIGNABLE_BY_TENANT_ADMIN:
        raise UserAdminForbidden("papel não atribuível")
    return r


def active_members(session: Session, tenant_id: str) -> int:
    return session.execute(
        select(func.count()).select_from(UserTenant).join(User, User.id == UserTenant.user_id)
        .where(UserTenant.tenant_id == tenant_id, UserTenant.status == "ACTIVE",
               User.status == "ACTIVE")
    ).scalar_one()


def _admins_ativos(session: Session, tenant_id: str) -> int:
    return session.execute(
        select(func.count()).select_from(UserTenant).join(User, User.id == UserTenant.user_id)
        .where(UserTenant.tenant_id == tenant_id, UserTenant.status == "ACTIVE",
               UserTenant.role == "TENANT_ADMIN", User.status == "ACTIVE")
    ).scalar_one()


def _checar_limite(session: Session, tenant_id: str) -> None:
    limite = settings_catalog.get_value(session, tenant_id, "limits.max_users")
    if active_members(session, tenant_id) >= limite:
        raise UserAdminError(f"limite contratual de {limite} usuários ativos atingido")


def list_members(session: Session, tenant_id: str) -> list[dict]:
    rows = session.execute(
        select(User, UserTenant).join(UserTenant, UserTenant.user_id == User.id)
        .where(UserTenant.tenant_id == tenant_id).order_by(User.name)
    ).all()
    return [member_dict(u, m) for u, m in rows]


def member_dict(u: User, m: UserTenant) -> dict:
    return {
        "user_id": str(u.id), "email": u.email, "name": u.name, "role": m.role,
        "membership_status": m.status, "user_status": u.status, "mfa_enabled": u.mfa_enabled,
        "must_change_password": u.must_change_password,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


def add_member(
    session: Session, tenant: Tenant, *, email: str, name: str, role: str, by_platform: bool,
) -> CreatedMembership:
    r = _check_role(role, by_platform=by_platform)
    email = normalize_email(email)
    name = (name or "").strip()
    if not 2 <= len(name) <= 120:
        raise UserAdminError("nome deve ter entre 2 e 120 caracteres")
    _checar_limite(session, tenant.id)

    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    senha: str | None = None
    existente = user is not None
    if user is None:
        senha = temporary_password()
        user = User(email=email, name=name, password_hash=hash_password(senha),
                    must_change_password=True, status="ACTIVE")
        session.add(user)
        session.flush()
    elif session.get(UserTenant, (user.id, tenant.id)) is not None:
        raise UserAdminError("usuário já vinculado a este tenant")
    m = UserTenant(user_id=user.id, tenant_id=tenant.id, role=r.value, status="ACTIVE")
    session.add(m)
    session.flush()
    return CreatedMembership(user, m, senha, existente)


def update_member(
    session: Session, tenant_id: str, user_id: uuid.UUID, *, actor_id: uuid.UUID,
    role: str | None, status: str | None, by_platform: bool,
) -> tuple[UserTenant, dict]:
    m = session.get(UserTenant, (user_id, tenant_id))
    if m is None:
        raise LookupError("vínculo não encontrado")
    if user_id == actor_id and not by_platform:
        raise UserAdminForbidden("não é permitido alterar o próprio acesso")
    antes = {"role": m.role, "status": m.status}
    novo_role = _check_role(role, by_platform=by_platform).value if role else m.role
    if status is not None and status not in ("ACTIVE", "INACTIVE"):
        raise UserAdminError("status inválido")
    novo_status = status or m.status
    perde_admin = m.role == "TENANT_ADMIN" and m.status == "ACTIVE" and (
        novo_role != "TENANT_ADMIN" or novo_status != "ACTIVE")
    if perde_admin and not by_platform and _admins_ativos(session, tenant_id) <= 1:
        raise UserAdminError("o tenant precisa manter ao menos um TENANT_ADMIN ativo")
    if novo_status == "ACTIVE" and m.status != "ACTIVE":
        _checar_limite(session, tenant_id)
    m.role, m.status = novo_role, novo_status
    if novo_status != "ACTIVE" or novo_role != antes["role"]:
        # papel/acesso mudou: derruba sessões do usuário NAQUELE tenant
        sessions.revoke_all_for_user_in_tenant(session, user_id, tenant_id, "membership_changed")
    session.flush()
    return m, antes


def is_exclusive_to(session: Session, user: User, tenant_id: str) -> bool:
    if user.platform_role is not None:
        return False
    outros = session.execute(
        select(func.count()).select_from(UserTenant)
        .where(UserTenant.user_id == user.id, UserTenant.tenant_id != tenant_id)
    ).scalar_one()
    return outros == 0


def reset_password(session: Session, user: User) -> str:
    senha = temporary_password()
    user.password_hash = hash_password(senha)
    user.must_change_password = True
    user.token_version += 1
    user.failed_login_count = 0
    user.locked_until = None
    sessions.revoke_all_for_user(session, user.id, "password_reset")
    session.flush()
    return senha


def reset_mfa(session: Session, user: User) -> None:
    user.mfa_enabled = False
    user.mfa_secret_enc = None
    user.mfa_pending_secret_enc = None
    user.mfa_last_used_step = None
    user.token_version += 1
    from app.security import recovery

    recovery.clear(session, user.id)  # códigos de recuperação antigos deixam de valer
    sessions.revoke_all_for_user(session, user.id, "mfa_reset")
    session.flush()


def set_user_status(session: Session, user: User, status: str) -> None:
    if status not in ("ACTIVE", "INACTIVE"):
        raise UserAdminError("status inválido")
    user.status = status
    if status != "ACTIVE":
        user.token_version += 1
        sessions.revoke_all_for_user(session, user.id, "user_deactivated")
    user.updated_at = datetime.now(UTC)
    session.flush()


def user_dict(session: Session, u: User) -> dict:
    vinculos = session.execute(
        select(UserTenant, Tenant.name).join(Tenant, Tenant.id == UserTenant.tenant_id)
        .where(UserTenant.user_id == u.id).order_by(Tenant.name)
    ).all()
    return {
        "id": str(u.id), "email": u.email, "name": u.name, "status": u.status,
        "platform_role": u.platform_role, "mfa_enabled": u.mfa_enabled,
        "must_change_password": u.must_change_password,
        "locked": bool(u.locked_until and u.locked_until > datetime.now(UTC)),
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "memberships": [{"tenant_id": m.tenant_id, "tenant_name": n, "role": m.role,
                         "status": m.status} for m, n in vinculos],
    }
