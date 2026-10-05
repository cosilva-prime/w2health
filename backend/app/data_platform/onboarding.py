"""Onboarding técnico do tenant — estado persistido (`tenant_onboarding`) + serviços.

Sequência (docs/CLIENT_ONBOARDING.md):

    TENANT_CREATED → SOURCE_REGISTERED → CONNECTION_VALIDATED → RAW_LOADED →
    MAPPING_VALIDATED → DATA_QUALITY_VALIDATED → SILVER_READY → GOLD_READY → RECONCILED →
    CAPABILITIES_READY → HOMOLOGATED → ACTIVE

* Estados até CAPABILITIES_READY avançam AUTOMATICAMENTE pelo pipeline (só para frente).
* HOMOLOGATED e ACTIVE são decisões humanas (SUPER_ADMIN), auditadas.
* Não há workflow engine: é um estado + histórico.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import TenantOnboarding
from app.models.saas import ONBOARDING_STATES

AUTOMATIC = ONBOARDING_STATES[:10]  # até CAPABILITIES_READY
MANUAL = ("HOMOLOGATED", "ACTIVE")


class OnboardingError(ValueError):
    pass


def _idx(state: str) -> int:
    return ONBOARDING_STATES.index(state)


def get(session: Session, tenant_id: str) -> TenantOnboarding:
    ob = session.get(TenantOnboarding, tenant_id)
    if ob is None:
        ob = TenantOnboarding(tenant_id=tenant_id, state="TENANT_CREATED",
                              history=[{"state": "TENANT_CREATED", "at": datetime.now(UTC).isoformat(),
                                        "by": "system"}])
        session.add(ob)
        session.flush()
    return ob


def advance(session: Session, tenant_id: str, state: str, *, by: str, note: str = "") -> TenantOnboarding:
    """Avança automaticamente (nunca retrocede; ignora se já está além)."""
    if state not in AUTOMATIC:
        raise OnboardingError("estado não é automático")
    ob = get(session, tenant_id)
    if _idx(state) > _idx(ob.state):
        ob.state = state
        ob.history = [*(ob.history or []), {"state": state, "at": datetime.now(UTC).isoformat(),
                                            "by": by, "note": note[:200]}]
        session.flush()
    return ob


def decide(session: Session, tenant_id: str, state: str, *, by: str, note: str) -> TenantOnboarding:
    """Decisão humana: HOMOLOGATED exige CAPABILITIES_READY; ACTIVE exige HOMOLOGATED."""
    if state not in MANUAL:
        raise OnboardingError("somente HOMOLOGATED ou ACTIVE são decisões manuais")
    ob = get(session, tenant_id)
    exigido = "CAPABILITIES_READY" if state == "HOMOLOGATED" else "HOMOLOGATED"
    if _idx(ob.state) < _idx(exigido):
        raise OnboardingError(f"estado atual {ob.state} não permite {state} (exige {exigido})")
    ob.state = state
    ob.history = [*(ob.history or []), {"state": state, "at": datetime.now(UTC).isoformat(),
                                        "by": by, "note": note[:200]}]
    session.flush()
    return ob


def as_dict(ob: TenantOnboarding) -> dict:
    atual = _idx(ob.state)
    return {
        "state": ob.state,
        "steps": [{"state": s, "done": i <= atual, "manual": s in MANUAL}
                  for i, s in enumerate(ONBOARDING_STATES)],
        "history": ob.history or [],
    }
