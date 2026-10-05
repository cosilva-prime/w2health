"""Administração da plataforma Works2Data — `/api/admin/*` (somente SUPER_ADMIN).

Toda mutação grava auditoria NA MESMA transação (`audit.add`) com o ator da plataforma.
Nenhuma rota daqui depende de tenant selecionado: o tenant-alvo vem do caminho e é
validado contra o cadastro — esta é a única área em que um id de tenant enviado pelo
cliente é aceito, e somente para quem tem papel de plataforma.

Promover alguém a SUPER_ADMIN **não** é possível por API (somente CLI com acesso ao banco
— `python -m app.saas.cli create-superadmin`), reduzindo o impacto de uma sessão
administrativa comprometida.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AuditLog, Feature, Plan, PlanFeature, Tenant, TenantFeature, User
from app.saas import audit, branding, secrets, settings_catalog
from app.saas import tenants as tenants_svc
from app.saas import users as users_svc
from app.saas.catalog import FEATURE_KEYS
from app.security import crypto
from app.security.deps import Principal, require_platform
from app.security.errors import ApiError
from app.security.rbac import Perm

router = APIRouter(prefix="/admin", tags=["Administração Works2Data"])

_TENANTS = require_platform(Perm.PLATFORM_TENANTS_MANAGE)
_PLANS = require_platform(Perm.PLATFORM_PLANS_MANAGE)
_FEATURES = require_platform(Perm.PLATFORM_FEATURES_MANAGE)
_USERS = require_platform(Perm.PLATFORM_USERS_MANAGE)
_SECRETS = require_platform(Perm.PLATFORM_SECRETS_MANAGE)
_AUDIT = require_platform(Perm.PLATFORM_AUDIT_READ)


# ============================================================================ schemas
class TenantCreateIn(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    legal_name: str | None = Field(default=None, max_length=200)
    plan_code: str | None = Field(default=None, max_length=40)
    is_synthetic: bool = False


class TenantPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    legal_name: str | None = Field(default=None, max_length=200)


class StatusIn(BaseModel):
    status: str
    reason: str = Field(min_length=3, max_length=300)


class PlanAssignIn(BaseModel):
    plan_code: str | None = Field(default=None, max_length=40)


class FeatureOverrideIn(BaseModel):
    enabled: bool | None  # None = remove o override (volta ao plano)
    reason: str = Field(min_length=3, max_length=300)


class BrandingIn(BaseModel):
    product_name: str | None = Field(default=None, max_length=60)
    primary_color: str | None = Field(default=None, max_length=7)
    accent_color: str | None = Field(default=None, max_length=7)
    login_title: str | None = Field(default=None, max_length=80)
    login_message: str | None = Field(default=None, max_length=300)


class SettingIn(BaseModel):
    value: Any


class SecretIn(BaseModel):
    value: str = Field(min_length=1, max_length=8192)


class MemberIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=2, max_length=120)
    role: str


class MemberPatchIn(BaseModel):
    role: str | None = None
    status: str | None = None


class UserPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    status: str | None = None


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class PlanCreateIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=400)


class PlanPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=400)
    is_active: bool | None = None


class PlanFeatureIn(BaseModel):
    included: bool


class FeaturePatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=400)
    is_active: bool | None = None


# ============================================================================ helpers
def _tenant(db: Session, tenant_id: str) -> Tenant:
    t = db.get(Tenant, tenant_id)
    if t is None:
        raise ApiError("not_found", "Tenant não encontrado.")
    return t


def _user(db: Session, user_id: str) -> User:
    try:
        u = db.get(User, uuid.UUID(user_id))
    except ValueError:
        u = None
    if u is None:
        raise ApiError("not_found", "Usuário não encontrado.")
    return u


def _plan(db: Session, code: str) -> Plan:
    p = db.execute(select(Plan).where(Plan.code == code)).scalar_one_or_none()
    if p is None:
        raise ApiError("not_found", "Plano não encontrado.")
    return p


def _invalid(e: Exception) -> ApiError:
    return ApiError("invalid_request", str(e))


# ============================================================================ tenants
@router.get("/tenants", summary="Lista tenants")
def list_tenants(_p: Principal = Depends(_TENANTS), db: Session = Depends(get_db)) -> dict:
    ts = db.execute(select(Tenant).order_by(Tenant.name)).scalars().all()
    return {"itens": [tenants_svc.summary(db, t) for t in ts]}


@router.post("/tenants", status_code=201, summary="Cria tenant")
def create_tenant(payload: TenantCreateIn, p: Principal = Depends(_TENANTS),
                  db: Session = Depends(get_db)) -> dict:
    try:
        t = tenants_svc.create(db, code=payload.code, name=payload.name,
                               legal_name=payload.legal_name, plan_code=payload.plan_code,
                               is_synthetic=payload.is_synthetic)
    except tenants_svc.TenantError as e:
        raise _invalid(e) from e
    audit.add(db, "tenant.created", actor=p.actor(), tenant_id=t.id, entity_type="tenant",
              entity_id=t.id, details={"plano": payload.plan_code, "sintetico": t.is_synthetic})
    db.commit()
    return tenants_svc.summary(db, t)


@router.get("/tenants/{tenant_id}", summary="Visão completa do tenant")
def get_tenant(tenant_id: str, _p: Principal = Depends(_TENANTS), db: Session = Depends(get_db)) -> dict:
    return tenants_svc.overview(db, _tenant(db, tenant_id))


@router.patch("/tenants/{tenant_id}", summary="Atualiza identificação do tenant")
def patch_tenant(tenant_id: str, payload: TenantPatchIn, p: Principal = Depends(_TENANTS),
                 db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    mudancas = payload.model_dump(exclude_unset=True)
    for k, v in mudancas.items():
        setattr(t, k, v.strip() if isinstance(v, str) else v)
    audit.add(db, "tenant.updated", actor=p.actor(), tenant_id=t.id, entity_type="tenant",
              entity_id=t.id, details={"campos": sorted(mudancas)})
    db.commit()
    return tenants_svc.summary(db, t)


@router.post("/tenants/{tenant_id}/status", summary="Ativa / suspende / inativa o tenant")
def tenant_status(tenant_id: str, payload: StatusIn, p: Principal = Depends(_TENANTS),
                  db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    try:
        anterior = tenants_svc.set_status(db, t, payload.status)
    except tenants_svc.TenantError as e:
        raise _invalid(e) from e
    audit.add(db, "tenant.status_changed", actor=p.actor(), tenant_id=t.id, entity_type="tenant",
              entity_id=t.id, details={"de": anterior, "para": t.status, "motivo": payload.reason})
    db.commit()
    return tenants_svc.summary(db, t)


@router.put("/tenants/{tenant_id}/plan", summary="Associa plano ao tenant")
def tenant_plan(tenant_id: str, payload: PlanAssignIn, p: Principal = Depends(_TENANTS),
                db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    try:
        de, para = tenants_svc.set_plan(db, t, payload.plan_code)
    except tenants_svc.TenantError as e:
        raise _invalid(e) from e
    audit.add(db, "tenant.plan_changed", actor=p.actor(), tenant_id=t.id, entity_type="tenant",
              entity_id=t.id, details={"de": de, "para": para})
    db.commit()
    return tenants_svc.summary(db, t)


@router.put("/tenants/{tenant_id}/features/{feature_key}", summary="Override de feature por tenant")
def tenant_feature(tenant_id: str, feature_key: str, payload: FeatureOverrideIn,
                   p: Principal = Depends(_FEATURES), db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    if db.get(Feature, feature_key) is None:
        raise ApiError("not_found", "Feature não encontrada.")
    ov = db.get(TenantFeature, (t.id, feature_key))
    anterior = None if ov is None else ov.enabled
    if payload.enabled is None:
        if ov is not None:
            db.delete(ov)
    elif ov is None:
        db.add(TenantFeature(tenant_id=t.id, feature_key=feature_key, enabled=payload.enabled,
                             reason=payload.reason, updated_by=p.user_id))
    else:
        ov.enabled, ov.reason, ov.updated_by = payload.enabled, payload.reason, p.user_id
    audit.add(db, "tenant.feature_override", actor=p.actor(), tenant_id=t.id, entity_type="feature",
              entity_id=feature_key, details={"de": anterior, "para": payload.enabled,
                                              "motivo": payload.reason})
    db.commit()
    return tenants_svc.overview(db, t)


# ---------------------------------------------------------------- branding (plataforma)
@router.get("/tenants/{tenant_id}/branding")
def get_branding(tenant_id: str, _p: Principal = Depends(_TENANTS), db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    return {"raw": branding.raw(db, t.id), "effective": branding.effective(db, t),
            "defaults": branding.DEFAULT_BRANDING}


@router.put("/tenants/{tenant_id}/branding")
def put_branding(tenant_id: str, payload: BrandingIn, p: Principal = Depends(_TENANTS),
                 db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    dados = payload.model_dump(exclude_unset=True)
    try:
        novo = branding.update(db, t.id, dados, user_id=p.user_id)
    except branding.BrandingError as e:
        raise _invalid(e) from e
    audit.add(db, "branding.updated", actor=p.actor(), tenant_id=t.id, entity_type="branding",
              entity_id=t.id, details={"campos": sorted(dados)})
    db.commit()
    return {"raw": novo, "effective": branding.effective(db, t)}


@router.post("/tenants/{tenant_id}/branding/{kind}")
async def upload_asset(tenant_id: str, kind: str, file: UploadFile = File(...),
                       p: Principal = Depends(_TENANTS), db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    data = await file.read(branding.MAX_ASSET_BYTES + 1)
    try:
        info = branding.set_asset(db, t.id, kind, data, user_id=p.user_id)
    except branding.BrandingError as e:
        raise _invalid(e) from e
    audit.add(db, "branding.asset_updated", actor=p.actor(), tenant_id=t.id, entity_type="branding",
              entity_id=kind, details={"tamanho": info["size"], "tipo": info["content_type"]})
    db.commit()
    return info


@router.delete("/tenants/{tenant_id}/branding/{kind}", status_code=204, response_model=None)
def delete_asset(tenant_id: str, kind: str, p: Principal = Depends(_TENANTS),
                 db: Session = Depends(get_db)) -> None:
    t = _tenant(db, tenant_id)
    if branding.delete_asset(db, t.id, kind):
        audit.add(db, "branding.asset_removed", actor=p.actor(), tenant_id=t.id,
                  entity_type="branding", entity_id=kind)
        db.commit()


# ---------------------------------------------------------------- configurações
@router.get("/tenants/{tenant_id}/settings")
def get_settings_(tenant_id: str, _p: Principal = Depends(_TENANTS), db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    return {"itens": settings_catalog.describe(db, t.id, editor="platform")}


@router.put("/tenants/{tenant_id}/settings/{key}")
def put_setting(tenant_id: str, key: str, payload: SettingIn, p: Principal = Depends(_TENANTS),
                db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    try:
        de, para = settings_catalog.set_value(db, t.id, key, payload.value, editor="platform",
                                              user_id=p.user_id)
    except settings_catalog.SettingError as e:
        raise _invalid(e) from e
    audit.add(db, "settings.updated", actor=p.actor(), tenant_id=t.id, entity_type="setting",
              entity_id=key, details={"de": de, "para": para})
    db.commit()
    return {"itens": settings_catalog.describe(db, t.id, editor="platform")}


# ---------------------------------------------------------------- segredos (write-only)
@router.get("/tenants/{tenant_id}/secrets", summary="Metadados dos segredos (nunca o valor)")
def list_secrets(tenant_id: str, _p: Principal = Depends(_SECRETS), db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    return {"itens": secrets.list_metadata(db, t.id), "encryption_available": crypto.encryption_available()}


@router.put("/tenants/{tenant_id}/secrets/{key}", summary="Cria/rotaciona segredo (cifrado)")
def put_secret(tenant_id: str, key: str, payload: SecretIn, p: Principal = Depends(_SECRETS),
               db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    try:
        rotacao = secrets.put(db, t.id, key, payload.value, user_id=p.user_id)
    except secrets.SecretError as e:
        raise _invalid(e) from e
    except crypto.EncryptionUnavailable as e:
        raise ApiError("service_unavailable", "Criptografia não configurada (DATA_ENCRYPTION_KEY).") from e
    audit.add(db, "secret.rotated" if rotacao else "secret.created", actor=p.actor(),
              tenant_id=t.id, entity_type="secret", entity_id=key)
    db.commit()
    return {"itens": secrets.list_metadata(db, t.id)}


@router.delete("/tenants/{tenant_id}/secrets/{key}", status_code=204, response_model=None)
def delete_secret(tenant_id: str, key: str, p: Principal = Depends(_SECRETS),
                  db: Session = Depends(get_db)) -> None:
    t = _tenant(db, tenant_id)
    if not secrets.delete(db, t.id, key):
        raise ApiError("not_found")
    audit.add(db, "secret.deleted", actor=p.actor(), tenant_id=t.id, entity_type="secret", entity_id=key)
    db.commit()


# ---------------------------------------------------------------- usuários do tenant
@router.get("/tenants/{tenant_id}/users")
def tenant_users(tenant_id: str, _p: Principal = Depends(_USERS), db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    return {"itens": users_svc.list_members(db, t.id)}


@router.post("/tenants/{tenant_id}/users", status_code=201)
def add_tenant_user(tenant_id: str, payload: MemberIn, p: Principal = Depends(_USERS),
                    db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    try:
        r = users_svc.add_member(db, t, email=payload.email, name=payload.name, role=payload.role,
                                 by_platform=True)
    except users_svc.UserAdminForbidden as e:
        raise ApiError("forbidden", str(e)) from e
    except users_svc.UserAdminError as e:
        raise _invalid(e) from e
    audit.add(db, "user.membership_created", actor=p.actor(), tenant_id=t.id, entity_type="user",
              entity_id=r.user.id, details={"papel": payload.role, "conta_existente": r.existing_account})
    db.commit()
    return {"member": users_svc.member_dict(r.user, r.membership),
            "temporary_password": r.temporary_password, "existing_account": r.existing_account}


@router.patch("/tenants/{tenant_id}/users/{user_id}")
def patch_tenant_user(tenant_id: str, user_id: str, payload: MemberPatchIn,
                      p: Principal = Depends(_USERS), db: Session = Depends(get_db)) -> dict:
    t = _tenant(db, tenant_id)
    u = _user(db, user_id)
    try:
        m, antes = users_svc.update_member(db, t.id, u.id, actor_id=p.user_id, role=payload.role,
                                           status=payload.status, by_platform=True)
    except LookupError as e:
        raise ApiError("not_found", "Vínculo não encontrado.") from e
    except users_svc.UserAdminForbidden as e:
        raise ApiError("forbidden", str(e)) from e
    except users_svc.UserAdminError as e:
        raise _invalid(e) from e
    audit.add(db, "user.membership_changed", actor=p.actor(), tenant_id=t.id, entity_type="user",
              entity_id=u.id, details={"de": antes, "para": {"role": m.role, "status": m.status}})
    db.commit()
    return users_svc.member_dict(u, m)


# ============================================================================ usuários
@router.get("/users", summary="Lista usuários da plataforma")
def list_users(q: str | None = Query(None, max_length=100), _p: Principal = Depends(_USERS),
               db: Session = Depends(get_db)) -> dict:
    stmt = select(User).order_by(User.name).limit(500)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(User.email.like(like), User.name.ilike(like)))
    return {"itens": [users_svc.user_dict(db, u) for u in db.execute(stmt).scalars()]}


@router.get("/users/{user_id}")
def get_user(user_id: str, _p: Principal = Depends(_USERS), db: Session = Depends(get_db)) -> dict:
    return users_svc.user_dict(db, _user(db, user_id))


@router.patch("/users/{user_id}")
def patch_user(user_id: str, payload: UserPatchIn, p: Principal = Depends(_USERS),
               db: Session = Depends(get_db)) -> dict:
    u = _user(db, user_id)
    if u.id == p.user_id and payload.status is not None:
        raise ApiError("forbidden", "Não é permitido alterar o próprio status.")
    antes = {"name": u.name, "status": u.status}
    if payload.name is not None:
        u.name = payload.name.strip()
    if payload.status is not None:
        try:
            users_svc.set_user_status(db, u, payload.status)
        except users_svc.UserAdminError as e:
            raise _invalid(e) from e
    audit.add(db, "user.updated", actor=p.actor(), entity_type="user", entity_id=u.id,
              details={"de": antes, "para": {"name": u.name, "status": u.status}})
    db.commit()
    return users_svc.user_dict(db, u)


@router.post("/users/{user_id}/reset-password", summary="Gera senha temporária (exibida uma vez)")
def reset_password(user_id: str, payload: ReasonIn, p: Principal = Depends(_USERS),
                   db: Session = Depends(get_db)) -> dict:
    u = _user(db, user_id)
    if u.id == p.user_id:
        raise ApiError("forbidden", "Use a troca de senha da própria conta.")
    senha = users_svc.reset_password(db, u)
    audit.add(db, "user.password_reset", actor=p.actor(), entity_type="user", entity_id=u.id,
              details={"motivo": payload.reason})
    db.commit()
    return {"temporary_password": senha}


@router.post("/users/{user_id}/reset-mfa", summary="Reset administrativo de MFA (auditado)")
def reset_mfa(user_id: str, payload: ReasonIn, p: Principal = Depends(_USERS),
              db: Session = Depends(get_db)) -> dict:
    u = _user(db, user_id)
    if u.id == p.user_id:
        raise ApiError("forbidden", "Reset de MFA da própria conta deve ser feito por outro administrador.")
    users_svc.reset_mfa(db, u)
    audit.add(db, "mfa.admin_reset", actor=p.actor(), entity_type="user", entity_id=u.id,
              details={"motivo": payload.reason})
    db.commit()
    return users_svc.user_dict(db, u)


# ============================================================================ planos
def _plans_matrix(db: Session) -> dict:
    planos = db.execute(select(Plan).order_by(Plan.sort_order, Plan.code)).scalars().all()
    feats = db.execute(select(Feature).order_by(Feature.sort_order, Feature.key)).scalars().all()
    inclusoes = {(pf.plan_id, pf.feature_key) for pf in db.execute(select(PlanFeature)).scalars()}
    return {
        "plans": [{"code": p.code, "name": p.name, "description": p.description,
                   "is_active": p.is_active,
                   "features": [f.key for f in feats if (p.id, f.key) in inclusoes]} for p in planos],
        "features": [{"key": f.key, "name": f.name, "module": f.module, "is_active": f.is_active}
                     for f in feats],
    }


@router.get("/plans", summary="Planos + matriz de features (configurável)")
def list_plans(_p: Principal = Depends(_PLANS), db: Session = Depends(get_db)) -> dict:
    return _plans_matrix(db)


@router.post("/plans", status_code=201)
def create_plan(payload: PlanCreateIn, p: Principal = Depends(_PLANS), db: Session = Depends(get_db)) -> dict:
    if db.execute(select(Plan).where(Plan.code == payload.code)).scalar_one_or_none():
        raise ApiError("conflict", "Já existe um plano com este código.")
    db.add(Plan(code=payload.code, name=payload.name, description=payload.description,
                sort_order=100))
    audit.add(db, "plan.created", actor=p.actor(), entity_type="plan", entity_id=payload.code)
    db.commit()
    return _plans_matrix(db)


@router.patch("/plans/{code}")
def patch_plan(code: str, payload: PlanPatchIn, p: Principal = Depends(_PLANS),
               db: Session = Depends(get_db)) -> dict:
    plano = _plan(db, code)
    mudancas = payload.model_dump(exclude_unset=True)
    for k, v in mudancas.items():
        setattr(plano, k, v)
    audit.add(db, "plan.updated", actor=p.actor(), entity_type="plan", entity_id=code,
              details=mudancas)
    db.commit()
    return _plans_matrix(db)


@router.put("/plans/{code}/features/{feature_key}")
def plan_feature(code: str, feature_key: str, payload: PlanFeatureIn,
                 p: Principal = Depends(_PLANS), db: Session = Depends(get_db)) -> dict:
    plano = _plan(db, code)
    if db.get(Feature, feature_key) is None:
        raise ApiError("not_found", "Feature não encontrada.")
    atual = db.get(PlanFeature, (plano.id, feature_key))
    if payload.included and atual is None:
        db.add(PlanFeature(plan_id=plano.id, feature_key=feature_key))
    elif not payload.included and atual is not None:
        db.delete(atual)
    audit.add(db, "plan.feature_changed", actor=p.actor(), entity_type="plan", entity_id=code,
              details={"feature": feature_key, "incluida": payload.included})
    db.commit()
    return _plans_matrix(db)


# ============================================================================ features
@router.get("/features", summary="Catálogo de features (kill switch global)")
def list_features(_p: Principal = Depends(_FEATURES), db: Session = Depends(get_db)) -> dict:
    feats = db.execute(select(Feature).order_by(Feature.sort_order, Feature.key)).scalars().all()
    return {"itens": [{"key": f.key, "name": f.name, "description": f.description,
                       "module": f.module, "is_active": f.is_active,
                       "implemented": f.key in FEATURE_KEYS} for f in feats]}


@router.patch("/features/{feature_key}")
def patch_feature(feature_key: str, payload: FeaturePatchIn, p: Principal = Depends(_FEATURES),
                  db: Session = Depends(get_db)) -> dict:
    f = db.get(Feature, feature_key)
    if f is None:
        raise ApiError("not_found", "Feature não encontrada.")
    mudancas = payload.model_dump(exclude_unset=True)
    for k, v in mudancas.items():
        setattr(f, k, v)
    audit.add(db, "feature.updated", actor=p.actor(), entity_type="feature", entity_id=feature_key,
              details=mudancas)
    db.commit()
    return list_features(p, db)


# ============================================================================ auditoria
@router.get("/audit", summary="Trilha de auditoria da plataforma")
def list_audit(
    tenant_id: str | None = Query(None, max_length=40),
    action: str | None = Query(None, max_length=60),
    outcome: str | None = Query(None, max_length=10),
    before_id: int | None = Query(None, ge=1),
    limit: int = Query(100, ge=1, le=500),
    _p: Principal = Depends(_AUDIT), db: Session = Depends(get_db),
) -> dict:
    stmt = select(AuditLog).order_by(desc(AuditLog.id)).limit(limit)
    if tenant_id:
        stmt = stmt.where(AuditLog.tenant_id == tenant_id)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    if outcome:
        stmt = stmt.where(AuditLog.outcome == outcome)
    if before_id:
        stmt = stmt.where(AuditLog.id < before_id)
    return {"itens": [tenants_svc.audit_dict(a) for a in db.execute(stmt).scalars()]}
