"""Acesso a dados de configuração — regras de alerta (v1.1, Etapa C)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RegraAlerta


def listar(session: Session, apenas_ativas: bool = False) -> list[RegraAlerta]:
    stmt = select(RegraAlerta).order_by(RegraAlerta.id)
    if apenas_ativas:
        stmt = stmt.where(RegraAlerta.ativo.is_(True))
    return list(session.execute(stmt).scalars().all())


def obter(session: Session, id_regra: int) -> RegraAlerta | None:
    return session.get(RegraAlerta, id_regra)


def criar(session: Session, dados: dict) -> RegraAlerta:
    regra = RegraAlerta(**dados)
    session.add(regra)
    session.commit()
    session.refresh(regra)
    return regra


def atualizar(session: Session, id_regra: int, dados: dict) -> RegraAlerta | None:
    regra = session.get(RegraAlerta, id_regra)
    if regra is None:
        return None
    for k, v in dados.items():
        if v is not None:
            setattr(regra, k, v)
    session.commit()
    session.refresh(regra)
    return regra


def excluir(session: Session, id_regra: int) -> bool:
    regra = session.get(RegraAlerta, id_regra)
    if regra is None:
        return False
    session.delete(regra)
    session.commit()
    return True
