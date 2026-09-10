"""Mixins compartilhados pelos modelos ORM.

`TenantMixin` — adiciona `tenant_id` a toda tabela que guarda dado de um cliente
(v1.2, fundação SaaS). O único modelo persistido que NÃO usa este mixin é
`Competencia` (calendário global, não pertence a nenhum cliente). Ver
`docs/MULTI_TENANCY.md`.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.tenant import DEFAULT_TENANT


class TenantMixin:
    """Coluna `tenant_id` (slug do cliente). NOT NULL, indexada.

    `server_default=DEFAULT_TENANT` permite adicionar a coluna a tabelas já populadas
    (migration preparatória) e manter o seed atual funcionando sem carimbar cada linha
    manualmente — mas o seed **carimba explicitamente** mesmo assim, para deixar claro
    a que tenant a massa sintética pertence.
    """

    tenant_id: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=DEFAULT_TENANT, index=True
    )
