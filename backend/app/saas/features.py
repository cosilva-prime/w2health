"""Resolução de features por tenant — o ÚNICO lugar que decide se uma capability vale.

Ordem (docs/FEATURE_CATALOG.md):

    1. Feature global ativa?            não → DESABILITADA (kill switch vale para todos)
    2. Há override explícito do tenant? sim → valor do override
    3. O plano do tenant inclui?        sim → HABILITADA
    4. caso contrário                   → DESABILITADA

Nenhum código chama isto com o nome do plano; o plano é só a origem padrão.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Feature, Plan, PlanFeature, Tenant, TenantFeature


@dataclass(frozen=True)
class FeatureResolution:
    key: str
    name: str
    enabled: bool
    source: str  # global_disabled | tenant_override | plan | not_in_plan | no_plan
    override: bool | None
    in_plan: bool
    global_active: bool
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "key": self.key, "name": self.name, "enabled": self.enabled, "source": self.source,
            "override": self.override, "in_plan": self.in_plan,
            "global_active": self.global_active, "reason": self.reason,
        }


def resolve_all(session: Session, tenant: Tenant) -> list[FeatureResolution]:
    features = session.execute(
        select(Feature).order_by(Feature.sort_order, Feature.key)
    ).scalars().all()
    overrides = {
        o.feature_key: o
        for o in session.execute(
            select(TenantFeature).where(TenantFeature.tenant_id == tenant.id)
        ).scalars()
    }
    plano_ativo = False
    no_plano: set[str] = set()
    if tenant.plan_id is not None:
        plano = session.get(Plan, tenant.plan_id)
        plano_ativo = bool(plano and plano.is_active)
        if plano_ativo:
            no_plano = set(
                session.execute(
                    select(PlanFeature.feature_key).where(PlanFeature.plan_id == tenant.plan_id)
                ).scalars()
            )

    out: list[FeatureResolution] = []
    for f in features:
        ov = overrides.get(f.key)
        in_plan = f.key in no_plano
        if not f.is_active:
            enabled, source = False, "global_disabled"
        elif ov is not None:
            enabled, source = bool(ov.enabled), "tenant_override"
        elif in_plan:
            enabled, source = True, "plan"
        else:
            enabled, source = False, "not_in_plan" if plano_ativo else "no_plan"
        out.append(FeatureResolution(
            key=f.key, name=f.name, enabled=enabled, source=source,
            override=None if ov is None else bool(ov.enabled), in_plan=in_plan,
            global_active=f.is_active, reason=ov.reason if ov is not None else "",
        ))
    return out


def enabled_features(session: Session, tenant: Tenant) -> frozenset[str]:
    return frozenset(r.key for r in resolve_all(session, tenant) if r.enabled)


def has_feature(session: Session, tenant: Tenant, feature_key: str) -> bool:
    return feature_key in enabled_features(session, tenant)
