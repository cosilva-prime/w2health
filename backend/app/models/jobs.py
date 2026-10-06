"""Fila de jobs do pipeline (Fase 3) — control plane, sem RLS.

A fila precisa ser lida pelo worker ANTES de existir um tenant de contexto (é o job que diz
qual tenant processar). Por isso a tabela não tem RLS e carrega **somente identificadores
técnicos** — nunca payload de arquivo, linha ou dado assistencial:

    tenant_id · source_connection_id · ingestion_run_id · pipeline_run_id

O worker reconstrói o `PipelineContext` a partir desses ids e valida, já sob RLS do tenant
do job, que a ingestão pertence a ele (job adulterado falha). Detalhe:
docs/WORKER_AND_QUEUE.md.

Vocabulário de status — o MESMO de `ingestion_runs.status` (não há duas máquinas de estado:
`ingestion_runs` diz o resultado do dado; o job acrescenta tentativas, lease e erro técnico):

    QUEUED → RUNNING → SUCCESS | PARTIAL | FAILED | CANCELLED
               ↑  └── (erro retentável) → QUEUED (backoff)
               └───── (lease expirado / worker caiu) → QUEUED ou FAILED
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import ControlBase

JOB_STATUS = ("QUEUED", "RUNNING", "SUCCESS", "PARTIAL", "FAILED", "CANCELLED")
JOB_TERMINAL = ("SUCCESS", "PARTIAL", "FAILED", "CANCELLED")
JOB_TYPES = ("file_ingestion",)
FAILURE_REASONS = (
    "dq_blocked",
    "reconciliation_failed",
    "file_validation",
    "integrity",
    "infrastructure",
    "internal",
    "lease_expired",
)
ERROR_CLASSES = ("retryable", "definitive")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class PipelineJob(ControlBase):
    __tablename__ = "pipeline_jobs"
    __table_args__ = (
        CheckConstraint(_in("status", JOB_STATUS), name="status_valido"),
        CheckConstraint(_in("job_type", JOB_TYPES), name="tipo_valido"),
        CheckConstraint(
            "error_class IS NULL OR " + _in("error_class", ERROR_CLASSES), name="classe_erro_valida"
        ),
        CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="tentativas_validas"),
        # índice da reivindicação (claim) e do reaper
        Index("ix_pipeline_jobs_status_next_attempt_at", "status", "next_attempt_at"),
        Index("ix_pipeline_jobs_ingestion_run_id", "ingestion_run_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(40))
    # identificadores técnicos — o worker revalida todos contra o banco sob RLS
    tenant_id: Mapped[str] = mapped_column(String(40), index=True)
    source_connection_id: Mapped[int] = mapped_column(BigInteger)
    ingestion_run_id: Mapped[int] = mapped_column(BigInteger)
    pipeline_run_id: Mapped[int] = mapped_column(BigInteger)
    # um job por ingestão: reenfileirar a mesma ingestão viola a unicidade (job duplicado)
    dedup_key: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", server_default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # mensagem SEGURA (sem stack trace, sem dado de linha) e classe do erro
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(20), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # contagens e motivo de falha (métricas sem dado de negócio)
    records_received: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    records_valid: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    records_rejected: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failure_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(254), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkerHeartbeat(ControlBase):
    """Presença dos workers (observabilidade e health) — sem dado de negócio."""

    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(120))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    current_job_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    jobs_processed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    jobs_failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
