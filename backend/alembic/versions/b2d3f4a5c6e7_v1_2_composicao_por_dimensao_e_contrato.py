"""v1.2: composicao financeira propagada as agg_* + agg_contrato_competencia

Aditivo. As colunas `despesa_bruta / glosas / coparticipacao / despesa_liquida` entram
em `agg_competencia_dimensao`, `agg_prestador_competencia` e `agg_beneficiario_competencia`
ao lado da `despesa` já existente (que mantém a semântica `Σ valor_pago` = bruta − glosa).
`agg_contrato_competencia` é a nova tabela materializada de Contract Intelligence
(tenant-aware). Todas as `agg_*` são reconstruídas do zero pelo seed/`app.seed.aggregate`.

Revision ID: b2d3f4a5c6e7
Revises: a1c2e3f4d5b6
Create Date: 2026-09-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2d3f4a5c6e7"
down_revision: str | None = "a1c2e3f4d5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMPOSICAO_TABLES = (
    "agg_competencia_dimensao",
    "agg_prestador_competencia",
    "agg_beneficiario_competencia",
)
_COMPOSICAO_COLS = ("despesa_bruta", "glosas", "coparticipacao", "despesa_liquida")


def upgrade() -> None:
    for tbl in _COMPOSICAO_TABLES:
        for col in _COMPOSICAO_COLS:
            op.add_column(tbl, sa.Column(col, sa.Float(), nullable=False, server_default="0"))
        for col in _COMPOSICAO_COLS:
            op.alter_column(tbl, col, server_default=None)

    op.create_table(
        "agg_contrato_competencia",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("id_contrato", sa.Integer(), nullable=False),
        sa.Column("vidas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("despesa", sa.Float(), nullable=False, server_default="0"),
        sa.Column("despesa_bruta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("glosas", sa.Float(), nullable=False, server_default="0"),
        sa.Column("coparticipacao", sa.Float(), nullable=False, server_default="0"),
        sa.Column("despesa_liquida", sa.Float(), nullable=False, server_default="0"),
        sa.Column("eventos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("beneficiarios_com_evento", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("custo_pmpm", sa.Float(), nullable=False, server_default="0"),
        sa.Column("gini", sa.Float(), nullable=False, server_default="0"),
        sa.Column("top5_share", sa.Float(), nullable=False, server_default="0"),
        sa.Column("n_beneficiarios_alto_custo", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["id_contrato"], ["contratos.id"], name=op.f("fk_agg_contrato_competencia_id_contrato_contratos")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agg_contrato_competencia")),
        sa.UniqueConstraint("tenant_id", "competencia", "id_contrato", name="uq_aggctr_tenant_comp_ctr"),
    )
    op.create_index(op.f("ix_agg_contrato_competencia_tenant_id"), "agg_contrato_competencia", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_agg_contrato_competencia_competencia"), "agg_contrato_competencia", ["competencia"], unique=False)
    op.create_index(op.f("ix_agg_contrato_competencia_id_contrato"), "agg_contrato_competencia", ["id_contrato"], unique=False)


def downgrade() -> None:
    op.drop_table("agg_contrato_competencia")
    for tbl in _COMPOSICAO_TABLES:
        for col in _COMPOSICAO_COLS:
            op.drop_column(tbl, col)
