"""Identidade de tenant — constantes e erros compartilhados.

Até a v1.2 este módulo guardava um `ContextVar` com default `w2h-demo`, nunca usado pelas
consultas. A partir da Fundação SaaS V1 o tenant efetivo **nunca** tem default: ele vem do
contexto autenticado (JWT → usuário → vínculo → `TenantContext`) e é amarrado à sessão do
banco por `app.db.tenant_scope.bind_tenant`. Sem tenant amarrado, os repositórios levantam
`TenantContextMissing` (fail-closed) e o RLS do PostgreSQL devolve zero linhas.

`DEFAULT_TENANT` permanece apenas como o **código do tenant demonstrativo** da massa
sintética (seed / testes) — não é fallback de nada.
"""

from __future__ import annotations

#: Código (slug) do tenant demonstrativo "Operadora Vida Plena" gerado pelo seed.
DEFAULT_TENANT = "w2h-demo"


class TenantContextMissing(RuntimeError):
    """Operação tenant-scoped executada sem tenant amarrado à sessão (fail-closed)."""
