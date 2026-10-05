"""Transparência de indicadores — definição, fórmula, composição e PROCEDÊNCIA real.

Regras:
* As definições reproduzem as fórmulas efetivamente implementadas (`formulas.py`,
  `sinistralidade.py`, `seed/aggregate.py`) e documentadas em `docs/ANALYTICS_ENGINE.md` —
  não há fórmula "de vitrine".
* A procedência vem do banco: última ingestão PUBLICADA (`ingestion_runs.stage=AVAILABLE`,
  de qualquer fonte — gerador sintético ou arquivo externo) e as fontes ativas do tenant. Sem registro → `None` e a interface mostra
  "Não disponível" — nada é fabricado.
* Massa sintética é sempre declarada (`dados_sinteticos=True`).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.tenant_scope import tenant_of

_ORIGEM_SERIE = "Serving · agg_sinistralidade_competencia (competência)"
_ORIGEM_FATO = "Serving · eventos_assistenciais → agregação mensal"

KPIS: dict[str, dict] = {
    "sinistralidade_liquida": {
        "rotulo": "Sinistralidade líquida",
        "definicao": "Quanto da receita de contraprestação foi consumido pela despesa "
                     "assistencial líquida no mês (KPI oficial).",
        "formula": "despesa líquida ÷ receita × 100",
        "composicao": ["Despesa apresentada (bruta)", "(−) glosas", "(−) coparticipação",
                       "= despesa líquida", "÷ receita de contraprestação",
                       "= sinistralidade líquida"],
        "unidade": "%", "origem": _ORIGEM_SERIE,
    },
    "sinistralidade_bruta": {
        "rotulo": "Sinistralidade bruta",
        "definicao": "Despesa apresentada pelos prestadores, antes de glosas e coparticipação, "
                     "sobre a receita.",
        "formula": "despesa bruta ÷ receita × 100",
        "composicao": ["Σ valor apresentado", "÷ receita de contraprestação"],
        "unidade": "%", "origem": _ORIGEM_SERIE,
    },
    "despesa_liquida": {
        "rotulo": "Despesa assistencial líquida",
        "definicao": "Despesa efetivamente suportada pela operadora.",
        "formula": "Σ (valor apresentado − valor glosado − coparticipação)",
        "composicao": ["Despesa apresentada", "(−) glosas", "(−) coparticipação",
                       "= despesa líquida"],
        "unidade": "R$", "origem": _ORIGEM_SERIE,
    },
    "receita": {
        "rotulo": "Receita de contraprestação",
        "definicao": "Receita do mês, informada no grão competência × plano.",
        "formula": "Σ receita_contraprestacao (competência × plano)",
        "composicao": [],
        "unidade": "R$", "origem": "Serving · receitas (competência × plano)",
    },
    "custo_pmpm": {
        "rotulo": "Custo assistencial por beneficiário (PMPM)",
        "definicao": "Despesa líquida média por beneficiário exposto no mês.",
        "formula": "despesa líquida ÷ exposição (beneficiários-mês)",
        "composicao": [],
        "unidade": "R$", "origem": _ORIGEM_SERIE,
    },
    "beneficiarios": {
        "rotulo": "Beneficiários expostos",
        "definicao": "Exposição do mês: soma dos beneficiários informados na receita por plano.",
        "formula": "Σ quantidade_beneficiarios (receitas do mês)",
        "composicao": [],
        "unidade": "vidas", "origem": _ORIGEM_SERIE,
    },
    "variacao_pp": {
        "rotulo": "Variação da sinistralidade",
        "definicao": "Diferença em pontos percentuais contra a base de comparação escolhida; "
                     "decomposta em efeito despesa + efeito receita (soma exata).",
        "formula": "sinistralidade(t) − sinistralidade(base)",
        "composicao": ["efeito despesa (p.p.)", "+ efeito receita (p.p.)", "= variação (p.p.)"],
        "unidade": "p.p.", "origem": _ORIGEM_SERIE,
    },
    "acumulado_12m": {
        "rotulo": "Sinistralidade acumulada 12 meses",
        "definicao": "Razão das somas dos 12 meses encerrados na competência.",
        "formula": "Σ despesa líquida (12m) ÷ Σ receita (12m) × 100",
        "composicao": [],
        "unidade": "%", "origem": _ORIGEM_SERIE,
    },
    "custo_medio": {
        "rotulo": "Custo médio por evento",
        "definicao": "Valor pago médio por evento na célula analisada.",
        "formula": "Σ valor pago ÷ nº de eventos",
        "composicao": [],
        "unidade": "R$", "origem": _ORIGEM_FATO,
    },
    "frequencia": {
        "rotulo": "Frequência por mil beneficiários",
        "definicao": "Eventos por mil beneficiários expostos no mês.",
        "formula": "eventos ÷ exposição × 1000",
        "composicao": [],
        "unidade": "‰", "origem": _ORIGEM_FATO,
    },
}


def procedencia(session: Session, *, is_synthetic: bool) -> dict:
    t = tenant_of(session)
    carga = session.execute(
        text("SELECT criado_em, inicio, fim FROM seed_manifest WHERE tenant_id = :t "
             "ORDER BY criado_em DESC LIMIT 1"),
        {"t": t},
    ).mappings().first()
    ingestao = session.execute(
        text("SELECT r.finished_at, c.name, c.source_type, c.source_system FROM ingestion_runs r "
             "LEFT JOIN source_connections c ON c.id = r.source_connection_id "
             "WHERE r.tenant_id = :t AND r.stage = 'AVAILABLE' "
             "ORDER BY r.finished_at DESC NULLS LAST LIMIT 1"),
        {"t": t},
    ).mappings().first()
    fontes = session.execute(
        text("SELECT name, source_type, last_success_at FROM source_connections "
             "WHERE tenant_id = :t AND status = 'ACTIVE' ORDER BY id"),
        {"t": t},
    ).mappings().all()

    if ingestao is not None and ingestao["finished_at"] is not None:
        ultima = ingestao["finished_at"]
        tipo = "massa_sintetica" if ingestao["source_type"] == "SYNTHETIC" else "ingestao"
    elif carga is not None:
        ultima, tipo = carga["criado_em"], "massa_sintetica"
    else:
        ultima, tipo = None, None

    return {
        "dados_sinteticos": bool(is_synthetic),
        "ultima_atualizacao": ultima.isoformat() if ultima else None,
        "tipo_carga": tipo,
        "janela": ({"inicio": carga["inicio"].isoformat(), "fim": carga["fim"].isoformat()}
                   if carga else None),
        "camada": "Serving (PostgreSQL) — tabelas agregadas agg_* reconstruídas a partir da "
                  "fato eventos_assistenciais",
        # origem lógica real dos dados (o motor analítico não usa isto — só exibição)
        "fonte_ultima_carga": ({"nome": ingestao["name"], "tipo": ingestao["source_type"]}
                               if ingestao is not None and ingestao["name"] else None),
        "fontes": [{"nome": f["name"], "tipo": f["source_type"],
                    "ultima_carga": f["last_success_at"].isoformat() if f["last_success_at"] else None}
                   for f in fontes],
        "kpis": KPIS,
    }
