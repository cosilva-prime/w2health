"""Contexto de tenant (cliente/operadora) — abstração preparatória para o SaaS (v1.2).

O W2Health v1.2 introduz `tenant_id` em **todas** as tabelas persistidas, mas ainda opera
como um único tenant: a massa sintética e as consultas do repositório usam o tenant
padrão `w2h-demo`. Este módulo é o **ponto único** onde, na Fase 2 (multi-tenant real),
o tenant do request (via JWT/domínio/cabeçalho) passará a ser resolvido e propagado —
junto com Row-Level Security no PostgreSQL. Nenhuma consulta analítica atual filtra por
`tenant_id`; isso está documentado como dívida em `docs/MULTI_TENANCY.md` e `docs/V1.2.md`.
"""

from __future__ import annotations

from contextvars import ContextVar

#: Tenant usado por toda a massa sintética e por todas as consultas single-tenant da v1.2.
DEFAULT_TENANT = "w2h-demo"

_tenant_atual: ContextVar[str] = ContextVar("tenant_atual", default=DEFAULT_TENANT)


def current_tenant() -> str:
    """Tenant do contexto atual. Hoje sempre `DEFAULT_TENANT` (single-tenant).

    Fase 2: um middleware do FastAPI fará `set_tenant(...)` por request a partir da
    identidade autenticada, e o repositório passará a aplicar `WHERE tenant_id = :t`.
    """
    return _tenant_atual.get()


def set_tenant(tenant_id: str) -> None:
    """Define o tenant do contexto atual (usado por scripts/testes; Fase 2: middleware)."""
    _tenant_atual.set(tenant_id)
