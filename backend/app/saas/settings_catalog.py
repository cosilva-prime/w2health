"""Configurações FUNCIONAIS por tenant — catálogo fechado e validado.

Separação obrigatória (docs/SECURITY_AND_TENANT_ISOLATION.md):
* **configuração funcional** → `tenant_settings` (JSON, legível, validado por este catálogo);
* **segredo/credencial**     → `tenant_secrets` (cifrado, write-only) — `app/saas/secrets.py`.

Só existem chaves que o código usa de fato. Cada uma declara quem pode editar:
`tenant_admin` (o próprio cliente) ou `platform` (somente SUPER_ADMIN — ex.: limites
contratuais). Chave fora do catálogo é rejeitada (sem configuração "livre").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.periodo import COMPARACOES
from app.models import TenantSetting

Editor = Literal["tenant_admin", "platform"]


@dataclass(frozen=True)
class SettingDef:
    key: str
    label: str
    description: str
    category: str
    adapter: TypeAdapter
    default: Any
    editable_by: Editor
    # exposto ao frontend de qualquer usuário do tenant (preferência de exibição)
    public: bool = False


SETTINGS: dict[str, SettingDef] = {
    d.key: d
    for d in (
        SettingDef(
            "analysis.default_comparison", "Comparação padrão",
            "Base de comparação aplicada quando o usuário não escolhe outra.",
            "Análise", TypeAdapter(Literal[COMPARACOES]),  # type: ignore[valid-type]
            "mes_anterior", "tenant_admin", public=True,
        ),
        SettingDef(
            "security.require_mfa", "Exigir MFA de todos os usuários",
            "Usuários sem MFA são obrigados a configurá-lo no próximo login.",
            "Segurança", TypeAdapter(bool), False, "tenant_admin",
        ),
        SettingDef(
            "limits.max_users", "Limite de usuários ativos",
            "Quantidade máxima de vínculos ativos no tenant (contratual).",
            "Limites", TypeAdapter(int), 50, "platform",
        ),
        SettingDef(
            "limits.max_alert_rules", "Limite de regras de alerta",
            "Quantidade máxima de regras de alerta cadastradas.",
            "Limites", TypeAdapter(int), 100, "platform",
        ),
    )
}

_LIMITES = {"limits.max_users": (1, 10_000), "limits.max_alert_rules": (1, 1_000)}


class SettingError(ValueError):
    pass


def validate(key: str, value: Any) -> Any:
    d = SETTINGS.get(key)
    if d is None:
        raise SettingError("configuração desconhecida")
    try:
        v = d.adapter.validate_python(value, strict=True)
    except ValidationError as e:
        raise SettingError("valor inválido para esta configuração") from e
    if key in _LIMITES:
        lo, hi = _LIMITES[key]
        if not lo <= v <= hi:
            raise SettingError(f"valor deve estar entre {lo} e {hi}")
    return v


def get_value(session: Session, tenant_id: str, key: str) -> Any:
    d = SETTINGS[key]
    row = session.get(TenantSetting, (tenant_id, key))
    return d.default if row is None else row.value.get("v", d.default)


def all_values(session: Session, tenant_id: str) -> dict[str, Any]:
    rows = {
        r.key: r for r in session.execute(
            select(TenantSetting).where(TenantSetting.tenant_id == tenant_id)
        ).scalars()
    }
    return {k: (rows[k].value.get("v", d.default) if k in rows else d.default)
            for k, d in SETTINGS.items()}


def describe(session: Session, tenant_id: str, *, editor: Editor) -> list[dict]:
    valores = all_values(session, tenant_id)
    return [
        {
            "key": d.key, "label": d.label, "description": d.description,
            "category": d.category, "value": valores[d.key], "default": d.default,
            "editable": editor == "platform" or d.editable_by == editor,
            "editable_by": d.editable_by,
        }
        for d in SETTINGS.values()
    ]


def set_value(session: Session, tenant_id: str, key: str, value: Any, *, editor: Editor,
              user_id=None) -> tuple[Any, Any]:
    """Grava (validado). Retorna (anterior, novo). Não faz commit."""
    d = SETTINGS.get(key)
    if d is None:
        raise SettingError("configuração desconhecida")
    if editor != "platform" and d.editable_by != editor:
        raise PermissionError("configuração reservada à plataforma")
    novo = validate(key, value)
    anterior = get_value(session, tenant_id, key)
    row = session.get(TenantSetting, (tenant_id, key))
    if row is None:
        session.add(TenantSetting(tenant_id=tenant_id, key=key, value={"v": novo}, updated_by=user_id))
    else:
        row.value = {"v": novo}
        row.updated_by = user_id
    session.flush()
    return anterior, novo


def public_values(session: Session, tenant_id: str) -> dict[str, Any]:
    valores = all_values(session, tenant_id)
    return {k: v for k, v in valores.items() if SETTINGS[k].public}
