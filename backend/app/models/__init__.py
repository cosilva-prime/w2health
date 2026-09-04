"""Modelos ORM do W2Health Intelligence.

Camada fonte (OLTP-like): catálogos, carteira, eventos assistenciais, receitas.
Camada analítica: agregações mensais, gabarito de cenários e manifesto do seed.
"""

from app.models.analytics import (
    AggBeneficiarioCompetencia,
    AggCompetenciaDimensao,
    AggPrestadorCompetencia,
    AggSinistralidadeCompetencia,
    CenarioGabarito,
    SeedManifest,
)
from app.models.catalog import (
    Contrato,
    Diagnostico,
    Especialidade,
    Plano,
    Prestador,
    Procedimento,
    Regiao,
)
from app.models.config import RegraAlerta
from app.models.events import EventoAssistencial
from app.models.membership import Beneficiario, Competencia, Receita

__all__ = [
    "RegraAlerta",
    "Regiao",
    "Plano",
    "Contrato",
    "Especialidade",
    "Procedimento",
    "Prestador",
    "Diagnostico",
    "Competencia",
    "Beneficiario",
    "Receita",
    "EventoAssistencial",
    "AggSinistralidadeCompetencia",
    "AggCompetenciaDimensao",
    "AggPrestadorCompetencia",
    "AggBeneficiarioCompetencia",
    "CenarioGabarito",
    "SeedManifest",
]
