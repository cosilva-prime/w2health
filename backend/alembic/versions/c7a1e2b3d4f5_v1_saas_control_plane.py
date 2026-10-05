"""v1 SaaS: control plane (usuarios, sessoes, planos, features, branding, settings, segredos, auditoria)

Fundação SaaS V1 — Etapas 1 a 7. Migration ADITIVA e não destrutiva:

1. cria as 13 tabelas novas do control plane (vazias);
2. evolui `tenants` SEM perder dado: `nome→name` e `criado_em→created_at` por RENAME;
   adiciona `uuid` (gerado), `legal_name`, `plan_id`, `is_synthetic`, `updated_at`;
   converte status `ativo|suspenso|onboarding → ACTIVE|SUSPENDED|INACTIVE`; só depois
   cria as CHECK constraints;
3. backfill: o tenant existente `w2h-demo` (massa sintética) é marcado `is_synthetic` e
   recebe o plano demonstrativo ENTERPRISE — mantém TODAS as funcionalidades que já tinha;
4. carga do catálogo de features/planos (snapshot desta revisão; edições posteriores são
   feitas pela administração e nunca sobrescritas);
5. garante que nenhuma coluna `tenant_id` do data plane tem DEFAULT (fail-closed) e que
   não há `tenant_id` órfão (aborta com mensagem clara se houver);
6. índices compostos `(tenant_id, competencia)` / `(tenant_id, id_beneficiario)` na fato.

RLS e o papel de runtime ficam na revisão seguinte (`e8b9c0d1f2a3`), para revisão separada.

Revision ID: c7a1e2b3d4f5
Revises: b2d3f4a5c6e7
Create Date: 2026-10-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7a1e2b3d4f5"
down_revision: str | None = "b2d3f4a5c6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Snapshot das 24 tabelas do data plane com tenant_id (igual a app.db.base.Base.metadata —
# verificado por tests/test_rls.py::test_lista_de_tabelas_da_migration_bate_com_metadata).
DATA_PLANE_TABLES = (
    "agg_beneficiario_competencia", "agg_competencia_dimensao", "agg_contrato_competencia",
    "agg_prestador_competencia", "agg_sinistralidade_competencia", "beneficiarios",
    "cenarios_gabarito", "contratos", "data_quality_results", "diagnosticos",
    "especialidades", "eventos_assistenciais", "ingestion_runs", "pipeline_runs", "planos",
    "prestadores", "procedimentos", "receitas", "receitas_contrato", "regioes",
    "regras_alerta", "seed_manifest", "source_connections", "source_entities",
)

_FEATURES = (
    ("executive_overview", "Visão Executiva", "Executive Overview"),
    ("loss_ratio_intelligence", "Inteligência de Sinistralidade", "Loss Ratio Intelligence"),
    ("financial_composition", "Composição financeira", "Loss Ratio Intelligence"),
    ("advanced_explanations", "Explicações avançadas (coortes)", "Loss Ratio Intelligence"),
    ("contract_intelligence", "Inteligência de Contratos", "Contract Intelligence"),
    ("provider_intelligence", "Inteligência de Prestadores", "Provider Intelligence"),
    ("beneficiary_intelligence", "Inteligência de Beneficiários", "Beneficiary Intelligence"),
    ("insights", "Insights automáticos", "Insights & Alerts"),
    ("alerts", "Alertas configuráveis", "Insights & Alerts"),
    ("custom_branding", "Identidade visual do cliente", "Plataforma"),
)
_BASE = ("executive_overview", "loss_ratio_intelligence", "financial_composition",
         "contract_intelligence", "insights")
_BUSINESS = _BASE + ("provider_intelligence", "beneficiary_intelligence", "alerts",
                     "advanced_explanations")
_PLANS = (
    ("BASIC", "Basic", _BASE),
    ("BUSINESS", "Business", _BUSINESS),
    ("ENTERPRISE", "Enterprise", _BUSINESS + ("custom_branding",)),
)


def upgrade() -> None:
    # ---------------------------------------------------- 1. tabelas do control plane
    op.create_table('audit_logs',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('actor_user_id', sa.Uuid(), nullable=True),
    sa.Column('actor_email', sa.String(length=254), nullable=True),
    sa.Column('actor_role', sa.String(length=20), nullable=True),
    sa.Column('tenant_id', sa.String(length=40), nullable=True),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=True),
    sa.Column('entity_id', sa.String(length=80), nullable=True),
    sa.Column('outcome', sa.String(length=10), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=200), nullable=True),
    sa.Column('request_id', sa.String(length=40), nullable=True),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.CheckConstraint("outcome IN ('success', 'failure', 'denied')", name=op.f('ck_audit_logs_outcome_valido')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_user_id'), 'audit_logs', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_occurred_at'), 'audit_logs', ['occurred_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_tenant_id'), 'audit_logs', ['tenant_id'], unique=False)
    op.create_table('features',
    sa.Column('key', sa.String(length=60), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.String(length=400), server_default='', nullable=False),
    sa.Column('module', sa.String(length=60), server_default='', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_features'))
    )
    op.create_table('plans',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=400), server_default='', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plans')),
    sa.UniqueConstraint('code', name=op.f('uq_plans_code'))
    )
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='ACTIVE', nullable=False),
    sa.Column('platform_role', sa.String(length=20), nullable=True),
    sa.Column('must_change_password', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('mfa_enabled', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('mfa_secret_enc', sa.Text(), nullable=True),
    sa.Column('mfa_pending_secret_enc', sa.Text(), nullable=True),
    sa.Column('mfa_last_used_step', sa.BigInteger(), nullable=True),
    sa.Column('failed_login_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('token_version', sa.Integer(), server_default='0', nullable=False),
    sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("platform_role IS NULL OR platform_role IN ('SUPER_ADMIN')", name=op.f('ck_users_platform_role_valido')),
    sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f('ck_users_status_valido')),
    sa.CheckConstraint('email = lower(email)', name=op.f('ck_users_email_minusculo')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('plan_features',
    sa.Column('plan_id', sa.Integer(), nullable=False),
    sa.Column('feature_key', sa.String(length=60), nullable=False),
    sa.ForeignKeyConstraint(['feature_key'], ['features.key'], name=op.f('fk_plan_features_feature_key_features'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], name=op.f('fk_plan_features_plan_id_plans'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('plan_id', 'feature_key', name=op.f('pk_plan_features'))
    )
    op.create_table('auth_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.String(length=40), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_reason', sa.String(length=40), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_auth_sessions_tenant_id_tenants'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_auth_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_sessions'))
    )
    op.create_index(op.f('ix_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False)
    op.create_table('tenant_branding',
    sa.Column('tenant_id', sa.String(length=40), nullable=False),
    sa.Column('product_name', sa.String(length=60), nullable=True),
    sa.Column('primary_color', sa.String(length=7), nullable=True),
    sa.Column('accent_color', sa.String(length=7), nullable=True),
    sa.Column('login_title', sa.String(length=80), nullable=True),
    sa.Column('login_message', sa.String(length=300), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("accent_color IS NULL OR accent_color ~ '^#[0-9a-f]{6}$'", name=op.f('ck_tenant_branding_accent_hex')),
    sa.CheckConstraint("primary_color IS NULL OR primary_color ~ '^#[0-9a-f]{6}$'", name=op.f('ck_tenant_branding_primary_hex')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_tenant_branding_tenant_id_tenants'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tenant_id', name=op.f('pk_tenant_branding'))
    )
    op.create_table('tenant_branding_assets',
    sa.Column('tenant_id', sa.String(length=40), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('content_type', sa.String(length=40), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('logo', 'favicon')", name=op.f('ck_tenant_branding_assets_kind_valido')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_tenant_branding_assets_tenant_id_tenants'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tenant_id', 'kind', name=op.f('pk_tenant_branding_assets'))
    )
    op.create_table('tenant_features',
    sa.Column('tenant_id', sa.String(length=40), nullable=False),
    sa.Column('feature_key', sa.String(length=60), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('reason', sa.String(length=300), server_default='', nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['feature_key'], ['features.key'], name=op.f('fk_tenant_features_feature_key_features'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_tenant_features_tenant_id_tenants'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tenant_id', 'feature_key', name=op.f('pk_tenant_features'))
    )
    op.create_table('tenant_secrets',
    sa.Column('tenant_id', sa.String(length=40), nullable=False),
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('ciphertext', sa.Text(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_tenant_secrets_tenant_id_tenants'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tenant_id', 'key', name=op.f('pk_tenant_secrets'))
    )
    op.create_table('tenant_settings',
    sa.Column('tenant_id', sa.String(length=40), nullable=False),
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_tenant_settings_tenant_id_tenants'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tenant_id', 'key', name=op.f('pk_tenant_settings'))
    )
    op.create_table('user_tenants',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.String(length=40), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='ACTIVE', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('TENANT_ADMIN', 'MANAGER', 'VIEWER')", name=op.f('ck_user_tenants_role_valido')),
    sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f('ck_user_tenants_status_valido')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_user_tenants_tenant_id_tenants'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_tenants_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'tenant_id', name=op.f('pk_user_tenants'))
    )
    op.create_index(op.f('ix_user_tenants_tenant_id'), 'user_tenants', ['tenant_id'], unique=False)
    op.create_table('refresh_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['auth_sessions.id'], name=op.f('fk_refresh_tokens_session_id_auth_sessions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_refresh_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_refresh_tokens_token_hash'))
    )
    op.create_index(op.f('ix_refresh_tokens_session_id'), 'refresh_tokens', ['session_id'], unique=False)

    # ---------------------------------------------------- 2. tenants (sem perda de dado)
    op.alter_column("tenants", "nome", new_column_name="name")
    op.alter_column("tenants", "criado_em", new_column_name="created_at")
    op.add_column("tenants", sa.Column("uuid", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False))
    op.add_column("tenants", sa.Column("legal_name", sa.String(length=200), nullable=True))
    op.add_column("tenants", sa.Column("plan_id", sa.Integer(), nullable=True))
    op.add_column("tenants", sa.Column("is_synthetic", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("tenants", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.execute("""
        UPDATE tenants SET status = CASE lower(status)
            WHEN 'ativo' THEN 'ACTIVE' WHEN 'active' THEN 'ACTIVE'
            WHEN 'suspenso' THEN 'SUSPENDED' WHEN 'suspended' THEN 'SUSPENDED'
            ELSE 'INACTIVE' END
    """)
    op.alter_column("tenants", "status", server_default="ACTIVE")
    op.create_index(op.f("ix_tenants_plan_id"), "tenants", ["plan_id"], unique=False)
    op.create_unique_constraint(op.f("uq_tenants_uuid"), "tenants", ["uuid"])
    op.create_foreign_key(op.f("fk_tenants_plan_id_plans"), "tenants", "plans", ["plan_id"], ["id"], ondelete="RESTRICT")
    op.create_check_constraint(op.f("ck_tenants_status_valido"), "tenants",
                               "status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE')")
    op.create_check_constraint(op.f("ck_tenants_codigo_valido"), "tenants",
                               "id ~ '^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$'")

    # ---------------------------------------------------- 4. catálogo (snapshot)
    conn = op.get_bind()
    for ordem, (key, name, module) in enumerate(_FEATURES):
        conn.execute(sa.text(
            "INSERT INTO features (key, name, module, sort_order) VALUES (:k, :n, :m, :o) "
            "ON CONFLICT (key) DO NOTHING"), {"k": key, "n": name, "m": module, "o": ordem})
    for ordem, (code, name, feats) in enumerate(_PLANS):
        conn.execute(sa.text(
            "INSERT INTO plans (code, name, description, sort_order) VALUES (:c, :n, :d, :o) "
            "ON CONFLICT (code) DO NOTHING"),
            {"c": code, "n": name, "d": "Matriz demonstrativa (configurável na administração).", "o": ordem})
        for k in feats:
            conn.execute(sa.text(
                "INSERT INTO plan_features (plan_id, feature_key) "
                "SELECT id, :k FROM plans WHERE code = :c ON CONFLICT DO NOTHING"), {"k": k, "c": code})

    # ---------------------------------------------------- 3. backfill do tenant demo
    conn.execute(sa.text("""
        UPDATE tenants SET is_synthetic = true,
               name = CASE WHEN name = 'W2Health Demo' THEN 'Operadora Vida Plena' ELSE name END,
               plan_id = COALESCE(plan_id, (SELECT id FROM plans WHERE code = 'ENTERPRISE'))
        WHERE id = 'w2h-demo'
    """))

    # ---------------------------------------------------- 5. fail-closed no data plane
    for tbl in DATA_PLANE_TABLES:
        op.alter_column(tbl, "tenant_id", server_default=None, existing_type=sa.String(length=40),
                        existing_nullable=False)
        orfaos = conn.execute(sa.text(
            f"SELECT DISTINCT tenant_id FROM {tbl} t "
            "WHERE NOT EXISTS (SELECT 1 FROM tenants x WHERE x.id = t.tenant_id) LIMIT 5"
        )).scalars().all()
        if orfaos:
            raise RuntimeError(
                f"{tbl}: tenant_id sem cadastro em `tenants`: {orfaos}. Cadastre os tenants "
                "(ou remova os dados órfãos) antes de aplicar a Fundação SaaS V1."
            )

    # ---------------------------------------------------- 6. índices compostos
    op.create_index("ix_eventos_tenant_competencia", "eventos_assistenciais", ["tenant_id", "competencia"])
    op.create_index("ix_eventos_tenant_beneficiario", "eventos_assistenciais", ["tenant_id", "id_beneficiario"])
    op.create_index("ix_aggben_tenant_beneficiario", "agg_beneficiario_competencia", ["tenant_id", "id_beneficiario"])


def downgrade() -> None:
    op.drop_index("ix_aggben_tenant_beneficiario", table_name="agg_beneficiario_competencia")
    op.drop_index("ix_eventos_tenant_beneficiario", table_name="eventos_assistenciais")
    op.drop_index("ix_eventos_tenant_competencia", table_name="eventos_assistenciais")

    op.drop_constraint(op.f("ck_tenants_codigo_valido"), "tenants", type_="check")
    op.drop_constraint(op.f("ck_tenants_status_valido"), "tenants", type_="check")
    op.drop_constraint(op.f("fk_tenants_plan_id_plans"), "tenants", type_="foreignkey")
    op.drop_constraint(op.f("uq_tenants_uuid"), "tenants", type_="unique")
    op.drop_index(op.f("ix_tenants_plan_id"), table_name="tenants")
    op.execute("""
        UPDATE tenants SET status = CASE status WHEN 'ACTIVE' THEN 'ativo'
            WHEN 'SUSPENDED' THEN 'suspenso' ELSE 'onboarding' END
    """)
    op.alter_column("tenants", "status", server_default="ativo")
    for col in ("updated_at", "is_synthetic", "plan_id", "legal_name", "uuid"):
        op.drop_column("tenants", col)
    op.alter_column("tenants", "created_at", new_column_name="criado_em")
    op.alter_column("tenants", "name", new_column_name="nome")

    for idx, tbl in (("ix_refresh_tokens_session_id", "refresh_tokens"),
                     ("ix_user_tenants_tenant_id", "user_tenants"),
                     ("ix_auth_sessions_user_id", "auth_sessions")):
        op.drop_index(op.f(idx), table_name=tbl)
    for tbl in ("refresh_tokens", "user_tenants", "tenant_settings", "tenant_secrets",
                "tenant_features", "tenant_branding_assets", "tenant_branding",
                "auth_sessions", "plan_features", "users", "plans", "features"):
        op.drop_table(tbl)
    for idx in ("ix_audit_logs_tenant_id", "ix_audit_logs_occurred_at",
                "ix_audit_logs_actor_user_id", "ix_audit_logs_action"):
        op.drop_index(op.f(idx), table_name="audit_logs")
    op.drop_table("audit_logs")
