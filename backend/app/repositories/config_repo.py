"""Acesso a dados de configuração — regras de alerta (v1.1, Etapa C).

Fundação SaaS V1: toda operação é escopada pelo tenant amarrado à sessão
(`tenant_of(session)` — fail-closed). `session.get(RegraAlerta, id)` foi substituído por
consulta com `tenant_id` para que um id de outro tenant seja indistinguível de inexistente
(IDOR). O `tenant_id` de uma regra nova vem do contexto, nunca do payload. `auditar`
(opcional) grava a auditoria na mesma transação do commit.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.tenant_scope import tenant_of
from app.models import RegraAlerta

Auditor = Callable[[RegraAlerta], None] | None


def listar(session: Session, apenas_ativas: bool = False) -> list[RegraAlerta]:
    stmt = select(RegraAlerta).where(RegraAlerta.tenant_id == tenant_of(session)).order_by(RegraAlerta.id)
    if apenas_ativas:
        stmt = stmt.where(RegraAlerta.ativo.is_(True))
    return list(session.execute(stmt).scalars().all())


def contar(session: Session) -> int:
    return session.execute(
        select(func.count()).select_from(RegraAlerta).where(RegraAlerta.tenant_id == tenant_of(session))
    ).scalar_one()


def obter(session: Session, id_regra: int) -> RegraAlerta | None:
    return session.execute(
        select(RegraAlerta).where(RegraAlerta.id == id_regra,
                                  RegraAlerta.tenant_id == tenant_of(session))
    ).scalar_one_or_none()


def criar(session: Session, dados: dict, auditar: Auditor = None) -> RegraAlerta:
    dados = {k: v for k, v in dados.items() if k != "tenant_id"}  # nunca do payload
    regra = RegraAlerta(**dados, tenant_id=tenant_of(session))
    session.add(regra)
    session.flush()
    if auditar:
        auditar(regra)
    session.commit()
    session.refresh(regra)
    return regra


def atualizar(session: Session, id_regra: int, dados: dict, auditar: Auditor = None) -> RegraAlerta | None:
    regra = obter(session, id_regra)
    if regra is None:
        return None
    for k, v in dados.items():
        if v is not None and k not in ("id", "tenant_id"):
            setattr(regra, k, v)
    session.flush()
    if auditar:
        auditar(regra)
    session.commit()
    session.refresh(regra)
    return regra


def excluir(session: Session, id_regra: int, auditar: Auditor = None) -> bool:
    regra = obter(session, id_regra)
    if regra is None:
        return False
    if auditar:
        auditar(regra)
    session.delete(regra)
    session.commit()
    return True
