"""Worker do pipeline — consome a fila e processa um job por vez.

Regras de isolamento (CRÍTICAS — testadas em tests/test_worker.py):
* cada job reconstrói o `PipelineContext` a partir dos ids do job (`runner.job_context`);
* o contexto de log é SUBSTITUÍDO por job (`fresh_log_context`), nunca mesclado;
* as sessões de banco são novas por operação e amarradas ao tenant do job; o tenant vai
  ao PostgreSQL por `set_config(..., true)` (local à transação) — conexão reaproveitada do
  pool não carrega tenant de um job anterior;
* o worker não guarda estado de negócio entre jobs.

Política de erro (docs/WORKER_AND_QUEUE.md §Retry):
* DEFINITIVO (sem retry): erro de pipeline/mapping/validação, integridade do job ou do RAW,
  tenant inexistente/inativo, objeto RAW ausente. Desfechos de negócio (DQ bloqueou,
  reconciliação reprovou) nem são exceção: viram FAILED direto.
* RETENTÁVEL: banco/armazenamento indisponível, timeout, erro inesperado — até
  `max_attempts`, com backoff exponencial (base × 2^(n-1), teto configurável).
"""

from __future__ import annotations

import contextlib
import logging
import os
import socket
import threading
import time
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.config import get_settings
from app.core.logging import fresh_log_context
from app.core.tenant import TenantContextMissing
from app.data_platform import runner
from app.data_platform.context import PipelineError
from app.data_platform.mapping import MappingError
from app.data_platform.storage import RawStorageError, StorageUnavailable
from app.db.pipeline import PipelineSession
from app.worker.queue import Claimed, JobQueue, PostgresJobQueue

log = logging.getLogger("app.worker")

RETRYABLE, DEFINITIVE = "retryable", "definitive"


def classify(exc: BaseException) -> tuple[str, str]:
    """(classe, mensagem segura). Mensagens nunca carregam stack trace nem dado de linha."""
    if isinstance(exc, StorageUnavailable):
        return RETRYABLE, "armazenamento RAW indisponível"
    if isinstance(exc, (OperationalError,)) or (
        isinstance(exc, DBAPIError) and exc.connection_invalidated
    ):
        return RETRYABLE, "banco de dados indisponível"
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return RETRYABLE, "tempo esgotado / conexão perdida"
    if isinstance(exc, TenantContextMissing):
        return DEFINITIVE, "tenant do job inexistente"
    if isinstance(exc, (PipelineError, MappingError)):
        return DEFINITIVE, str(exc)[:300]
    if isinstance(exc, RawStorageError):  # chave inválida, objeto ausente, integridade
        return DEFINITIVE, "objeto RAW ausente ou inválido"
    return RETRYABLE, "erro interno do pipeline"


def _motivo(exc: BaseException, classe: str) -> str:
    from app.data_platform.runner import FileValidationError, JobIntegrityError, RawIntegrityError

    if isinstance(exc, FileValidationError):
        return "file_validation"
    if isinstance(exc, (JobIntegrityError, RawIntegrityError)):
        return "integrity"
    if classe == RETRYABLE and classify(exc)[1] != "erro interno do pipeline":
        return "infrastructure"
    return "internal"


