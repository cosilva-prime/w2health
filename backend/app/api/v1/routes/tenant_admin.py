"""Administração do PRÓPRIO tenant — `/api/tenant/*` (TENANT_ADMIN; SUPER_ADMIN em acesso
explícito também passa).

Confinamento: o tenant é SEMPRE `ctx.tenant_id` (do contexto autenticado). Não existe
parâmetro de tenant nestas rotas. O que um TENANT_ADMIN **não** pode, por construção:
trocar o próprio plano, habilitar feature não contratada, acessar outro tenant, atribuir
SUPER_ADMIN, editar limites contratuais, ver/gravar segredos.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AuditLog, Plan, Tenant, User, UserTenant
from app.saas import audit, branding, settings_catalog
from app.saas import tenants as tenants_svc
from app.saas import users as users_svc
from app.saas.features import resolve_all
from app.security.deps import TenantContext, require_feature, require_permission
from app.security.errors import ApiError
from app.security.rbac import Perm

router = APIRouter(prefix="/tenant", tags=["Administração do tenant"])


class MemberIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=2, max_length=120)
    role: str


class MemberPatchIn(BaseModel):
    role: str | None = None
    status: str | None = None


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class BrandingIn(BaseModel):
    product_name: str | None = Field(default=None, max_length=60)
    primary_color: str | None = Field(default=None, max_length=7)
    accent_color: str | None = Field(default=None, max_length=7)
    login_title: str | None = Field(default=None, max_length=80)
    login_message: str | None = Field(default=None, max_length=300)


class SettingIn(BaseModel):
    value: Any


def _editor(ctx: TenantContext) -> str:
    return "platform" if ctx.principal.is_super_admin else "tenant_admin"


# =========================================================================== ambiente
@router.get("/overview", summary="Informações do ambiente (tenant, plano, features, usuários)")
def overview(ctx: TenantContext = Depends(require_permission(Perm.TENANT_USERS_READ)),
             db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, ctx.tenant_id)
    plano = db.get(Plan, t.plan_id) if t.plan_id else None
    return {
        "tenant": {"id": t.id, "name": t.name, "legal_name": t.legal_name, "status": t.status,
                   "is_synthetic": t.is_synthetic,
                   "created_at": t.created_at.isoformat() if t.created_at else None},
        "plan": {"code": plano.code, "name": plano.name} if plano else None,
        "features": [{"key": r.key, "name": r.name, "enabled": r.enabled} for r in resolve_all(db, t)],
        "active_users": users_svc.active_members(db, t.id),
        "limits": {"max_users": settings_catalog.get_value(db, t.id, "limits.max_users"),
                   "max_alert_rules": settings_catalog.get_value(db, t.id, "limits.max_alert_rules")},
    }


# =========================================================================== usuários
@router.get("/users")
def list_users(ctx: TenantContext = Depends(require_permission(Perm.TENANT_USERS_READ)),
               db: Session = Depends(get_db)) -> dict:
    return {"itens": users_svc.list_members(db, ctx.tenant_id)}


@router.post("/users", status_code=201)
def add_user(payload: MemberIn, ctx: TenantContext = Depends(require_permission(Perm.TENANT_USERS_MANAGE)),
             db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, ctx.tenant_id)
    try:
        r = users_svc.add_member(db, t, email=payload.email, name=payload.name, role=payload.role,
                                 by_platform=ctx.principal.is_super_admin)
    except users_svc.UserAdminForbidden as e:
        audit.record_independent(db.get_bind(), "access.denied", actor=ctx.actor,
                                 tenant_id=ctx.tenant_id, outcome="denied",
                                 details={"motivo": "papel_nao_atribuivel", "papel": payload.role})
        raise ApiError("forbidden", "Papel não pode ser atribuído pela administração do tenant.") from e
    except users_svc.UserAdminError as e:
        raise ApiError("invalid_request", str(e)) from e
    audit.add(db, "user.membership_created", actor=ctx.actor, tenant_id=ctx.tenant_id,
              entity_type="user", entity_id=r.user.id,
              details={"papel": payload.role, "conta_existente": r.existing_account})
    db.commit()
    return {"member": users_svc.member_dict(r.user, r.membership),
            "temporary_password": r.temporary_password, "existing_account": r.existing_account}


def _membro(db: Session, ctx: TenantContext, user_id: str) -> User:
    try:
        u = db.get(User, uuid.UUID(user_id))
    except ValueError:
        u = None
    # usuário de outro tenant é indistinguível de inexistente (sem IDOR/enumeração)
    if u is None or db.get(UserTenant, (u.id, ctx.tenant_id)) is None:
        raise ApiError("not_found", "Usuário não encontrado.")
    return u


@router.patch("/users/{user_id}")
def patch_user(user_id: str, payload: MemberPatchIn,
               ctx: TenantContext = Depends(require_permission(Perm.TENANT_USERS_MANAGE)),
               db: Session = Depends(get_db)) -> dict:
    u = _membro(db, ctx, user_id)
    try:
        m, antes = users_svc.update_member(db, ctx.tenant_id, u.id, actor_id=ctx.principal.user_id,
                                           role=payload.role, status=payload.status,
                                           by_platform=ctx.principal.is_super_admin)
    except users_svc.UserAdminForbidden as e:
        audit.record_independent(db.get_bind(), "access.denied", actor=ctx.actor,
                                 tenant_id=ctx.tenant_id, outcome="denied",
                                 details={"motivo": str(e), "alvo": str(u.id)})
        raise ApiError("forbidden", str(e)) from e
    except users_svc.UserAdminError as e:
        raise ApiError("invalid_request", str(e)) from e
    audit.add(db, "user.membership_changed", actor=ctx.actor, tenant_id=ctx.tenant_id,
              entity_type="user", entity_id=u.id,
              details={"de": antes, "para": {"role": m.role, "status": m.status}})
    db.commit()
    return users_svc.member_dict(u, m)


def _exclusivo(db: Session, ctx: TenantContext, u: User) -> None:
    if u.id == ctx.principal.user_id:
        raise ApiError("forbidden", "Use as opções da sua própria conta.")
    if not ctx.principal.is_super_admin and not users_svc.is_exclusive_to(db, u, ctx.tenant_id):
        raise ApiError("forbidden", "Esta conta é gerenciada pela Works2Data. Abra um chamado.")


@router.post("/users/{user_id}/reset-password", summary="Senha temporária (conta exclusiva do tenant)")
def reset_password(user_id: str, payload: ReasonIn,
                   ctx: TenantContext = Depends(require_permission(Perm.TENANT_USERS_MANAGE)),
                   db: Session = Depends(get_db)) -> dict:
    u = _membro(db, ctx, user_id)
    _exclusivo(db, ctx, u)
    senha = users_svc.reset_password(db, u)
    audit.add(db, "user.password_reset", actor=ctx.actor, tenant_id=ctx.tenant_id,
              entity_type="user", entity_id=u.id, details={"motivo": payload.reason})
    db.commit()
    return {"temporary_password": senha}


@router.post("/users/{user_id}/reset-mfa", summary="Reset de MFA (conta exclusiva do tenant, auditado)")
def reset_mfa(user_id: str, payload: ReasonIn,
              ctx: TenantContext = Depends(require_permission(Perm.TENANT_USERS_MANAGE)),
              db: Session = Depends(get_db)) -> dict:
    u = _membro(db, ctx, user_id)
    _exclusivo(db, ctx, u)
    users_svc.reset_mfa(db, u)
    audit.add(db, "mfa.admin_reset", actor=ctx.actor, tenant_id=ctx.tenant_id,
              entity_type="user", entity_id=u.id, details={"motivo": payload.reason})
    db.commit()
    return {"status": "ok"}


# =========================================================================== branding
_BRANDING = (require_permission(Perm.TENANT_BRANDING_MANAGE), require_feature("custom_branding"))


@router.get("/branding")
def get_branding(ctx: TenantContext = Depends(_BRANDING[0]), _f: TenantContext = Depends(_BRANDING[1]),
                 db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, ctx.tenant_id)
    return {"raw": branding.raw(db, t.id), "effective": branding.effective(db, t),
            "defaults": branding.DEFAULT_BRANDING}


@router.put("/branding")
def put_branding(payload: BrandingIn, ctx: TenantContext = Depends(_BRANDING[0]),
                 _f: TenantContext = Depends(_BRANDING[1]), db: Session = Depends(get_db)) -> dict:
    dados = payload.model_dump(exclude_unset=True)
    try:
        novo = branding.update(db, ctx.tenant_id, dados, user_id=ctx.principal.user_id)
    except branding.BrandingError as e:
        raise ApiError("invalid_request", str(e)) from e
    audit.add(db, "branding.updated", actor=ctx.actor, tenant_id=ctx.tenant_id,
              entity_type="branding", entity_id=ctx.tenant_id, details={"campos": sorted(dados)})
    db.commit()
    return {"raw": novo, "effective": branding.effective(db, db.get(Tenant, ctx.tenant_id))}


@router.post("/branding/{kind}")
async def upload_asset(kind: str, file: UploadFile = File(...),
                       ctx: TenantContext = Depends(_BRANDING[0]),
                       _f: TenantContext = Depends(_BRANDING[1]), db: Session = Depends(get_db)) -> dict:
    data = await file.read(branding.MAX_ASSET_BYTES + 1)
    try:
        info = branding.set_asset(db, ctx.tenant_id, kind, data, user_id=ctx.principal.user_id)
    except branding.BrandingError as e:
        raise ApiError("invalid_request", str(e)) from e
    audit.add(db, "branding.asset_updated", actor=ctx.actor, tenant_id=ctx.tenant_id,
              entity_type="branding", entity_id=kind,
              details={"tamanho": info["size"], "tipo": info["content_type"]})
    db.commit()
    return info


@router.delete("/branding/{kind}", status_code=204, response_model=None)
def delete_asset(kind: str, ctx: TenantContext = Depends(_BRANDING[0]),
                 _f: TenantContext = Depends(_BRANDING[1]), db: Session = Depends(get_db)) -> None:
    if branding.delete_asset(db, ctx.tenant_id, kind):
        audit.add(db, "branding.asset_removed", actor=ctx.actor, tenant_id=ctx.tenant_id,
                  entity_type="branding", entity_id=kind)
        db.commit()


# ====================================================================== configurações
@router.get("/settings")
def get_settings_(ctx: TenantContext = Depends(require_permission(Perm.TENANT_SETTINGS_READ)),
                  db: Session = Depends(get_db)) -> dict:
    return {"itens": settings_catalog.describe(db, ctx.tenant_id, editor=_editor(ctx))}


@router.put("/settings/{key}")
def put_setting(key: str, payload: SettingIn,
                ctx: TenantContext = Depends(require_permission(Perm.TENANT_SETTINGS_MANAGE)),
                db: Session = Depends(get_db)) -> dict:
    try:
        de, para = settings_catalog.set_value(db, ctx.tenant_id, key, payload.value,
                                              editor=_editor(ctx), user_id=ctx.principal.user_id)
    except PermissionError as e:
        audit.record_independent(db.get_bind(), "access.denied", actor=ctx.actor,
                                 tenant_id=ctx.tenant_id, outcome="denied",
                                 details={"motivo": "configuracao_de_plataforma", "chave": key})
        raise ApiError("forbidden", "Configuração reservada à Works2Data.") from e
    except settings_catalog.SettingError as e:
        raise ApiError("invalid_request", str(e)) from e
    audit.add(db, "settings.updated", actor=ctx.actor, tenant_id=ctx.tenant_id,
              entity_type="setting", entity_id=key, details={"de": de, "para": para})
    db.commit()
    return {"itens": settings_catalog.describe(db, ctx.tenant_id, editor=_editor(ctx))}


# ========================================================================== auditoria
@router.get("/audit", summary="Auditoria do próprio tenant")
def list_audit(
    action: str | None = Query(None, max_length=60),
    before_id: int | None = Query(None, ge=1),
    limit: int = Query(100, ge=1, le=500),
    ctx: TenantContext = Depends(require_permission(Perm.TENANT_AUDIT_READ)),
    db: Session = Depends(get_db),
) -> dict:
    stmt = (select(AuditLog).where(AuditLog.tenant_id == ctx.tenant_id)
            .order_by(desc(AuditLog.id)).limit(limit))
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    if before_id:
        stmt = stmt.where(AuditLog.id < before_id)
    return {"itens": [tenants_svc.audit_dict(a) for a in db.execute(stmt).scalars()]}
