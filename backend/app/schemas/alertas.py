"""Schemas de `regras_alerta` (configuração de insights/alertas — v1.1 Etapa C)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.config import ENTIDADES_VALIDAS, OPERADORES_VALIDOS, SEVERIDADES_VALIDAS

Entidade = Literal["beneficiario", "prestador", "procedimento", "plano", "contrato", "financeiro"]
Operador = Literal[">=", ">", "<=", "<", "=="]
Severidade = Literal["critica", "atencao", "informativo"]

assert set(Entidade.__args__) == set(ENTIDADES_VALIDAS)  # trava as duas fontes de verdade
assert set(Operador.__args__) == set(OPERADORES_VALIDOS)
assert set(Severidade.__args__) == set(SEVERIDADES_VALIDAS)


class RegraAlertaBase(BaseModel):
    nome: str = Field(min_length=3, max_length=120)
    entidade: Entidade
    indicador: str = Field(min_length=1, max_length=50)
    operador: Operador
    limite: float
    severidade: Severidade
    escopo: dict = Field(default_factory=dict)
    ativo: bool = True


class RegraAlertaCreate(RegraAlertaBase):
    pass


class RegraAlertaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=3, max_length=120)
    entidade: Entidade | None = None
    indicador: str | None = Field(default=None, min_length=1, max_length=50)
    operador: Operador | None = None
    limite: float | None = None
    severidade: Severidade | None = None
    escopo: dict | None = None
    ativo: bool | None = None


class RegraAlertaOut(RegraAlertaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    criado_em: datetime
    atualizado_em: datetime