class Worker:
    def __init__(self, worker_id: str | None = None, queue: JobQueue | None = None) -> None:
        self.settings = get_settings()
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self.queue = queue or PostgresJobQueue()
        self._ultimo_reap = 0.0
        self.processed = 0
        self.failed = 0

    # ------------------------------------------------------------------ política
    def backoff(self, attempt: int) -> int:
        s = self.settings
        return int(
            min(s.job_backoff_max_seconds, s.job_backoff_base_seconds * (2 ** max(attempt - 1, 0)))
        )

    # ------------------------------------------------------------------ ciclo
    def run_once(self) -> bool:
        """Recupera jobs abandonados (periodicamente) e processa no máximo um job."""
        self.reap_if_due()
        claimed = self.queue.claim(self.worker_id, self.settings.job_lease_seconds)
        if claimed is None:
            return False
        self._process(claimed)
        return True

    def run_job(self, job_id: int) -> bool:
        """Processa um job específico (CLI síncrona / testes) pelo mesmo caminho."""
        claimed = self.queue.claim(self.worker_id, self.settings.job_lease_seconds, job_id=job_id)
        if claimed is None:
            return False
        self._process(claimed)
        return True

    def drain(self, max_jobs: int = 1000) -> int:
        n = 0
        while n < max_jobs and self.run_once():
            n += 1
        return n

    def run_forever(self, stop: threading.Event | None = None) -> None:
        stop = stop or threading.Event()
        log.info("worker.start", extra={"event": "worker.start", "worker_id": self.worker_id})
        espera = self.settings.worker_poll_seconds
        while not stop.is_set():
            try:
                trabalhou = self.run_once()
                self.beat()
                espera = self.settings.worker_poll_seconds
            except Exception:  # noqa: BLE001 — o loop nunca morre por falha de infraestrutura
                log.exception("worker.loop_error", extra={"event": "worker.loop_error"})
                trabalhou = False
                espera = min(espera * 2, 30.0)  # banco/fila fora: recua sem martelar
            if not trabalhou:
                stop.wait(espera)
        log.info("worker.stop", extra={"event": "worker.stop", "worker_id": self.worker_id})

    # ------------------------------------------------------------------ recuperação
    def reap_if_due(self, force: bool = False) -> int:
        agora = time.monotonic()
        if not force and agora - self._ultimo_reap < max(self.settings.job_lease_seconds / 4, 5):
            return 0
        self._ultimo_reap = agora
        reaped = self.queue.reap(self.settings.job_max_runtime_seconds, self.backoff)
        for r in reaped:
            with fresh_log_context(
                job_id=r.job.job_id,
                tenant_id=r.job.tenant_id,
                ingestion_run_id=r.job.ingestion_run_id,
            ):
                log.warning(
                    "job.recovered",
                    extra={"event": "job.recovered", "requeued": r.requeued, "reason": r.reason},
                )
                try:
                    if r.requeued:
                        runner.requeue_ingestion(r.job, r.reason, r.job.attempt, r.max_attempts)
                    else:
                        runner.fail_ingestion(r.job, r.reason + " — tentativas esgotadas")
                except Exception:  # noqa: BLE001
                    log.exception("job.recover_error", extra={"event": "job.recover_error"})
        return len(reaped)

    # ------------------------------------------------------------------ processamento
    def _process(self, claimed: Claimed) -> None:
        job = claimed.job
        t0 = time.perf_counter()
        with fresh_log_context(
            job_id=job.job_id,
            tenant_id=job.tenant_id,
            correlation_id=job.correlation_id,
            ingestion_run_id=job.ingestion_run_id,
            pipeline_run_id=job.pipeline_run_id,
            source_connection_id=job.source_connection_id,
        ):
            log.info(
                "job.start",
                extra={"event": "job.start", "attempt": job.attempt, "worker_id": self.worker_id},
            )
            lease = self.settings.job_lease_seconds
            self._set_current(job.job_id)
            try:
                summary = runner.process_ingestion(
                    job, on_step=lambda: self.queue.heartbeat(job.job_id, self.worker_id, lease)
                )
                status = (
                    summary.status
                    if summary.status in ("SUCCESS", "PARTIAL", "FAILED", "CANCELLED")
                    else "FAILED"
                )
                falhou = status == "FAILED"
                self.queue.finish(
                    job.job_id,
                    self.worker_id,
                    status,
                    error=summary.message if falhou else None,
                    error_class=DEFINITIVE if falhou else None,
                    counts=(summary.received, summary.valid, summary.rejected),
                    failure_reason=(summary.failure_reason or "internal") if falhou else None,
                )
                self.processed += 1
                self.failed += int(falhou)
                log.info(
                    "job.finished",
                    extra={
                        "event": "job.finished",
                        "status": status,
                        "duration_ms": int((time.perf_counter() - t0) * 1000),
                    },
                )
            except Exception as exc:  # noqa: BLE001 — classificado e registrado sem stack ao usuário
                classe, msg = classify(exc)
                log.warning(
                    "job.error",
                    extra={
                        "event": "job.error",
                        "error_class": classe,
                        "error_type": type(exc).__name__,
                        "attempt": job.attempt,
                    },
                    exc_info=classe == RETRYABLE and msg == "erro interno do pipeline",
                )
                if classe == RETRYABLE and job.attempt < claimed.max_attempts:
                    atraso = self.backoff(job.attempt)
                    runner.requeue_ingestion(job, msg, job.attempt, claimed.max_attempts)
                    self.queue.retry_later(job.job_id, self.worker_id, msg, atraso)
                    log.info(
                        "job.retry_scheduled",
                        extra={
                            "event": "job.retry_scheduled",
                            "delay_s": atraso,
                            "attempt": job.attempt,
                        },
                    )
                else:
                    final = msg if classe == DEFINITIVE else f"{msg} — tentativas esgotadas"
                    runner.fail_ingestion(job, final)
                    self.queue.finish(
                        job.job_id,
                        self.worker_id,
                        "FAILED",
                        error=final,
                        error_class=classe,
                        failure_reason=_motivo(exc, classe),
                    )
                    self.failed += 1
                    log.info(
                        "job.finished",
                        extra={
                            "event": "job.finished",
                            "status": "FAILED",
                            "duration_ms": int((time.perf_counter() - t0) * 1000),
                        },
                    )
            finally:
                self._set_current(None)

    # ------------------------------------------------------------------ presença / health
    def _set_current(self, job_id: int | None) -> None:
        self._current = job_id

    def beat(self) -> None:
        """Heartbeat do processo: arquivo local (healthcheck do contêiner) + linha no banco."""
        with contextlib.suppress(OSError):
            Path(self.settings.worker_heartbeat_file).write_text(str(int(time.time())))
        with PipelineSession() as s:
            s.execute(
                text(
                    "INSERT INTO worker_heartbeats (worker_id, hostname, started_at, last_seen_at, "
                    "current_job_id, jobs_processed, jobs_failed) "
                    "VALUES (:w, :h, now(), now(), :j, :p, :f) "
                    "ON CONFLICT (worker_id) DO UPDATE SET last_seen_at = now(), "
                    "current_job_id = :j, "
                    "jobs_processed = :p, jobs_failed = :f"
                ),
                {
                    "w": self.worker_id,
                    "h": socket.gethostname()[:120],
                    "j": getattr(self, "_current", None),
                    "p": self.processed,
                    "f": self.failed,
                },
            )
            s.commit()


def healthcheck(max_age_seconds: int = 120) -> bool:
    """Liveness do worker para o contêiner: o loop atualizou o heartbeat recentemente."""
    p = Path(get_settings().worker_heartbeat_file)
    try:
        return time.time() - int(p.read_text().strip() or 0) <= max_age_seconds
    except (OSError, ValueError):
        return False
