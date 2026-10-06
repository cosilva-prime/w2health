"""Fase 3 — fila do pipeline e presença do worker.

* `pipeline_jobs` (control plane, sem RLS — só ids técnicos): fila durável consumida com
  `FOR UPDATE SKIP LOCKED`, com tentativas, lease, backoff e motivo de falha;
* `worker_heartbeats`: presença dos workers (health/observabilidade);
* `ingestion_runs.status` aceita `QUEUED` e `CANCELLED` (mesmo vocabulário do job);
* grants mínimos: runtime (`w2health_app`) só LÊ a fila; pipeline (`w2health_pipeline`)
  enfileira, consome e atualiza;
* endurecimento: `CREATE` no schema public revogado de PUBLIC (já é o padrão do
  PostgreSQL ≥ 15 — explícito aqui para bancos antigos/gerenciados).

Aditiva: nada é apagado. Ingestões antigas não ganham job (já estão concluídas).

Revision ID: b8e9f0a1c2d3
Revises: a7d8e9f0b1c2
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8e9f0a1c2d3"
down_revision: str | None = "a7d8e9f0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_RE = re.compile(r"^[a-z_][a-z0-9_]{2,62}$")


def _role(env: str, default: str) -> str:
    r = os.environ.get(env, default)
    if not _ROLE_RE.match(r):
        raise RuntimeError(f"{env} inválido")
    return r


def _existe(role: str) -> bool:
    return bool(op.get_bind().exec_driver_sql(f"SELECT 1 FROM pg_roles WHERE rolname = '{role}'").first())


def upgrade() -> None:
    op.create_table(
        "pipeline_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_type", sa.String(40), nullable=False),
        sa.Column("tenant_id", sa.String(40), nullable=False),
        sa.Column("source_connection_id", sa.BigInteger(), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
        sa.Column("pipeline_run_id", sa.BigInteger(), nullable=False),
        sa.Column("dedup_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), server_default="QUEUED", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_by", sa.String(120), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(300), nullable=True),
        sa.Column("error_class", sa.String(20), nullable=True),
        sa.Column("correlation_id", sa.String(40), nullable=True),
        sa.Column("records_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_valid", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_rejected", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_reason", sa.String(40), nullable=True),
        sa.Column("created_by", sa.String(254), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('QUEUED', 'RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED', 'CANCELLED')",
                           name="ck_pipeline_jobs_status_valido"),
        sa.CheckConstraint("job_type IN ('file_ingestion')", name="ck_pipeline_jobs_tipo_valido"),
        sa.CheckConstraint("error_class IS NULL OR error_class IN ('retryable', 'definitive')",
                           name="ck_pipeline_jobs_classe_erro_valida"),
        sa.CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="ck_pipeline_jobs_tentativas_validas"),
        sa.PrimaryKeyConstraint("id", name="pk_pipeline_jobs"),
        sa.UniqueConstraint("dedup_key", name="uq_pipeline_jobs_dedup_key"),
    )
    op.create_index("ix_pipeline_jobs_tenant_id", "pipeline_jobs", ["tenant_id"])
    op.create_index("ix_pipeline_jobs_status_next_attempt_at", "pipeline_jobs", ["status", "next_attempt_at"])
    op.create_index("ix_pipeline_jobs_ingestion_run_id", "pipeline_jobs", ["ingestion_run_id"])
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(120), nullable=False),
        sa.Column("hostname", sa.String(120), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("current_job_id", sa.BigInteger(), nullable=True),
        sa.Column("jobs_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_failed", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("worker_id", name="pk_worker_heartbeats"),
    )
    op.drop_constraint("ck_ingestion_runs_status_valido", "ingestion_runs", type_="check")
    op.create_check_constraint(
        "ck_ingestion_runs_status_valido", "ingestion_runs",
        "status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED', 'CANCELLED')")

    app = _role("APP_DB_ROLE", "w2health_app")
    if _existe(app):
        op.execute(f"GRANT SELECT ON pipeline_jobs, worker_heartbeats TO {app}")
    pipe = _role("PIPELINE_DB_ROLE", "w2health_pipeline")
    if _existe(pipe):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON pipeline_jobs TO {pipe}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON worker_heartbeats TO {pipe}")
        op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {pipe}")
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")


def downgrade() -> None:
    op.execute("UPDATE ingestion_runs SET status = 'FAILED', error_message = 'downgrade: fila removida' "
               "WHERE status IN ('QUEUED', 'CANCELLED')")
    op.drop_constraint("ck_ingestion_runs_status_valido", "ingestion_runs", type_="check")
    op.create_check_constraint(
        "ck_ingestion_runs_status_valido", "ingestion_runs",
        "status IN ('PENDING', 'RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED')")
    op.drop_table("worker_heartbeats")
    op.drop_index("ix_pipeline_jobs_ingestion_run_id", table_name="pipeline_jobs")
    op.drop_index("ix_pipeline_jobs_status_next_attempt_at", table_name="pipeline_jobs")
    op.drop_index("ix_pipeline_jobs_tenant_id", table_name="pipeline_jobs")
    op.drop_table("pipeline_jobs")
