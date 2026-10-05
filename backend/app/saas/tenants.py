"""Tenants — criação, status, plano e visão consolidada para a administração Works2Data."""

from __future__ import annotations

import re

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Plan, Tenant, UserTenant
from app.saas import branding, features, secrets, settings_catalog
from app.saas import users as users_svc

_CODE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")
STATUS = ("ACTIVE", "SUSPENDED", "INACTIVE")


class TenantError(ValueError):
    pass


def validate_code(code: str) -> str:
    c = (code or "").strip().lower()
    if not _CODE.match(c):
        raise TenantError("código inválido: 3–40 caracteres, a-z, 0-9 e '-' (sem começar/terminar com '-')")
    return c


def create(session: Session, *, code: str, name: str, legal_name: str | None,
           plan_code: str | None, is_synthetic: bool = False) -> Tenant:
    code = validate_code(code)
    if session.get(Tenant, code) is not None:
        raise TenantError("já existe um tenant com este código")
    name = (name or "").strip()
    if not 2 <= len(name) <= 120:
        raise TenantError("nome deve ter entre 2 e 120 caracteres")
    plano = None
    if plan_code:
        plano = session.execute(select(Plan).where(Plan.code == plan_code)).scalar_one_or_none()
        if plano is None:
            raise TenantError("plano inexistente")
    t = Tenant(id=code, name=name, legal_name=(legal_name or None) and legal_name.strip()[:200],
               status="ACTIVE", plan_id=plano.id if plano else None, is_synthetic=is_synthetic)
    session.add(t)
    session.flush()
    return t


def set_status(session: Session, tenant: Tenant, status: str) -> str:
    if status not in STATUS:
        raise TenantError("status inválido")
    anterior = tenant.status
    tenant.status = status
    session.flush()
    return anterior


def set_plan(session: Session, tenant: Tenant, plan_code: str | None) -> tuple[str | None, str | None]:
    anterior = session.get(Plan, tenant.plan_id).code if tenant.plan_id else None
    if plan_code is None:
        tenant.plan_id = None
    else:
        plano = session.execute(select(Plan).where(Plan.code == plan_code)).scalar_one_or_none()
        if plano is None:
            raise TenantError("plano inexistente")
        tenant.plan_id = plano.id
    session.flush()
    return anterior, plan_code


def summary(session: Session, t: Tenant) -> dict:
    plano = session.get(Plan, t.plan_id) if t.plan_id else None
    n_users = session.execute(
        select(func.count()).select_from(UserTenant).where(
            UserTenant.tenant_id == t.id, UserTenant.status == "ACTIVE")
    ).scalar_one()
    return {
        "id": t.id, "code": t.id, "uuid": str(t.uuid), "name": t.name, "legal_name": t.legal_name,
        "status": t.status, "is_synthetic": t.is_synthetic,
        "plan": {"code": plano.code, "name": plano.name} if plano else None,
        "active_users": n_users,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def overview(session: Session, t: Tenant) -> dict:
    """Visão completa para /admin/tenants/{id}: identificação, plano, status, features,
    usuários, branding, configurações, segredos (metadados) e auditoria recente."""
    auditoria = session.execute(
        select(AuditLog).where(AuditLog.tenant_id == t.id).order_by(desc(AuditLog.id)).limit(15)
    ).scalars().all()
    return {
        "tenant": summary(session, t),
        "features": [r.as_dict() for r in features.resolve_all(session, t)],
        "users": users_svc.list_members(session, t.id),
        "branding": {"raw": branding.raw(session, t.id), "effective": branding.effective(session, t)},
        "settings": settings_catalog.describe(session, t.id, editor="platform"),
        "secrets": secrets.list_metadata(session, t.id),
        "recent_audit": [audit_dict(a) for a in auditoria],
    }


def audit_dict(a: AuditLog) -> dict:
    return {
        "id": a.id, "occurred_at": a.occurred_at.isoformat() if a.occurred_at else None,
        "actor_email": a.actor_email, "actor_role": a.actor_role, "tenant_id": a.tenant_id,
        "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
        "outcome": a.outcome, "ip": a.ip, "request_id": a.request_id, "details": a.details,
    }
