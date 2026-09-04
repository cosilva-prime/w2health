"""Configuração do gestor — regras de alerta (v1.1, Etapa C).

⚠️ DÍVIDA TÉCNICA: os endpoints que escrevem nesta tabela (`/api/config/regras-alerta`,
POST/PUT/DELETE) NÃO têm autenticação/autorização — aceitável apenas para demonstração
local. Ver docs/V1.1.md § Dívida Técnica antes de expor este ambiente publicamente.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ENTIDADES_VALIDAS = ("beneficiario", "prestador", "procedimento", "plano", "contrato", "financeiro")
OPERADORES_VALIDOS = (">=", ">", "<=", "<", "==")
SEVERIDADES_VALIDAS = ("critica", "atencao", "informativo")


class RegraAlerta(Base):
    __tablename__ = "regras_alerta"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    entidade: Mapped[str] = mapped_column(String(20))
    indicador: Mapped[str] = mapped_column(String(50))
    operador: Mapped[str] = mapped_column(String(4))
    limite: Mapped[float] = mapped_column(Float)
    severidade: Mapped[str] = mapped_column(String(20))
    escopo: Mapped[dict] = mapped_column(JSON, default=dict)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
