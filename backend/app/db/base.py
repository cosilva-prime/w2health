"""Bases declarativas do SQLAlchemy com convenção de nomes para constraints/índices.

Duas metadatas, duas responsabilidades (Fundação SaaS V1):

* `Base` — **data plane**: tudo que pertence a uma operadora. Toda tabela aqui tem
  `tenant_id` NOT NULL e recebe política de Row-Level Security (exceção única: o calendário
  global `competencias`). Invariante verificado por `tests/test_multitenancy.py`.
* `ControlBase` — **control plane**: cadastro de tenants, usuários, vínculos, sessões,
  planos, features, branding, configurações, segredos e auditoria. São tabelas da
  plataforma; o isolamento delas é feito na aplicação (dependências de RBAC), não por RLS,
  porque o próprio fluxo de autenticação precisa enxergar vínculos de vários tenants.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base do data plane (dados de operadora, tenant-scoped)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ControlBase(DeclarativeBase):
    """Base do control plane (plataforma SaaS)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


ALL_METADATA = (Base.metadata, ControlBase.metadata)


def create_all(bind) -> None:
    """Cria as tabelas das duas metadatas (control plane primeiro — FKs para `tenants`)."""
    ControlBase.metadata.create_all(bind)
    Base.metadata.create_all(bind)
