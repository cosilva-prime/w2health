"""PipelineContext — tenant explícito do começo ao fim de uma execução de pipeline.

Um pipeline só começa depois que o tenant foi resolvido de forma explícita (parâmetro do
operador/CLI ou tenant-alvo de uma rota administrativa). Não existe execução "para todos
os clientes": cada `PipelineContext` carrega exatamente um tenant, e a sessão de banco do
pipeline é amarrada a ele (`bind_tenant` → RLS).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.tenant import TenantContextMissing
from app.models import Tenant

_CODE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")


class PipelineError(RuntimeError):
    """Falha de pipeline com mensagem segura para registrar/exibir."""


@dataclass(frozen=True)
class PipelineContext:
    tenant_id: str
    source_connection_id: int | None
    triggered_by: str  # e-mail do operador, "cli:<usuario>" ou "synthetic_generator"
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    pipeline_run_id: int | None = None
    ingestion_run_id: int | None = None
    job_id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, str) or not _CODE.match(self.tenant_id or ""):
            raise TenantContextMissing("pipeline sem tenant válido")
        if not self.triggered_by:
            raise PipelineError("pipeline sem responsável (triggered_by)")

    def with_runs(self, *, pipeline_run_id: int | None = None,
                  ingestion_run_id: int | None = None, job_id: int | None = None) -> PipelineContext:
        return PipelineContext(
            tenant_id=self.tenant_id, source_connection_id=self.source_connection_id,
            triggered_by=self.triggered_by, started_at=self.started_at,
            correlation_id=self.correlation_id,
            pipeline_run_id=pipeline_run_id or self.pipeline_run_id,
            ingestion_run_id=ingestion_run_id or self.ingestion_run_id,
            job_id=job_id or self.job_id,
        )

    def log_fields(self) -> dict:
        return {
            "tenant_id": self.tenant_id, "source_connection_id": self.source_connection_id,
            "pipeline_run_id": self.pipeline_run_id, "ingestion_run_id": self.ingestion_run_id,
            "correlation_id": self.correlation_id, "job_id": self.job_id,
        }


def require_active_tenant(session: Session, tenant_id: str) -> Tenant:
    """O tenant precisa existir e não estar INATIVO (SUSPENDED pode receber carga de
    homologação; INACTIVE não)."""
    t = session.get(Tenant, tenant_id)
    if t is None:
        raise TenantContextMissing("tenant inexistente para o pipeline")
    if t.status == "INACTIVE":
        raise PipelineError("tenant inativo não recebe cargas")
    return t
