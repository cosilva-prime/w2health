"""Admin Works2Data — Integrações / Data Sources (somente SUPER_ADMIN).

O tenant-alvo vem do caminho (área de plataforma) e cada leitura/escrita do data plane é
feita numa sessão amarrada a ESSE tenant (RLS). A execução de carga usa o papel de
pipeline (`app/data_platform/runner.py`). Segredos nunca são exibidos.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.data_platform import connections as conn_svc
from app.data_platform import lineage, onboarding, readiness
from app.data_platform.context import PipelineError
from app.data_platform.mapping import MappingError
from app.data_platform.runner import FileValidationError, run_file_ingestion
from app.db.pipeline import PipelineDatabaseNotConfigured
from app.db.session import get_db
from app.db.tenant_scope import bind_tenant
from app.models import (
    DataQualityResult,
    IngestionRun,
    PipelineRun,
    ReconciliationResult,
    SourceConnection,
    Tenant,
)
from app.saas import audit
from app.saas.features import resolve_all
from app.security.deps import Principal, require_platform
from app.security.errors import ApiError
from app.security.rbac import Perm

router = APIRouter(prefix="/admin", tags=["Administração Works2Data — Integrações"])
_INTEG = require_platform(Perm.PLATFORM_TENANTS_MANAGE)


class SourceIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    source_type: str
    source_system: str = Field(min_length=2, max_length=60)
    configuration: dict = Field(default_factory=dict)
    secret_reference: str | None = Field(default=None, max_length=120)


class SourcePatchIn(BaseModel):
    status: str


class OnboardingIn(BaseModel):
    state: str
    note: str = Field(min_length=3, max_length=200)


@contextmanager
def tenant_session(db: Session, tenant_id: str):
    if db.get(Tenant, tenant_id) is None:
        raise ApiError("not_found", "Tenant não encontrado.")
    s = Session(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    try:
        bind_tenant(s, tenant_id)
        yield s
    finally:
        s.close()


def _iso(d):
    return d.isoformat() if d else None


def run_dict(r: IngestionRun) -> dict:
    return {
        "id": r.id, "source_connection_id": r.source_connection_id, "status": r.status, "stage": r.stage,
        "started_at": _iso(r.started_at), "finished_at": _iso(r.finished_at),
        "records_received": r.records_received, "records_valid": r.records_valid,
        "records_rejected": r.records_rejected, "warnings": r.warnings_count, "errors": r.errors_count,
        "competencia_inicio": _iso(r.competencia_inicio), "competencia_fim": _iso(r.competencia_fim),
        "checksum": r.checksum, "mapping_ref": r.mapping_ref, "triggered_by": r.triggered_by,
        "duplicate_of": r.duplicate_of, "error_summary": r.error_summary or {},
        "correlation_id": r.correlation_id,
    }


def _recon_status(s: Session, run_id: int) -> str | None:
    sts = set(s.execute(select(ReconciliationResult.status).where(
        ReconciliationResult.ingestion_run_id == run_id)).scalars())
    if not sts:
        return None
    return "FAIL" if "FAIL" in sts else ("WARNING" if "WARNING" in sts else "PASS")


# ============================================================================ visão geral
@router.get("/integrations", summary="Fontes de dados de todos os tenants (visão operacional)")
def overview(_p: Principal = Depends(_INTEG), db: Session = Depends(get_db)) -> dict:
    itens = []
    for t in db.execute(select(Tenant).order_by(Tenant.name)).scalars():
        with tenant_session(db, t.id) as s:
            for c in conn_svc.list_for_tenant(s, t.id):
                ultimo = s.execute(select(IngestionRun).where(IngestionRun.source_connection_id == c.id)
                                   .order_by(desc(IngestionRun.id))).scalars().first()
                # última carga EFETIVA publicada (reenvio idêntico não conta como carga)
                publicada = s.execute(select(IngestionRun).where(
                    IngestionRun.source_connection_id == c.id, IngestionRun.stage == "AVAILABLE",
                    IngestionRun.duplicate_of.is_(None)).order_by(desc(IngestionRun.id))).scalars().first()
                itens.append({"tenant_id": t.id, "tenant_name": t.name, **conn_svc.as_dict(c),
                              "last_run": run_dict(ultimo) if ultimo else None,
                              "last_published": run_dict(publicada) if publicada else None,
                              "last_published_reconciliation": _recon_status(s, publicada.id) if publicada else None})
            ob = onboarding.get(s, t.id)
            s.commit()
        for i in itens:
            if i["tenant_id"] == t.id:
                i["onboarding_state"] = ob.state
    return {"itens": itens}


# ============================================================================ fontes
@router.get("/tenants/{tenant_id}/sources")
def list_sources(tenant_id: str, _p: Principal = Depends(_INTEG), db: Session = Depends(get_db)) -> dict:
    with tenant_session(db, tenant_id) as s:
        return {"itens": [conn_svc.as_dict(c) for c in conn_svc.list_for_tenant(s, tenant_id)]}


@router.post("/tenants/{tenant_id}/sources", status_code=201)
def create_source(tenant_id: str, payload: SourceIn, p: Principal = Depends(_INTEG),
                  db: Session = Depends(get_db)) -> dict:
    try:
        cfg = conn_svc.validate_payload(payload.source_type, payload.name, payload.source_system,
                                        payload.configuration, payload.secret_reference)
    except (conn_svc.ConnectionError_, MappingError, ValueError) as e:
        raise ApiError("invalid_request", str(e)) from e
    with tenant_session(db, tenant_id) as s:
        if s.execute(select(SourceConnection).where(SourceConnection.tenant_id == tenant_id,
                                                    SourceConnection.name == payload.name)).first():
            raise ApiError("conflict", "Já existe uma fonte com este nome no tenant.")
        c = SourceConnection(tenant_id=tenant_id, name=payload.name, source_type=payload.source_type,
                             source_system=payload.source_system, configuration=cfg,
                             secret_reference=payload.secret_reference)
        s.add(c)
        s.flush()
        onboarding.advance(s, tenant_id, "SOURCE_REGISTERED", by=p.email)
        audit.add(s, "integration.source_created", actor=p.actor(), tenant_id=tenant_id,
                  entity_type="source_connection", entity_id=c.id,
                  details={"tipo": c.source_type, "source_system": c.source_system,
                           "mapping": cfg.get("mapping_id"), "com_segredo": c.secret_reference is not None})
        s.commit()
        return conn_svc.as_dict(c)


@router.patch("/tenants/{tenant_id}/sources/{source_id}")
def patch_source(tenant_id: str, source_id: int, payload: SourcePatchIn, p: Principal = Depends(_INTEG),
                 db: Session = Depends(get_db)) -> dict:
    if payload.status not in ("ACTIVE", "DISABLED"):
        raise ApiError("invalid_request", "status deve ser ACTIVE ou DISABLED")
    with tenant_session(db, tenant_id) as s:
        c = s.get(SourceConnection, source_id)
        if c is None:
            raise ApiError("not_found", "Fonte não encontrada.")
        de = c.status
        c.status = payload.status
        audit.add(s, "integration.source_status", actor=p.actor(), tenant_id=tenant_id,
                  entity_type="source_connection", entity_id=c.id, details={"de": de, "para": c.status})
        s.commit()
        return conn_svc.as_dict(c)


@router.post("/tenants/{tenant_id}/sources/{source_id}/validate", summary="Valida conectividade da fonte")
def validate_source(tenant_id: str, source_id: int, p: Principal = Depends(_INTEG),
                    db: Session = Depends(get_db)) -> dict:
    with tenant_session(db, tenant_id) as s:
        c = s.get(SourceConnection, source_id)
        if c is None:
            raise ApiError("not_found", "Fonte não encontrada.")
        try:
            r = conn_svc.validate_connectivity(c)
        except (MappingError, ValueError) as e:
            r = {"ok": False, "detail": str(e)[:200]}
        if r["ok"]:
            onboarding.advance(s, tenant_id, "CONNECTION_VALIDATED", by=p.email)
        audit.add(s, "integration.source_validated", actor=p.actor(), tenant_id=tenant_id,
                  entity_type="source_connection", entity_id=c.id, outcome="success" if r["ok"] else "failure")
        s.commit()
        return r


# ============================================================================ upload controlado
@router.post("/tenants/{tenant_id}/sources/{source_id}/uploads",
             summary="Importação controlada (fonte FILE): RAW → mapping → DQ → Silver → Gold → reconciliação")
async def upload(tenant_id: str, source_id: int, files: list[UploadFile] = File(...),
                 p: Principal = Depends(_INTEG), db: Session = Depends(get_db)) -> dict:
    cfg = get_settings()
    limite = cfg.upload_max_file_mb * 1024 * 1024
    if len(files) > cfg.upload_max_files:
        raise ApiError("invalid_request", f"no máximo {cfg.upload_max_files} arquivos por carga")
    recebidos: dict[str, bytes] = {}
    for f in files:
        data = await f.read(limite + 1)
        if len(data) > limite:
            raise ApiError("invalid_request", f"arquivo maior que {cfg.upload_max_file_mb} MB")
        recebidos[(f.filename or "")[:200]] = data
    if db.get(Tenant, tenant_id) is None:
        raise ApiError("not_found", "Tenant não encontrado.")
    try:
        r = await run_in_threadpool(run_file_ingestion, tenant_id=tenant_id, source_connection_id=source_id,
                                    files=recebidos, triggered_by=p.email, max_bytes=limite,
                                    max_files=cfg.upload_max_files)
    except PipelineDatabaseNotConfigured as e:
        raise ApiError("service_unavailable", "Execução de pipeline não configurada neste ambiente.") from e
    except (PipelineError, MappingError, FileValidationError) as e:
        raise ApiError("invalid_request", str(e)[:300]) from e
    return r.as_dict()


# ============================================================================ execuções
@router.get("/tenants/{tenant_id}/ingestion-runs")
def list_runs(tenant_id: str, source_id: int | None = Query(None), limit: int = Query(50, ge=1, le=200),
              _p: Principal = Depends(_INTEG), db: Session = Depends(get_db)) -> dict:
    with tenant_session(db, tenant_id) as s:
        stmt = select(IngestionRun).order_by(desc(IngestionRun.id)).limit(limit)
        if source_id:
            stmt = stmt.where(IngestionRun.source_connection_id == source_id)
        itens = []
        for r in s.execute(stmt).scalars():
            itens.append({**run_dict(r), "reconciliation": _recon_status(s, r.id)})
        return {"itens": itens}


@router.get("/tenants/{tenant_id}/ingestion-runs/{run_id}")
def get_run(tenant_id: str, run_id: int, _p: Principal = Depends(_INTEG), db: Session = Depends(get_db)) -> dict:
    with tenant_session(db, tenant_id) as s:
        r = s.get(IngestionRun, run_id)
        if r is None:
            raise ApiError("not_found", "Execução não encontrada.")
        prun = s.execute(select(PipelineRun).where(PipelineRun.ingestion_run_id == r.id)
                         .order_by(desc(PipelineRun.id))).scalars().first()
        dq = s.execute(select(DataQualityResult).where(DataQualityResult.ingestion_run_id == r.id)
                       .order_by(DataQualityResult.id)).scalars().all()
        rec = s.execute(select(ReconciliationResult).where(ReconciliationResult.ingestion_run_id == r.id)
                        .order_by(ReconciliationResult.id)).scalars().all()
        return {
            "run": run_dict(r),
            "lineage": lineage.ingestion_detail(s, r),
            "steps": prun.steps if prun else [],
            "pipeline_status": prun.status if prun else None,
            "data_quality": [{"rule_id": d.rule_id, "description": d.rule_description, "entity": d.entity,
                              "severity": d.severity, "blocking": d.blocking, "checked": d.records_checked,
                              "failed": d.records_failed, "sample": (d.sample or {}).get("referencias", [])}
                             for d in dq],
            "reconciliation": [{"check_id": c.check_id, "entity": c.entity, "scope": c.scope,
                                "expected": str(c.expected), "actual": str(c.actual),
                                "difference": str(c.difference), "tolerance": str(c.tolerance),
                                "status": c.status} for c in rec],
            "reconciliation_status": _recon_status(s, r.id),
        }


@router.get("/tenants/{tenant_id}/lineage", summary="De onde veio a métrica da competência?")
def get_lineage(tenant_id: str, competencia: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
                _p: Principal = Depends(_INTEG), db: Session = Depends(get_db)) -> dict:
    y, m = competencia.split("-")
    with tenant_session(db, tenant_id) as s:
        return lineage.metric_lineage(s, tenant_id, date(int(y), int(m), 1))


# ============================================================================ readiness / onboarding
def capabilities(s: Session, t: Tenant) -> list[dict]:
    prontidao = readiness.current(s, t.id)
    out = []
    for f in resolve_all(s, t):
        r = prontidao.get(f.key)
        out.append({"key": f.key, "name": f.name, "entitled": f.enabled, "entitlement_source": f.source,
                    "data_status": r.status if r else "NOT_READY", "data_reason": r.reason if r else "",
                    "available": f.enabled and bool(r and r.ready)})
    return out


@router.get("/tenants/{tenant_id}/readiness", summary="Feature contratada × dados prontos × disponível")
def get_readiness(tenant_id: str, _p: Principal = Depends(_INTEG), db: Session = Depends(get_db)) -> dict:
    with tenant_session(db, tenant_id) as s:
        out = {"itens": capabilities(s, s.get(Tenant, tenant_id))}
        s.commit()
        return out


@router.post("/tenants/{tenant_id}/readiness/refresh")
def refresh_readiness(tenant_id: str, p: Principal = Depends(_INTEG), db: Session = Depends(get_db)) -> dict:
    with tenant_session(db, tenant_id) as s:
        readiness.refresh(s, tenant_id)
        audit.add(s, "integration.readiness_refreshed", actor=p.actor(), tenant_id=tenant_id,
                  entity_type="tenant", entity_id=tenant_id)
        s.commit()
        return {"itens": capabilities(s, s.get(Tenant, tenant_id))}


@router.get("/tenants/{tenant_id}/onboarding")
def get_onboarding(tenant_id: str, _p: Principal = Depends(_INTEG), db: Session = Depends(get_db)) -> dict:
    with tenant_session(db, tenant_id) as s:
        ob = onboarding.get(s, tenant_id)
        s.commit()
        return onboarding.as_dict(ob)


@router.post("/tenants/{tenant_id}/onboarding", summary="Decisão manual: HOMOLOGATED ou ACTIVE")
def decide_onboarding(tenant_id: str, payload: OnboardingIn, p: Principal = Depends(_INTEG),
                      db: Session = Depends(get_db)) -> dict:
    with tenant_session(db, tenant_id) as s:
        try:
            ob = onboarding.decide(s, tenant_id, payload.state, by=p.email, note=payload.note)
        except onboarding.OnboardingError as e:
            raise ApiError("invalid_request", str(e)) from e
        audit.add(s, "integration.onboarding_decision", actor=p.actor(), tenant_id=tenant_id,
                  entity_type="tenant", entity_id=tenant_id,
                  details={"estado": payload.state, "nota": payload.note})
        s.commit()
        return onboarding.as_dict(ob)
