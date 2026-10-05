"""Lineage — "de onde veio este dado?"

    métrica de Serving/Gold (tenant, competência)
      → linhas da Silver agrupadas por origem (source_system, fonte, ingestão)
      → ingestão (status, estágio, checksum, mapping, quem disparou)
      → objetos RAW (chave no storage, sha256, nº de registros)
      → fonte (nome, tipo)

Sem plataforma gráfica: são consultas sobre os metadados persistidos pelo pipeline.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AggSinistralidadeCompetencia,
    IngestionRun,
    PipelineRun,
    RawObject,
    Receita,
    SourceConnection,
)
from app.models import EventoAssistencial as Ev


def _iso(d):
    return d.isoformat() if d else None


def ingestion_detail(session: Session, run: IngestionRun) -> dict:
    raws = session.execute(select(RawObject).where(RawObject.ingestion_run_id == run.id)
                           .order_by(RawObject.id)).scalars().all()
    pr = session.execute(select(PipelineRun).where(PipelineRun.ingestion_run_id == run.id)
                         .order_by(PipelineRun.id.desc())).scalars().first()
    conn = session.get(SourceConnection, run.source_connection_id) if run.source_connection_id else None
    return {
        "ingestion_run_id": run.id, "status": run.status, "stage": run.stage,
        "started_at": _iso(run.started_at), "finished_at": _iso(run.finished_at),
        "triggered_by": run.triggered_by, "checksum": run.checksum, "mapping_ref": run.mapping_ref,
        "duplicate_of": run.duplicate_of,
        "source": {"id": conn.id, "name": conn.name, "source_type": conn.source_type,
                   "source_system": conn.source_system} if conn else {"source_system": run.source_system},
        "pipeline_run_id": pr.id if pr else None,
        "raw_objects": [{"entity": r.source_entity, "file_name": r.file_name,
                         "storage_key": r.storage_key, "sha256": r.sha256, "records": r.records,
                         "size_bytes": r.size_bytes} for r in raws],
    }


def metric_lineage(session: Session, tenant_id: str, competencia: date) -> dict:
    gold = session.execute(select(AggSinistralidadeCompetencia).where(
        AggSinistralidadeCompetencia.tenant_id == tenant_id,
        AggSinistralidadeCompetencia.competencia == competencia)).scalars().first()
    eventos = session.execute(
        select(Ev.source_system, Ev.source_connection_id, Ev.ingestion_run_id, func.count(),
               func.sum(Ev.valor_apresentado))
        .where(Ev.tenant_id == tenant_id, Ev.competencia == competencia)
        .group_by(Ev.source_system, Ev.source_connection_id, Ev.ingestion_run_id)).all()
    receitas = session.execute(
        select(Receita.source_system, Receita.source_connection_id, Receita.ingestion_run_id,
               func.count(), func.sum(Receita.receita_contraprestacao))
        .where(Receita.tenant_id == tenant_id, Receita.competencia == competencia)
        .group_by(Receita.source_system, Receita.source_connection_id, Receita.ingestion_run_id)).all()
    run_ids = {r[2] for r in eventos + receitas if r[2] is not None}
    runs = [ingestion_detail(session, r) for r in session.execute(
        select(IngestionRun).where(IngestionRun.id.in_(run_ids))).scalars()] if run_ids else []
    return {
        "tenant_id": tenant_id, "competencia": competencia.isoformat(),
        "gold": {
            "tabela": "agg_sinistralidade_competencia",
            "despesa_bruta": str(gold.despesa_bruta), "despesa_liquida": str(gold.despesa_liquida),
            "receita": str(gold.receita), "eventos": gold.eventos,
        } if gold else None,
        "silver": {
            "eventos_assistenciais": [{"source_system": r[0], "source_connection_id": r[1],
                                       "ingestion_run_id": r[2], "linhas": r[3],
                                       "valor_apresentado": str(r[4])} for r in eventos],
            "receitas": [{"source_system": r[0], "source_connection_id": r[1],
                          "ingestion_run_id": r[2], "linhas": r[3],
                          "receita": str(r[4])} for r in receitas],
        },
        "ingestoes": runs,
    }
