"""Data Platform — modelo de controle de ingestão e o layout `receitas_contrato`.

**Estrutura, não uso.** Nenhum pipeline real roda na v1.2. Estas tabelas existem para:
  1. fixar o modelo tenant-aware que as integrações futuras vão preencher
     (ver `data_platform/` e `docs/DATA_PLATFORM_ARCHITECTURE.md`);
  2. dar aos testes de isolamento algo concreto para validar.

`Tenant` é o cadastro de clientes — pertence ao **control plane** (`ControlBase`) desde a
Fundação SaaS V1. As demais tabelas (data plane) rastreiam cargas por tenant.
`ReceitaContrato` é o **layout preparado** para receita no grão de contrato — criado e
documentado, mas **não populado nem lido pelo motor** nesta versão (receita por contrato
depende de regra de negócio ainda não validada — ver `docs/DISCOVERY_GESTAO_SAUDE.md`).
"""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ControlBase
from app.models._mixins import TenantMixin


class Tenant(ControlBase):
    """Cadastro de clientes (operadoras) — control plane.

    `id` é o **código** (slug) imutável do tenant e o valor gravado em `tenant_id` em todas
    as tabelas do data plane (ex.: `w2h-demo`). `uuid` é o identificador público estável.
    Decisão conservadora da Fundação SaaS V1: manter o slug como chave técnica evita
    reescrever 24 colunas/~330 mil linhas — ver `docs/DATABASE_EVOLUTION_V1.md`.
    """

    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE')", name="status_valido"
        ),
        CheckConstraint("id ~ '^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$'", name="codigo_valido"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # código/slug imutável
    uuid: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, unique=True, default=uuid_mod.uuid4, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(120))
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # Massa sintética (demonstração/testes) — exibido em toda a interface (transparência).
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def code(self) -> str:
        return self.id


class SourceConnection(TenantMixin, Base):
    """Uma fonte de dados de um cliente (MV, Tasy, Benner, ERP, arquivos, API...)."""

    __tablename__ = "source_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_system: Mapped[str] = mapped_column(String(60))  # rótulo livre do sistema de origem
    tipo: Mapped[str] = mapped_column(String(30))  # db_sql | api | arquivos | outro
    # Configuração NÃO sensível. Credenciais vão para `tenant_secrets` (cifradas) e aqui
    # entram só como referência (`{"secret_ref": "<chave>"}`) — ver app/saas/secrets.py.
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceEntity(TenantMixin, Base):
    """Mapeamento de uma entidade de origem para uma entidade canônica + estratégia de carga."""

    __tablename__ = "source_entities"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source_system", "source_entity", name="uq_srcent_tenant_sys_ent"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_system: Mapped[str] = mapped_column(String(60))
    source_entity: Mapped[str] = mapped_column(String(80))
    target_entity: Mapped[str] = mapped_column(String(60))  # entidade canônica W2Health
    load_strategy: Mapped[str] = mapped_column(String(20), default="FULL")
    business_key: Mapped[str] = mapped_column(String(200), default="")
    watermark_column: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at_column: Mapped[str | None] = mapped_column(String(80), nullable=True)
    deduplication_strategy: Mapped[str] = mapped_column(String(120), default="business_key")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class IngestionRun(TenantMixin, Base):
    """Uma execução de carga RAW de uma entidade de uma fonte."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|success|failed
    records_received: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    watermark: Mapped[str | None] = mapped_column(String(80), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(80), nullable=True)


class PipelineRun(TenantMixin, Base):
    """Uma execução de transformação entre camadas (raw→silver, silver→gold, gold→serving)."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    layer: Mapped[str] = mapped_column(String(20))  # raw | silver | gold | serving
    entity: Mapped[str] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    rows_in: Mapped[int] = mapped_column(Integer, default=0)
    rows_out: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)


class DataQualityResult(TenantMixin, Base):
    """Resultado da avaliação de uma regra de qualidade sobre uma entidade num run."""

    __tablename__ = "data_quality_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rule_id: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(10))  # ERROR | WARNING | INFO
    records_checked: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    sample: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReceitaContrato(TenantMixin, Base):
    """Layout preparado para receita no grão de contrato. **Não populado / não lido na v1.2.**

    Existe para que os conectores futuros já tenham um alvo canônico e para que
    `docs/CANONICAL_DATA_MODEL.md` / `data_platform/contracts/receita_contrato.yaml`
    tenham um espelho no ORM. Sinistralidade por contrato depende deste dado + de regra
    de negócio validada (fora do escopo da v1.2).
    """

    __tablename__ = "receitas_contrato"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "competencia", "id_contrato", name="uq_recctr_tenant_comp_ctr"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competencia: Mapped[date] = mapped_column(Date, index=True)
    id_contrato: Mapped[int] = mapped_column(ForeignKey("contratos.id"), index=True)
    quantidade_beneficiarios: Mapped[int] = mapped_column(Integer, default=0)
    receita_contraprestacao: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    reajuste_aplicado_no_periodo: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    metodologia: Mapped[str | None] = mapped_column(String(40), nullable=True)  # informativo
