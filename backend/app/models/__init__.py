"""Modelos ORM do W2Health Intelligence.

Camada fonte (OLTP-like): catálogos, carteira, eventos assistenciais, receitas.
Camada analítica: agregações mensais, gabarito de cenários e manifesto do seed.
Data Platform (v1.2): controle de ingestão (estrutura, não uso).
Control plane (Fundação SaaS V1, `ControlBase`): tenants, usuários, sessões, planos,
features, branding, configurações, segredos e auditoria — `app/models/saas.py`.
"""

from app.models.analytics import (
    AggBeneficiarioCompetencia,
    AggCompetenciaDimensao,
    AggContratoCompetencia,
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
from app.models.platform import (
    DataQualityResult,
    IngestionRun,
    PipelineRun,
    ReceitaContrato,
    SourceConnection,
    SourceEntity,
    Tenant,
)
from app.models.saas import (
    AuditLog,
    AuthSession,
    Feature,
    Plan,
    PlanFeature,
    RefreshToken,
    TenantBranding,
    TenantBrandingAsset,
    TenantFeature,
    TenantSecret,
    TenantSetting,
    User,
    UserTenant,
)

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
    "AggContratoCompetencia",
    "CenarioGabarito",
    "SeedManifest",
    # Data Platform (v1.2)
    "Tenant",
    "SourceConnection",
    "SourceEntity",
    "IngestionRun",
    "PipelineRun",
    "DataQualityResult",
    "ReceitaContrato",
    # Control plane — Fundação SaaS V1
    "User",
    "UserTenant",
    "AuthSession",
    "RefreshToken",
    "Plan",
    "Feature",
    "PlanFeature",
    "TenantFeature",
    "TenantBranding",
    "TenantBrandingAsset",
    "TenantSetting",
    "TenantSecret",
    "AuditLog",
]
