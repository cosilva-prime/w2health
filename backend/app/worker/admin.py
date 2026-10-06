"""Ações administrativas sobre a fila (retry / cancel) — chamadas pela API, auditadas lá.

Transições CONDICIONAIS (UPDATE ... WHERE status = <esperado>): se o worker mudou o estado
no meio do caminho, nada acontece e a API responde conflito — não há corrida que reabra um
job concluído ou cancele um job que já começou.
"""

from __future__ import annotations

from sqlalchemy import text

from app.data_platform import runner
from app.db.pipeline import PipelineSession
from app.worker.queue import _COLS, _ref


def admin_requeue(job_id: int, *, by: str) -> bool:
    """FAILED por infraestrutura, ou RUNNING com lease vencido (travado) → QUEUED agora,
    com uma tentativa adicional."""
    with PipelineSession() as s:
        row = s.execute(
            text(f"""
            UPDATE pipeline_jobs SET status = 'QUEUED', next_attempt_at = now(), locked_by = NULL,
                   lease_expires_at = NULL, finished_at = NULL, max_attempts = attempts + 1,
                   last_error = :e, error_class = NULL
             WHERE id = :id AND (
                   (status = 'FAILED' AND error_class = 'retryable')
                OR (status = 'RUNNING' AND lease_expires_at < now()))
            RETURNING {_COLS}"""),
            {"id": job_id, "e": f"reenfileirado por {by[:120]}"},
        ).first()
        s.commit()
    if row is None:
        return False
    c = _ref(row)
    runner.requeue_ingestion(
        c.job, f"reenfileirado manualmente por {by[:120]}", c.job.attempt, c.max_attempts
    )
    return True


def admin_cancel(job_id: int, *, by: str) -> bool:
    with PipelineSession() as s:
        row = s.execute(
            text(f"""
            UPDATE pipeline_jobs SET status = 'CANCELLED', finished_at = now(), last_error = :e
             WHERE id = :id AND status = 'QUEUED'
            RETURNING {_COLS}"""),
            {"id": job_id, "e": f"cancelado por {by[:120]}"},
        ).first()
        s.commit()
    if row is None:
        return False
    runner.cancel_ingestion(_ref(row).job, by)
    return True
