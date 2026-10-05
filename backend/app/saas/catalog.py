"""Catálogo de features (capabilities) e planos PADRÃO.

* `FEATURES` é a lista de capabilities que **existem no código** — cada chave é checada por
  pelo menos uma rota (`require_feature`) ou serviço. Não se cria feature "futura" aqui;
  candidatas ficam documentadas em `docs/FEATURE_CATALOG.md`.
* `DEFAULT_PLANS` é só o **ponto de partida** (matriz demonstrativa, não comercial): depois
  de criado, cada plano é editado pela área administrativa. `sync_catalog` nunca sobrescreve
  edição feita no admin — só insere o que falta.
* Nenhuma regra de negócio lê `plan.code`. A aplicação pergunta `has_feature(...)`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Feature, Plan, PlanFeature


@dataclass(frozen=True)
class FeatureDef:
    key: str
    name: str
    description: str
    module: str


FEATURES: tuple[FeatureDef, ...] = (
    FeatureDef("executive_overview", "Visão Executiva",
               "KPIs da carteira, evolução e fatores de atenção.", "Executive Overview"),
    FeatureDef("loss_ratio_intelligence", "Inteligência de Sinistralidade",
               "Indicador, evolução, decomposição receita x despesa, explicação por dimensão, "
               "bridge frequência x custo médio e procedimentos.", "Loss Ratio Intelligence"),
    FeatureDef("financial_composition", "Composição financeira",
               "Despesa bruta, glosas, coparticipação e líquida; decomposição em 4 efeitos.",
               "Loss Ratio Intelligence"),
    FeatureDef("advanced_explanations", "Explicações avançadas (coortes)",
               "O porquê do porquê: coortes com evidências FATO / HIPÓTESE / A INVESTIGAR.",
               "Loss Ratio Intelligence"),
    FeatureDef("contract_intelligence", "Inteligência de Contratos",
               "Vidas, despesa, concentração e drivers por contrato (sem sinistralidade "
               "contratual enquanto não houver receita por contrato).", "Contract Intelligence"),
    FeatureDef("provider_intelligence", "Inteligência de Prestadores",
               "Ranking de contribuição, anomalias vs pares (z-score) e detalhe do prestador.",
               "Provider Intelligence"),
    FeatureDef("beneficiary_intelligence", "Inteligência de Beneficiários",
               "Beneficiários anonimizados, concentração, comportamento e novos casos de alto "
               "custo.", "Beneficiary Intelligence"),
    FeatureDef("insights", "Insights automáticos",
               "Achados derivados matematicamente dos dados, com metodologia e deep-link.",
               "Insights & Alerts"),
    FeatureDef("alerts", "Alertas configuráveis",
               "Regras de alerta sobre o catálogo fechado de indicadores.", "Insights & Alerts"),
    FeatureDef("custom_branding", "Identidade visual do cliente",
               "Permite ao administrador do tenant ajustar nome de produto, cores e logo "
               "(white-label limitado).", "Plataforma"),
)
FEATURE_KEYS = frozenset(f.key for f in FEATURES)


@dataclass(frozen=True)
class PlanDef:
    code: str
    name: str
    description: str
    features: tuple[str, ...]


_BASE = ("executive_overview", "loss_ratio_intelligence", "financial_composition",
         "contract_intelligence", "insights")
_BUSINESS = _BASE + ("provider_intelligence", "beneficiary_intelligence", "alerts",
                     "advanced_explanations")

DEFAULT_PLANS: tuple[PlanDef, ...] = (
    PlanDef("BASIC", "Basic", "Matriz demonstrativa: visão executiva, sinistralidade e "
            "contratos.", _BASE),
    PlanDef("BUSINESS", "Business", "Matriz demonstrativa: + prestadores, beneficiários, "
            "alertas e explicações avançadas.", _BUSINESS),
    PlanDef("ENTERPRISE", "Enterprise", "Matriz demonstrativa: todas as capabilities, "
            "incluindo identidade visual do cliente.", _BUSINESS + ("custom_branding",)),
)


def sync_catalog(session: Session) -> dict[str, int]:
    """Insere features e planos padrão AUSENTES (idempotente; não altera o que existe)."""
    novas_features = 0
    existentes = {f.key for f in session.execute(select(Feature)).scalars()}
    for ordem, fd in enumerate(FEATURES):
        if fd.key not in existentes:
            session.add(Feature(key=fd.key, name=fd.name, description=fd.description,
                                module=fd.module, is_active=True, sort_order=ordem))
            novas_features += 1
    session.flush()

    novos_planos = 0
    planos = {p.code: p for p in session.execute(select(Plan)).scalars()}
    for ordem, pd in enumerate(DEFAULT_PLANS):
        if pd.code in planos:
            continue
        plano = Plan(code=pd.code, name=pd.name, description=pd.description,
                     is_active=True, sort_order=ordem)
        session.add(plano)
        session.flush()
        session.add_all(PlanFeature(plan_id=plano.id, feature_key=k) for k in pd.features)
        novos_planos += 1
    session.flush()
    return {"features_inseridas": novas_features, "planos_inseridos": novos_planos}
