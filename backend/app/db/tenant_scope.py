"""Amarração de tenant à sessão do banco — o elo entre `TenantContext` e o PostgreSQL.

Duas camadas, um único ponto de entrada (`bind_tenant`):

1. **Aplicação** — `session.info[TENANT_INFO_KEY]` guarda o tenant. Todo repositório de
   dados chama `tenant_of(session)`, que levanta `TenantContextMissing` se nada foi
   amarrado (fail-closed: sem tenant válido, sem dado).
2. **Banco (RLS)** — a cada transação aberta pela sessão, o listener `after_begin` executa
   `set_config('app.tenant_id', <tenant>, true)`. O `true` torna o valor LOCAL à transação:
   ele morre no COMMIT/ROLLBACK e nunca vaza para a próxima requisição que reutilizar a
   conexão do pool. Sessões sem tenant gravam `''` — que não casa com nenhuma política.

Uma sessão nunca troca de tenant: tentar amarrar um segundo tenant diferente é erro de
programação (evita misturar contextos dentro da mesma unidade de trabalho).
"""

from __future__ import annotations

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.core.tenant import TenantContextMissing

TENANT_INFO_KEY = "w2h_tenant_id"
#: Nome do parâmetro de sessão lido pelas políticas de RLS.
PG_TENANT_SETTING = "app.tenant_id"

_SET_TENANT_SQL = text(f"SELECT set_config('{PG_TENANT_SETTING}', :tid, true)")


def bind_tenant(session: Session, tenant_id: str) -> None:
    """Amarra `tenant_id` à sessão (aplicação + transação corrente do banco)."""
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise TenantContextMissing("tenant inválido para amarração de sessão")
    atual = session.info.get(TENANT_INFO_KEY)
    if atual is not None and atual != tenant_id:
        raise TenantContextMissing("sessão já amarrada a outro tenant")
    session.info[TENANT_INFO_KEY] = tenant_id
    if session.in_transaction():
        # transação já aberta (ex.: leitura do usuário durante a autenticação)
        session.connection().execute(_SET_TENANT_SQL, {"tid": tenant_id})


def tenant_of(session: Session) -> str:
    """Tenant amarrado à sessão. Fail-closed: levanta se ausente."""
    tid = session.info.get(TENANT_INFO_KEY)
    if not tid:
        raise TenantContextMissing("operação de dados sem tenant no contexto")
    return tid


def bound_tenant(session: Session) -> str | None:
    """Tenant amarrado, ou None — para código que só quer saber (não consultar dados)."""
    return session.info.get(TENANT_INFO_KEY)


@event.listens_for(Session, "after_begin")
def _apply_tenant_on_begin(session: Session, _transaction, connection) -> None:
    connection.execute(_SET_TENANT_SQL, {"tid": session.info.get(TENANT_INFO_KEY) or ""})


@event.listens_for(Session, "before_flush")
def _guard_tenant_on_write(session: Session, _flush_context, _instances) -> None:
    """Guard de escrita do ORM no data plane.

    * objeto novo sem `tenant_id` → recebe o tenant AMARRADO à sessão (o tenant vem do
      contexto, nunca do payload); sem tenant amarrado, fica NULL e o NOT NULL rejeita;
    * objeto com `tenant_id` diferente do tenant amarrado → erro (escrita cruzada).
    Sessões sem tenant amarrado (CLI privilegiada) não são alteradas.
    """
    tid = session.info.get(TENANT_INFO_KEY)
    if not tid:
        return
    for obj in list(session.new) + list(session.dirty):
        if not hasattr(obj, "tenant_id") or getattr(obj, "__table__", None) is None:
            continue
        if obj.__table__.metadata is not _data_plane_metadata():
            continue
        atual = obj.tenant_id
        if atual is None and obj in session.new:
            obj.tenant_id = tid
        elif atual != tid:
            raise TenantContextMissing("escrita com tenant_id diferente do contexto")


def _data_plane_metadata():
    from app.db.base import Base

    return Base.metadata
