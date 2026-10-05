"""Mixins compartilhados pelos modelos ORM.

`TenantMixin` — adiciona `tenant_id` a toda tabela do **data plane** (dado de operadora).
O único modelo do data plane que NÃO usa este mixin é `Competencia` (calendário global).
Ver `docs/MULTI_TENANCY.md` e `docs/SECURITY_AND_TENANT_ISOLATION.md`.

Fundação SaaS V1: a coluna **não tem mais `server_default`**. Um INSERT sem tenant falha
(NOT NULL) em vez de cair silenciosamente no tenant demonstrativo — e, para o papel de
runtime, a política de RLS (`WITH CHECK`) também rejeita tenant diferente do contexto.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class TenantMixin:
    """Coluna `tenant_id` (código/slug do tenant). NOT NULL, indexada, sem default."""

    tenant_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
