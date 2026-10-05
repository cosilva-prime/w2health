"""Camada de acesso ao banco: bases declarativas, engines, sessões e escopo de tenant."""

from app.db.base import Base, ControlBase
from app.db.session import AdminSessionLocal, SessionLocal, get_db, get_engine

__all__ = ["Base", "ControlBase", "AdminSessionLocal", "SessionLocal", "get_db", "get_engine"]
