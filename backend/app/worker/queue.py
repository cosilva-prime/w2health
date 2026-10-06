"""Fila de jobs — interface + implementação em PostgreSQL.

Escolha (docs/WORKER_AND_QUEUE.md §Decisão): **PostgreSQL com `FOR UPDATE SKIP LOCKED`**.
O banco já é infraestrutura obrigatória; a fila fica transacional com o resto (a ingestão e
o job nascem no MESMO commit — sem job órfão nem ingestão sem job), durável, auditável e
visível ao Admin sem um segundo sistema. Volume esperado (dezenas de cargas/dia por
cliente) está muito abaixo do limite do padrão. O domínio depende só de `JobQueue`; um
adapter Redis/RQ/SQS pode substituir esta classe sem tocar no pipeline.

A tabela `pipeline_jobs` não tem RLS (o worker precisa enxergar a fila antes de ter um
tenant) e por isso carrega apenas ids técnicos.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data_platform.runner import JobRef
from app.db.pipeline import PipelineSession

_COLS = (
    "id, tenant_id, source_connection_id, ingestion_run_id, pipeline_run_id, attempts, "
    "max_attempts, created_by, correlation_id"
)


@dataclass(frozen=True)
class Claimed:
    job: JobRef
    max_attempts: int


@dataclass(frozen=True)
class Reaped:
    job: JobRef
    max_attempts: int
    requeued: bool
    reason: str


class JobQueue(Protocol):
    def claim(
        self, worker_id: str, lease_seconds: int, *, job_id: int | None = None
    ) -> Claimed | None: ...
    def heartbeat(self, job_id: int, worker_id: str, lease_seconds: int) -> bool: ...
    def finish(
        self,
        job_id: int,
        worker_id: str,
        status: str,
        *,
        error: str | None = None,
        error_class: str | None = None,
        counts: tuple[int, int, int] | None = None,
        failure_reason: str | None = None,
    ) -> None: ...
    def retry_later(self, job_id: int, worker_id: str, error: str, delay_seconds: int) -> None: ...
    def reap(self, max_runtime_seconds: int, backoff: Callable[[int], int]) -> list[Reaped]: ...
    def depth(self) -> int: ...


def _ref(row) -> Claimed:
    return Claimed(
        JobRef(
            job_id=row.id,
            tenant_id=row.tenant_id,
            source_connection_id=row.source_connection_id,
            ingestion_run_id=row.ingestion_run_id,
            pipeline_run_id=row.pipeline_run_id,
            attempt=row.attempts,
            created_by=row.created_by,
            correlation_id=row.correlation_id,
        ),
        row.max_attempts,
    )


class PostgresJobQueue:
    def __init__(self, session_factory: Callable[[], Session] = PipelineSession) -> None:
        self._s = session_factory

    def claim(
        self, worker_id: str, lease_seconds: int, *, job_id: int | None = None
    ) -> Claimed | None:
        filtro = "AND id = :jid " if job_id is not None else ""
        sql = text(f"""
            UPDATE pipeline_jobs SET status = 'RUNNING', locked_by = :w, heartbeat_at = now(),
                   lease_expires_at = now() + make_interval(secs => :lease),
                   attempts = attempts + 1, started_at = now(), last_error = NULL,
                   error_class = NULL
             WHERE id = (SELECT id FROM pipeline_jobs
                          WHERE status = 'QUEUED' AND next_attempt_at <= now() {filtro}
                          ORDER BY next_attempt_at, id
                          FOR UPDATE SKIP LOCKED LIMIT 1)
            RETURNING {_COLS}""")
        with self._s() as s:
            row = s.execute(sql, {"w": worker_id, "lease": lease_seconds, "jid": job_id}).first()
            s.commit()
        return _ref(row) if row else None

    def heartbeat(self, job_id: int, worker_id: str, lease_seconds: int) -> bool:
        with self._s() as s:
            n = s.execute(
                text(
                    "UPDATE pipeline_jobs SET heartbeat_at = now(), "
                    "lease_expires_at = now() + make_interval(secs => :lease) "
                    "WHERE id = :id AND locked_by = :w AND status = 'RUNNING'"
                ),
                {"id": job_id, "w": worker_id, "lease": lease_seconds},
            ).rowcount
            s.commit()
        return n == 1

    def finish(
        self,
        job_id: int,
        worker_id: str,
        status: str,
        *,
        error: str | None = None,
        error_class: str | None = None,
        counts: tuple[int, int, int] | None = None,
        failure_reason: str | None = None,
    ) -> None:
        rec, val, rej = counts or (0, 0, 0)
        with self._s() as s:
            s.execute(
                text(
                    "UPDATE pipeline_jobs SET status = :st, finished_at = now(), locked_by = NULL, "
                    "lease_expires_at = NULL, last_error = :e, error_class = :c, "
                    "failure_reason = :fr, "
                    "records_received = :rec, records_valid = :val, records_rejected = :rej "
                    "WHERE id = :id AND locked_by = :w AND status = 'RUNNING'"
                ),
                {
                    "st": status,
                    "id": job_id,
                    "w": worker_id,
                    "e": (error or None) and error[:300],
                    "c": error_class,
                    "fr": failure_reason,
                    "rec": rec,
                    "val": val,
                    "rej": rej,
                },
            )
            s.commit()

    def retry_later(self, job_id: int, worker_id: str, error: str, delay_seconds: int) -> None:
        with self._s() as s:
            s.execute(
                text(
                    "UPDATE pipeline_jobs SET status = 'QUEUED', locked_by = NULL, "
                    "lease_expires_at = NULL, "
                    "next_attempt_at = now() + make_interval(secs => :d), last_error = :e, "
                    "error_class = 'retryable' "
                    "WHERE id = :id AND locked_by = :w AND status = 'RUNNING'"
                ),
                {"id": job_id, "w": worker_id, "e": error[:300], "d": delay_seconds},
            )
            s.commit()

    def reap(self, max_runtime_seconds: int, backoff: Callable[[int], int]) -> list[Reaped]:
        """Jobs RUNNING com lease vencido (worker morreu/travou) ou além do tempo máximo:
        voltam para a fila (se ainda há tentativas) ou falham. Seguro com várias réplicas
        (SKIP LOCKED)."""
        out: list[Reaped] = []
        with self._s() as s:
            rows = s.execute(
                text(f"""
                SELECT {_COLS}, (lease_expires_at < now()) AS lease_vencido
                  FROM pipeline_jobs
                 WHERE status = 'RUNNING'
                   AND (lease_expires_at < now() OR started_at < now() - make_interval(secs => :mx))
                 FOR UPDATE SKIP LOCKED"""),
                {"mx": max_runtime_seconds},
            ).all()
            for r in rows:
                motivo = (
                    "worker parou de responder (lease expirado)"
                    if r.lease_vencido
                    else f"tempo máximo de execução excedido ({max_runtime_seconds}s)"
                )
                if r.attempts < r.max_attempts:
                    s.execute(
                        text(
                            "UPDATE pipeline_jobs SET status = 'QUEUED', locked_by = NULL, "
                            "lease_expires_at = NULL, "
                            "next_attempt_at = now() + make_interval(secs => :d), "
                            "last_error = :e, error_class = 'retryable' WHERE id = :id"
                        ),
                        {"id": r.id, "e": motivo, "d": backoff(r.attempts)},
                    )
                    out.append(Reaped(_ref(r).job, r.max_attempts, True, motivo))
                else:
                    s.execute(
                        text(
                            "UPDATE pipeline_jobs SET status = 'FAILED', locked_by = NULL, "
                            "lease_expires_at = NULL, finished_at = now(), last_error = :e, "
                            "error_class = 'retryable', failure_reason = 'lease_expired' "
                            "WHERE id = :id"
                        ),
                        {"id": r.id, "e": motivo + " — tentativas esgotadas"},
                    )
                    out.append(Reaped(_ref(r).job, r.max_attempts, False, motivo))
            s.commit()
        return out

    def depth(self) -> int:
        with self._s() as s:
            return int(
                s.execute(
                    text("SELECT count(*) FROM pipeline_jobs WHERE status = 'QUEUED'")
                ).scalar_one()
            )
