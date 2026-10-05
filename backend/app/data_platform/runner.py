"""Orquestrador do pipeline de arquivo (fonte FILE) — um tenant por execução.

    validar arquivos → RAW (imutável) → mapping → canônico → Data Quality (gate)
      → [transação] Silver → Gold → readiness → reconciliação → publicação (commit)

Garantias:
* tenant explícito (`PipelineContext`) e sessões do papel `w2health_pipeline` amarradas a
  ele (RLS) — sem fallback para o papel dono;
* nada é promovido antes do gate de Data Quality;
* Silver + Gold + reconciliação na MESMA transação: carga reprovada não é publicada;
* metadados (ingestão, DQ, reconciliação, passos) são gravados em transações próprias —
  sobrevivem à falha e explicam "por que a carga do tenant X falhou";
* estágio honesto: RECEIVED → VALIDATED → PROCESSED → RECONCILED → AVAILABLE;
* reenviar o MESMO pacote (mesmo checksum) não reprocessa nem duplica.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import log_context
from app.data_platform import onboarding, quality, readiness, reconciliation
from app.data_platform.canonical import ENTITIES, LOAD_ORDER
from app.data_platform.connections import load_connection_mapping
from app.data_platform.context import PipelineContext, PipelineError, require_active_tenant
from app.data_platform.mapping import EntityResult, Mapping, apply_entity
from app.data_platform.silver import SilverLoader, derive_canonical, existing_codes
from app.data_platform.storage import get_raw_storage, raw_key
from app.db.pipeline import PipelineSession
from app.db.tenant_scope import bind_tenant
from app.models import (
    DataQualityResult,
    IngestionRun,
    PipelineRun,
    RawObject,
    ReconciliationResult,
    SourceConnection,
)
from app.saas import audit
from app.seed.aggregate import rebuild_aggregations

log = logging.getLogger("app.pipeline")

_FILE = re.compile(r"^([a-z][a-z0-9_]{1,60})\.csv$")


@dataclass
class RunSummary:
    ingestion_run_id: int
    pipeline_run_id: int | None
    status: str
    stage: str | None
    received: int = 0
    valid: int = 0
    rejected: int = 0
    warnings: int = 0
    errors: int = 0
    reconciliation: str | None = None
    duplicate_of: int | None = None
    message: str = ""
    entities: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class FileValidationError(PipelineError):
    pass


# ======================================================================== validação de arquivos
def validate_files(mapping: Mapping, files: dict[str, bytes], *, max_bytes: int,
                   max_files: int) -> dict[str, tuple[list[str], list[dict], bytes]]:
    """Valida nome, extensão, tamanho, encoding e estrutura CSV. Nunca executa conteúdo.
    Retorna {source_entity: (cabeçalho, linhas, bytes)}."""
    if not files:
        raise FileValidationError("nenhum arquivo recebido")
    if len(files) > max_files:
        raise FileValidationError(f"no máximo {max_files} arquivos por carga")
    out = {}
    for nome, data in files.items():
        base = nome.replace("\\", "/").rsplit("/", 1)[-1].strip().lower()
        m = _FILE.match(base)
        if not m:
            raise FileValidationError(f"nome de arquivo inválido: use <entidade>.csv ({base[:60]!r})")
        entidade = m.group(1)
        if mapping.by_source(entidade) is None:
            raise FileValidationError(f"arquivo '{base}' não pertence ao mapping {mapping.ref}")
        if entidade in out:
            raise FileValidationError(f"arquivo duplicado: {base}")
        if len(data) == 0:
            raise FileValidationError(f"arquivo vazio: {base}")
        if len(data) > max_bytes:
            raise FileValidationError(f"arquivo maior que o limite ({max_bytes // (1024 * 1024)} MB): {base}")
        if b"\x00" in data[:65536]:
            raise FileValidationError(f"arquivo binário não é aceito: {base}")
        try:
            texto = data.decode(mapping.encoding).lstrip("﻿")
        except UnicodeDecodeError as e:
            raise FileValidationError(f"encoding inválido em {base} (esperado {mapping.encoding})") from e
        try:
            leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=mapping.delimiter, strict=True)
            linhas = list(leitor)
        except csv.Error as e:
            raise FileValidationError(f"CSV malformado em {base}: {str(e)[:80]}") from e
        if not linhas or not any(c.strip() for c in linhas[0]):
            raise FileValidationError(f"cabeçalho ausente em {base}")
        cab = [c.strip() for c in linhas[0]]
        if len(set(cab)) != len(cab):
            raise FileValidationError(f"colunas repetidas no cabeçalho de {base}")
        registros = []
        for n, lin in enumerate(linhas[1:], start=2):
            if not lin or all(not c.strip() for c in lin):
                continue
            if len(lin) != len(cab):
                raise FileValidationError(f"{base} linha {n}: {len(lin)} colunas, esperado {len(cab)}")
            registros.append(dict(zip(cab, lin, strict=True)))
        out[entidade] = (cab, registros, data)
    return out


def package_checksum(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for nome in sorted(files):
        h.update(nome.encode())
        h.update(hashlib.sha256(files[nome]).digest())
    return h.hexdigest()


# ======================================================================== metadados
class _Meta:
    """Gravações de metadados em transações próprias (sobrevivem a falhas)."""

    def __init__(self, ctx: PipelineContext) -> None:
        self.ctx = ctx

    def session(self) -> Session:
        s = PipelineSession()
        bind_tenant(s, self.ctx.tenant_id)
        return s

    def update_run(self, run_id: int, **campos) -> None:
        with self.session() as s:
            r = s.get(IngestionRun, run_id)
            for k, v in campos.items():
                setattr(r, k, v)
            s.commit()

    def step(self, prun_id: int, stage: str, status: str, t0: float, **info) -> None:
        with self.session() as s:
            p = s.get(PipelineRun, prun_id)
            p.steps = [*(p.steps or []), {"stage": stage, "status": status,
                                          "ms": int((time.perf_counter() - t0) * 1000), **info}]
            p.layer = stage
            s.commit()
        log.info("pipeline.step", extra={"stage": stage, "status": status, **self.ctx.log_fields()})


# ======================================================================== execução
def run_file_ingestion(*, tenant_id: str, source_connection_id: int, files: dict[str, bytes],
                       triggered_by: str, max_bytes: int, max_files: int) -> RunSummary:
    ctx = PipelineContext(tenant_id=tenant_id, source_connection_id=source_connection_id,
                          triggered_by=triggered_by)
    meta = _Meta(ctx)
    with meta.session() as s:
        require_active_tenant(s, tenant_id)
        conn = s.get(SourceConnection, source_connection_id)
        if conn is None:  # RLS: fonte de outro tenant é invisível
            raise PipelineError("fonte inexistente neste tenant")
        if conn.source_type != "FILE" or conn.status != "ACTIVE":
            raise PipelineError("fonte não é um arquivo ativo")
        mapping = load_connection_mapping(conn.configuration or {})
        checksum = package_checksum(files)
        anterior = s.execute(select(IngestionRun).where(
            IngestionRun.source_connection_id == conn.id, IngestionRun.checksum == checksum,
            IngestionRun.stage == "AVAILABLE").order_by(IngestionRun.id.desc())).scalars().first()
        run = IngestionRun(tenant_id=tenant_id, source_connection_id=conn.id,
                           source_system=conn.source_system, status="RUNNING", checksum=checksum,
                           triggered_by=triggered_by, mapping_ref=mapping.ref,
                           correlation_id=ctx.correlation_id, error_summary={})
        s.add(run)
        s.flush()
        prun = PipelineRun(tenant_id=tenant_id, ingestion_run_id=run.id, source_connection_id=conn.id,
                           layer="ingestion", status="RUNNING", triggered_by=triggered_by,
                           correlation_id=ctx.correlation_id, steps=[])
        s.add(prun)
        conn.last_run_at = datetime.now(UTC)
        s.commit()
        source_system = conn.source_system
    ctx = ctx.with_runs(pipeline_run_id=prun.id, ingestion_run_id=run.id)
    meta.ctx = ctx
    summary = RunSummary(run.id, prun.id, "RUNNING", None)

    with log_context(**ctx.log_fields()):
        log.info("pipeline.start", extra={"files": sorted(files)})
        try:
            if anterior is not None:
                return _finish_duplicate(meta, ctx, summary, anterior.id)
            return _execute(meta, ctx, mapping, files, summary, checksum, source_system,
                            max_bytes=max_bytes, max_files=max_files)
        except Exception as e:  # noqa: BLE001 — registra e devolve status honesto
            seguro = str(e)[:300] if isinstance(e, PipelineError) else "erro interno do pipeline"
            log.exception("pipeline.erro")
            _fail(meta, ctx, summary, seguro, stage=summary.stage)
            return summary


def _finish_duplicate(meta: _Meta, ctx: PipelineContext, summary: RunSummary, anterior: int) -> RunSummary:
    msg = f"pacote idêntico à ingestão #{anterior} — nada a reprocessar (idempotência por checksum)"
    meta.update_run(ctx.ingestion_run_id, status="SUCCESS", stage="AVAILABLE", duplicate_of=anterior,
                    finished_at=datetime.now(UTC), error_summary={"nota": msg})
    meta.step(ctx.pipeline_run_id, "duplicate_check", "SKIPPED", time.perf_counter(), duplicate_of=anterior)
    _close_pipeline(meta, ctx, "SUCCESS")
    summary.status, summary.stage, summary.duplicate_of, summary.message = "SUCCESS", "AVAILABLE", anterior, msg
    _audit(meta, ctx, "pipeline.ingestion_duplicate", "success", {"duplicate_of": anterior})
    return summary


def _execute(meta, ctx, mapping, files, summary, checksum, source_system, *, max_bytes, max_files):
    storage = get_raw_storage()

    # 1. arquivos ------------------------------------------------------------------
    t0 = time.perf_counter()
    parsed = validate_files(mapping, files, max_bytes=max_bytes, max_files=max_files)
    meta.step(ctx.pipeline_run_id, "file_validation", "OK", t0, arquivos=len(parsed))

    # 2. RAW (imutável) --------------------------------------------------------------
    t0 = time.perf_counter()
    with meta.session() as s:
        for entidade, (_cab, linhas, data) in parsed.items():
            ref = storage.put(raw_key(ctx.tenant_id, ctx.source_connection_id, entidade,
                                      ctx.ingestion_run_id, f"{entidade}.csv"), data)
            s.add(RawObject(tenant_id=ctx.tenant_id, source_connection_id=ctx.source_connection_id,
                            ingestion_run_id=ctx.ingestion_run_id, source_entity=entidade,
                            storage_key=ref.key, file_name=f"{entidade}.csv", size_bytes=ref.size,
                            sha256=ref.sha256, records=len(linhas)))
        run = s.get(IngestionRun, ctx.ingestion_run_id)
        run.stage = "RECEIVED"
        run.records_received = sum(len(v[1]) for v in parsed.values())
        s.commit()
        onboarding.advance(s, ctx.tenant_id, "RAW_LOADED", by=ctx.triggered_by)
        s.commit()
    summary.stage, summary.received = "RECEIVED", sum(len(v[1]) for v in parsed.values())
    meta.step(ctx.pipeline_run_id, "raw", "OK", t0, registros=summary.received)

    # 3. mapping → canônico --------------------------------------------------------
    t0 = time.perf_counter()
    results: dict[str, EntityResult] = {}
    for entidade, (cab, linhas, _d) in parsed.items():
        em = mapping.by_source(entidade)
        res = apply_entity(mapping, em, linhas, cab)
        for mr in res.rows:
            mr.values = derive_canonical(em.target_entity, mr.values)
        results[em.target_entity] = res
    meta.step(ctx.pipeline_run_id, "mapping", "OK", t0, mapping=mapping.ref)

    # 4. Data Quality (gate) — antes de qualquer promoção -------------------------
    t0 = time.perf_counter()
    with meta.session() as s:
        existentes = existing_codes(s, ctx.tenant_id)
    business_keys = {e: ENTITIES[e].business_key for e in LOAD_ORDER}
    report = quality.evaluate(mapping, results, {m.source_entity for m in mapping.entities
                                                 if m.source_entity in parsed},
                              existentes, business_keys, LOAD_ORDER)
    _persist_dq(meta, ctx, report)
    summary.errors, summary.warnings = report.errors, report.warnings
    summary.rejected = sum(len(q.rejected_lines) for q in report.entities.values())
    summary.valid = sum(len(q.valid_rows) for q in report.entities.values())
    summary.entities = {e: {"recebidas": q.received, "validas": len(q.valid_rows),
                            "rejeitadas": len(q.rejected_lines), "duplicadas": q.duplicates_removed}
                        for e, q in report.entities.items()}
    meta.update_run(ctx.ingestion_run_id, records_valid=summary.valid,
                    records_rejected=summary.rejected, warnings_count=summary.warnings,
                    errors_count=summary.errors)
    if report.blocked:
        meta.step(ctx.pipeline_run_id, "data_quality", "BLOCKED", t0, erros=summary.errors)
        bloqueios = [f.description for f in report.findings if f.blocking][:5]
        _fail(meta, ctx, summary, "Data Quality bloqueou a promoção", stage="RECEIVED",
              detalhes={"bloqueios": bloqueios})
        return summary
    meta.step(ctx.pipeline_run_id, "data_quality", "OK", t0, erros=summary.errors, avisos=summary.warnings)
    with meta.session() as s:
        onboarding.advance(s, ctx.tenant_id, "MAPPING_VALIDATED", by=ctx.triggered_by)
        onboarding.advance(s, ctx.tenant_id, "DATA_QUALITY_VALIDATED", by=ctx.triggered_by)
        s.commit()
    summary.stage = "VALIDATED"
    meta.update_run(ctx.ingestion_run_id, stage="VALIDATED")

    # 5. publicação transacional: Silver → Gold → readiness → reconciliação ---------
    validas = {e: q.valid_rows for e, q in report.entities.items()}
    meses = {r["competencia"] for e in ("evento_assistencial", "receita") for r in validas.get(e, [])}
    ref_inicio = min(meses) if meses else date.today().replace(day=1)
    ref_fim = max(meses) if meses else date.today().replace(day=1)
    t0 = time.perf_counter()
    data_s = PipelineSession()
    try:
        bind_tenant(data_s, ctx.tenant_id)
        loader = SilverLoader(data_s, ctx, source_system)
        loader.ensure_competencias(meses)
        etapas = {
            "especialidade": loader.especialidades, "plano": loader.planos,
            "contrato": loader.contratos, "prestador": loader.prestadores,
            "procedimento": loader.procedimentos,
            "beneficiario": lambda rows: loader.beneficiarios(rows, ref_inicio, ref_fim),
            "receita": loader.receitas, "evento_assistencial": loader.eventos,
        }
        for entidade in LOAD_ORDER:
            if validas.get(entidade):
                etapas[entidade](validas[entidade])
        data_s.flush()
        meta.step(ctx.pipeline_run_id, "silver", "OK", t0, inseridos=loader.stats.inserted,
                  atualizados=loader.stats.updated, removidos=loader.stats.deleted)

        t1 = time.perf_counter()
        gold = rebuild_aggregations(data_s, tenant_id=ctx.tenant_id)
        prontidao = readiness.refresh(data_s, ctx.tenant_id)
        meta.step(ctx.pipeline_run_id, "gold", "OK", t1, linhas=gold)
        summary.stage = "PROCESSED"

        t2 = time.perf_counter()
        checks = reconciliation.reconcile(
            data_s, ctx.tenant_id, ctx.ingestion_run_id,
            eventos=validas.get("evento_assistencial", []), receitas=validas.get("receita", []),
            beneficiarios=validas.get("beneficiario", []),
            received={e: q.received for e, q in report.entities.items()},
            rejected={e: len(q.rejected_lines) for e, q in report.entities.items()},
            duplicates={e: q.duplicates_removed for e, q in report.entities.items()},
            fin_tol=mapping.financial_tolerance_abs, count_tol=mapping.count_tolerance_abs)
        resultado = reconciliation.overall(checks)
        summary.reconciliation = resultado
        _persist_recon(meta, ctx, checks)
        meta.step(ctx.pipeline_run_id, "reconciliation", resultado, t2, verificacoes=len(checks))
        if resultado == reconciliation.FAIL:
            data_s.rollback()
            _fail(meta, ctx, summary, "Reconciliação reprovou a carga — nada foi publicado",
                  stage="PROCESSED",
                  detalhes={"falhas": [c.as_dict() for c in checks if c.status == "FAIL"][:5]})
            return summary
        data_s.commit()  # publicação atômica (Silver + Gold + readiness)
    finally:
        data_s.close()

    status = "PARTIAL" if summary.rejected else "SUCCESS"
    meta.update_run(ctx.ingestion_run_id, status=status, stage="AVAILABLE", finished_at=datetime.now(UTC),
                    competencia_inicio=min(meses) if meses else None,
                    competencia_fim=max(meses) if meses else None,
                    records_inserted=sum(loader.stats.inserted.values()),
                    records_updated=sum(loader.stats.updated.values()))
    with meta.session() as s:
        for estado in ("SILVER_READY", "GOLD_READY", "RECONCILED"):
            onboarding.advance(s, ctx.tenant_id, estado, by=ctx.triggered_by)
        if any(r.ready for r in prontidao.values() if r.feature_key != "custom_branding"):
            onboarding.advance(s, ctx.tenant_id, "CAPABILITIES_READY", by=ctx.triggered_by)
        conn = s.get(SourceConnection, ctx.source_connection_id)
        conn.last_success_at = datetime.now(UTC)
        s.commit()
    _close_pipeline(meta, ctx, status)
    summary.status, summary.stage = status, "AVAILABLE"
    summary.message = ("carga publicada" if status == "SUCCESS"
                       else f"carga publicada com {summary.rejected} linha(s) rejeitada(s)")
    _audit(meta, ctx, "pipeline.ingestion_completed", "success",
           {"status": status, "recebidas": summary.received, "validas": summary.valid,
            "rejeitadas": summary.rejected, "reconciliacao": resultado})
    log.info("pipeline.fim", extra={"status": status, **ctx.log_fields()})
    return summary


def _persist_dq(meta: _Meta, ctx: PipelineContext, report) -> None:
    with meta.session() as s:
        for f in report.findings:
            s.add(DataQualityResult(
                tenant_id=ctx.tenant_id, pipeline_run_id=ctx.pipeline_run_id,
                ingestion_run_id=ctx.ingestion_run_id, rule_id=f.rule_id[:60],
                rule_description=f.description[:300], entity=f.entity, severity=f.severity,
                blocking=f.blocking, records_checked=f.checked, records_failed=f.failed,
                sample={"referencias": f.sample}))
        s.commit()


def _persist_recon(meta: _Meta, ctx: PipelineContext, checks) -> None:
    with meta.session() as s:
        for c in checks:
            s.add(ReconciliationResult(
                tenant_id=ctx.tenant_id, pipeline_run_id=ctx.pipeline_run_id,
                ingestion_run_id=ctx.ingestion_run_id, check_id=c.check_id, entity=c.entity,
                scope=c.scope, expected=c.expected, actual=c.actual, difference=c.difference,
                tolerance=c.tolerance, status=c.status))
        s.commit()


def _close_pipeline(meta: _Meta, ctx: PipelineContext, status: str) -> None:
    with meta.session() as s:
        p = s.get(PipelineRun, ctx.pipeline_run_id)
        p.status = status
        p.finished_at = datetime.now(UTC)
        s.commit()


def _fail(meta: _Meta, ctx: PipelineContext, summary: RunSummary, msg: str, *,
          stage: str | None, detalhes: dict | None = None) -> None:
    resumo = {"erro": msg, "correlation_id": ctx.correlation_id, **(detalhes or {})}
    meta.update_run(ctx.ingestion_run_id, status="FAILED", stage=stage,
                    finished_at=datetime.now(UTC), error_message=msg[:500], error_summary=resumo)
    with meta.session() as s:
        conn = s.get(SourceConnection, ctx.source_connection_id)
        if conn is not None:
            conn.last_error_at = datetime.now(UTC)
            conn.last_error_summary = msg[:300]
        s.commit()
    _close_pipeline(meta, ctx, "FAILED")
    summary.status, summary.stage, summary.message = "FAILED", stage, msg
    _audit(meta, ctx, "pipeline.ingestion_failed", "failure", {"motivo": msg})
    log.warning("pipeline.falhou", extra={"motivo": msg, **ctx.log_fields()})


def _audit(meta: _Meta, ctx: PipelineContext, action: str, outcome: str, details: dict) -> None:
    with meta.session() as s:
        audit.add(s, action, actor=audit.Actor(email=ctx.triggered_by[:254], role="PIPELINE"),
                  tenant_id=ctx.tenant_id, entity_type="ingestion_run",
                  entity_id=ctx.ingestion_run_id, outcome=outcome,
                  details={**details, "correlation_id": ctx.correlation_id,
                           "source_connection_id": ctx.source_connection_id})
        s.commit()
