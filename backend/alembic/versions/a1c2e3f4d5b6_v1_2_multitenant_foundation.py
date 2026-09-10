"""v1.2: fundacao multi-tenant + tabelas de controle da data platform

Adiciona `tenant_id` a todas as tabelas que guardam dado de cliente (mixin `TenantMixin`),
cria a tabela `tenants` e as tabelas de controle de ingestão (estrutura, não uso), e
recompõe as chaves de negócio como `(tenant_id, <chave natural>)`.

Migration **preparatória e não destrutiva**: `server_default='w2h-demo'` permite adicionar
a coluna a tabelas já populadas; o seed carimba o tenant explicitamente e reconstrói toda
a camada `agg_*`. As consultas do repositório ainda NÃO filtram por `tenant_id` nesta
versão — dívida registrada em docs/MULTI_TENANCY.md e docs/V1.2.md.

Revision ID: a1c2e3f4d5b6
Revises: 568c707880c2
Create Date: 2026-09-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c2e3f4d5b6"
down_revision: str | None = "568c707880c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tabelas que recebem `tenant_id` simples (coluna + índice). `agg_sinistralidade_competencia`
# é tratada à parte (entra na PK).
_TENANT_TABLES = (
    "regioes", "planos", "contratos", "especialidades", "procedimentos", "prestadores",
    "diagnosticos", "beneficiarios", "receitas", "eventos_assistenciais",
    "agg_competencia_dimensao", "agg_prestador_competencia", "agg_beneficiario_competencia",
    "cenarios_gabarito", "seed_manifest", "regras_alerta",
)

# (tabela, nome antigo da unique global, colunas da nova unique tenant-scoped, novo nome)
_UNIQUES = (
    ("planos", "uq_planos_codigo", ["tenant_id", "codigo"], "uq_planos_tenant_codigo"),
    ("especialidades", "uq_especialidades_codigo", ["tenant_id", "codigo"], "uq_especialidades_tenant_codigo"),
    ("procedimentos", "uq_procedimentos_codigo", ["tenant_id", "codigo"], "uq_procedimentos_tenant_codigo"),
    ("diagnosticos", "uq_diagnosticos_cid", ["tenant_id", "cid"], "uq_diagnosticos_tenant_cid"),
    ("receitas", "uq_receita_comp_plano", ["tenant_id", "competencia", "id_plano"], "uq_receitas_tenant_comp_plano"),
    ("cenarios_gabarito", "uq_cenarios_gabarito_codigo", ["tenant_id", "codigo"], "uq_gabarito_tenant_codigo"),
    ("agg_competencia_dimensao", "uq_aggdim_comp_dim_chave", ["tenant_id", "competencia", "dimensao", "chave"], "uq_aggdim_tenant_comp_dim_chave"),
    ("agg_prestador_competencia", "uq_aggprest_comp_prest", ["tenant_id", "competencia", "id_prestador"], "uq_aggprest_tenant_comp_prest"),
    ("agg_beneficiario_competencia", "uq_aggben_comp_ben", ["tenant_id", "competencia", "id_beneficiario"], "uq_aggben_tenant_comp_ben"),
)


def upgrade() -> None:
    # --- cadastro de tenants ---------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ativo"),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
    )
    op.execute("INSERT INTO tenants (id, nome, status) VALUES ('w2h-demo', 'W2Health Demo', 'ativo')")

    # --- tenant_id nas tabelas de dado de cliente ----------------------------------
    for tbl in _TENANT_TABLES:
        op.add_column(tbl, sa.Column("tenant_id", sa.String(length=40), nullable=False, server_default="w2h-demo"))
        op.create_index(op.f(f"ix_{tbl}_tenant_id"), tbl, ["tenant_id"], unique=False)

    # agg_sinistralidade_competencia: tenant_id entra na PK (PK natural = competencia)
    op.add_column("agg_sinistralidade_competencia", sa.Column("tenant_id", sa.String(length=40), nullable=False, server_default="w2h-demo"))
    op.drop_constraint("pk_agg_sinistralidade_competencia", "agg_sinistralidade_competencia", type_="primary")
    op.create_primary_key("pk_agg_sinistralidade_competencia", "agg_sinistralidade_competencia", ["tenant_id", "competencia"])
    op.create_index(op.f("ix_agg_sinistralidade_competencia_tenant_id"), "agg_sinistralidade_competencia", ["tenant_id"], unique=False)

    # --- chaves de negócio -> (tenant_id, chave natural) --------------------------
    # beneficiarios.codigo era um índice ÚNICO; passa a índice comum + unique composta
    op.drop_index("ix_beneficiarios_codigo", table_name="beneficiarios")
    op.create_index("ix_beneficiarios_codigo", "beneficiarios", ["codigo"], unique=False)
    op.create_unique_constraint("uq_beneficiarios_tenant_codigo", "beneficiarios", ["tenant_id", "codigo"])
    for tbl, old_name, cols, new_name in _UNIQUES:
        op.drop_constraint(old_name, tbl, type_="unique")
        op.create_unique_constraint(new_name, tbl, cols)

    # --- colunas novas de negócio (v1.2) -----------------------------------------
    # novos códigos de `efeito_esperado` da v1.2 são mais longos ('distribuicao_homogenea')
    op.alter_column("cenarios_gabarito", "efeito_esperado",
                    existing_type=sa.String(length=20), type_=sa.String(length=30),
                    existing_nullable=True)
    op.add_column("contratos", sa.Column("vidas_alvo", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("agg_beneficiario_competencia", sa.Column("id_contrato", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_agg_beneficiario_competencia_id_contrato"), "agg_beneficiario_competencia", ["id_contrato"], unique=False)

    # --- tabelas de controle da data platform (estrutura, não uso) --------------
    op.create_table(
        "source_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("source_system", sa.String(length=60), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_connections")),
    )
    op.create_index(op.f("ix_source_connections_tenant_id"), "source_connections", ["tenant_id"], unique=False)
    op.create_table(
        "source_entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("source_system", sa.String(length=60), nullable=False),
        sa.Column("source_entity", sa.String(length=80), nullable=False),
        sa.Column("target_entity", sa.String(length=60), nullable=False),
        sa.Column("load_strategy", sa.String(length=20), nullable=False),
        sa.Column("business_key", sa.String(length=200), nullable=False),
        sa.Column("watermark_column", sa.String(length=80), nullable=True),
        sa.Column("updated_at_column", sa.String(length=80), nullable=True),
        sa.Column("deduplication_strategy", sa.String(length=120), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_entities")),
        sa.UniqueConstraint("tenant_id", "source_system", "source_entity", name="uq_srcent_tenant_sys_ent"),
    )
    op.create_index(op.f("ix_source_entities_tenant_id"), "source_entities", ["tenant_id"], unique=False)
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("source_system", sa.String(length=60), nullable=False),
        sa.Column("entity", sa.String(length=80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("records_received", sa.Integer(), nullable=False),
        sa.Column("records_inserted", sa.Integer(), nullable=False),
        sa.Column("records_updated", sa.Integer(), nullable=False),
        sa.Column("records_rejected", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("watermark", sa.String(length=80), nullable=True),
        sa.Column("batch_id", sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_runs")),
    )
    op.create_index(op.f("ix_ingestion_runs_tenant_id"), "ingestion_runs", ["tenant_id"], unique=False)
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("layer", sa.String(length=20), nullable=False),
        sa.Column("entity", sa.String(length=80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rows_in", sa.Integer(), nullable=False),
        sa.Column("rows_out", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_runs")),
    )
    op.create_index(op.f("ix_pipeline_runs_tenant_id"), "pipeline_runs", ["tenant_id"], unique=False)
    op.create_table(
        "data_quality_results",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column("rule_id", sa.String(length=60), nullable=False),
        sa.Column("entity", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("records_checked", sa.Integer(), nullable=False),
        sa.Column("records_failed", sa.Integer(), nullable=False),
        sa.Column("sample", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_quality_results")),
    )
    op.create_index(op.f("ix_data_quality_results_tenant_id"), "data_quality_results", ["tenant_id"], unique=False)

    # layout preparado — NÃO populado / NÃO lido na v1.2
    op.create_table(
        "receitas_contrato",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("id_contrato", sa.Integer(), nullable=False),
        sa.Column("quantidade_beneficiarios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("receita_contraprestacao", sa.Numeric(precision=16, scale=2), nullable=False, server_default="0"),
        sa.Column("reajuste_aplicado_no_periodo", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("metodologia", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["id_contrato"], ["contratos.id"], name=op.f("fk_receitas_contrato_id_contrato_contratos")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_receitas_contrato")),
        sa.UniqueConstraint("tenant_id", "competencia", "id_contrato", name="uq_recctr_tenant_comp_ctr"),
    )
    op.create_index(op.f("ix_receitas_contrato_tenant_id"), "receitas_contrato", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_receitas_contrato_competencia"), "receitas_contrato", ["competencia"], unique=False)
    op.create_index(op.f("ix_receitas_contrato_id_contrato"), "receitas_contrato", ["id_contrato"], unique=False)

    # --- remove os server_default temporários (o app/seed passam o valor) --------
    for tbl in (*_TENANT_TABLES, "agg_sinistralidade_competencia"):
        op.alter_column(tbl, "tenant_id", server_default=None)
    op.alter_column("contratos", "vidas_alvo", server_default=None)


def downgrade() -> None:
    op.drop_table("receitas_contrato")
    op.drop_table("data_quality_results")
    op.drop_table("pipeline_runs")
    op.drop_table("ingestion_runs")
    op.drop_table("source_entities")
    op.drop_table("source_connections")

    op.drop_index(op.f("ix_agg_beneficiario_competencia_id_contrato"), table_name="agg_beneficiario_competencia")
    op.drop_column("agg_beneficiario_competencia", "id_contrato")
    op.drop_column("contratos", "vidas_alvo")
    op.alter_column("cenarios_gabarito", "efeito_esperado",
                    existing_type=sa.String(length=30), type_=sa.String(length=20),
                    existing_nullable=True)

    op.drop_constraint("uq_beneficiarios_tenant_codigo", "beneficiarios", type_="unique")
    op.drop_index("ix_beneficiarios_codigo", table_name="beneficiarios")
    op.create_index("ix_beneficiarios_codigo", "beneficiarios", ["codigo"], unique=True)
    for tbl, old_name, _cols, new_name in _UNIQUES:
        op.drop_constraint(new_name, tbl, type_="unique")
        # recria a unique global antiga
        cols = {
            "uq_planos_codigo": ["codigo"], "uq_especialidades_codigo": ["codigo"],
            "uq_procedimentos_codigo": ["codigo"], "uq_diagnosticos_cid": ["cid"],
            "uq_receita_comp_plano": ["competencia", "id_plano"],
            "uq_cenarios_gabarito_codigo": ["codigo"],
            "uq_aggdim_comp_dim_chave": ["competencia", "dimensao", "chave"],
            "uq_aggprest_comp_prest": ["competencia", "id_prestador"],
            "uq_aggben_comp_ben": ["competencia", "id_beneficiario"],
        }[old_name]
        op.create_unique_constraint(old_name, tbl, cols)

    op.drop_index(op.f("ix_agg_sinistralidade_competencia_tenant_id"), table_name="agg_sinistralidade_competencia")
    op.drop_constraint("pk_agg_sinistralidade_competencia", "agg_sinistralidade_competencia", type_="primary")
    op.create_primary_key("pk_agg_sinistralidade_competencia", "agg_sinistralidade_competencia", ["competencia"])
    op.drop_column("agg_sinistralidade_competencia", "tenant_id")

    for tbl in _TENANT_TABLES:
        op.drop_index(op.f(f"ix_{tbl}_tenant_id"), table_name=tbl)
        op.drop_column(tbl, "tenant_id")

    op.drop_table("tenants")
