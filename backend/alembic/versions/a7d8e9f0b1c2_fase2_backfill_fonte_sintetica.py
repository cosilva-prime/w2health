"""Fase 2 — backfill: dados sintéticos pré-existentes ganham fonte e ingestão registradas.

A migration f4c5d6e7a8b9 marcou as linhas existentes com `source_system =
'synthetic_generator'`, mas sem `source_connection_id` / `ingestion_run_id` — só as massas
geradas DEPOIS dela tinham a linhagem completa do Caminho A. Esta migration registra, para
cada tenant com dado sintético sem fonte:

* a fonte SYNTHETIC "Gerador sintético W2Health" (se ainda não existir);
* uma ingestão SUCCESS/AVAILABLE (`triggered_by = migration:backfill_fase2`) com a janela
  de competências e a contagem de eventos reais do tenant;
* um pipeline_run descrevendo o backfill;

e preenche `source_connection_id` / `ingestion_run_id` nas linhas canônicas desse tenant.
Nada é apagado nem recalculado. Idempotente (só atua onde a fonte está vazia).

Revision ID: a7d8e9f0b1c2
Revises: f4c5d6e7a8b9
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7d8e9f0b1c2"
down_revision: str | None = "f4c5d6e7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_NAME = "Gerador sintético W2Health"
TRIGGER = "migration:backfill_fase2"
LINEAGE_TABLES = ("regioes", "planos", "contratos", "especialidades", "procedimentos", "prestadores",
                  "diagnosticos", "beneficiarios", "receitas", "eventos_assistenciais")


def upgrade() -> None:
    conn = op.get_bind()
    tenants = conn.execute(sa.text(
        "SELECT DISTINCT tenant_id FROM eventos_assistenciais "
        "WHERE source_system = 'synthetic_generator' AND source_connection_id IS NULL "
        "ORDER BY tenant_id")).scalars().all()
    for t in tenants:
        p = {"t": t}
        # RLS: as tabelas do data plane exigem o tenant da transação para papéis não-dono
        conn.execute(sa.text("SELECT set_config('app.tenant_id', :t, true)"), p)
        sid = conn.execute(sa.text(
            "SELECT id FROM source_connections WHERE tenant_id = :t AND name = :n"),
            {**p, "n": SOURCE_NAME}).scalar()
        if sid is None:
            sid = conn.execute(sa.text(
                "INSERT INTO source_connections (tenant_id, name, source_type, source_system, status, "
                "configuration) VALUES (:t, :n, 'SYNTHETIC', 'synthetic_generator', 'ACTIVE', "
                "CAST(:cfg AS json)) RETURNING id"),
                {**p, "n": SOURCE_NAME,
                 "cfg": '{"description": "massa sintética gerada internamente"}'}).scalar_one()
        n, ini, fim, quando = conn.execute(sa.text(
            "SELECT count(*), min(competencia), max(competencia), "
            "coalesce((SELECT max(criado_em) FROM seed_manifest WHERE tenant_id = :t), now()) "
            "FROM eventos_assistenciais WHERE tenant_id = :t"), p).one()
        rid = conn.execute(sa.text(
            "INSERT INTO ingestion_runs (tenant_id, source_connection_id, source_system, started_at, "
            "finished_at, status, stage, records_received, records_valid, records_inserted, "
            "records_updated, records_rejected, competencia_inicio, competencia_fim, triggered_by, "
            "mapping_ref, error_summary) VALUES (:t, :s, 'synthetic_generator', :q, :q, 'SUCCESS', "
            "'AVAILABLE', :n, :n, :n, 0, 0, :ini, :fim, :by, 'canonico-direto', CAST('{}' AS json)) "
            "RETURNING id"),
            {**p, "s": sid, "q": quando, "n": n, "ini": ini, "fim": fim, "by": TRIGGER}).scalar_one()
        conn.execute(sa.text(
            "INSERT INTO pipeline_runs (tenant_id, ingestion_run_id, source_connection_id, layer, "
            "started_at, finished_at, status, rows_in, rows_out, triggered_by, steps) "
            "VALUES (:t, :r, :s, 'serving', :q, :q, 'SUCCESS', :n, :n, :by, CAST(:steps AS json))"),
            {**p, "r": rid, "s": sid, "q": quando, "n": n, "by": TRIGGER,
             "steps": '[{"stage": "lineage_backfill", "status": "OK"}]'})
        for tabela in LINEAGE_TABLES:
            conn.execute(sa.text(
                f"UPDATE {tabela} SET source_connection_id = :s, ingestion_run_id = :r "
                "WHERE tenant_id = :t AND source_system = 'synthetic_generator' "
                "AND source_connection_id IS NULL"), {**p, "s": sid, "r": rid})
        conn.execute(sa.text(
            "UPDATE source_connections SET last_run_at = :q, last_success_at = :q WHERE id = :s"),
            {"q": quando, "s": sid})


def downgrade() -> None:
    conn = op.get_bind()
    runs = conn.execute(sa.text(
        "SELECT id, tenant_id FROM ingestion_runs WHERE triggered_by = :by"), {"by": TRIGGER}).all()
    for rid, t in runs:
        conn.execute(sa.text("SELECT set_config('app.tenant_id', :t, true)"), {"t": t})
        for tabela in LINEAGE_TABLES:
            conn.execute(sa.text(
                f"UPDATE {tabela} SET source_connection_id = NULL, ingestion_run_id = NULL "
                "WHERE ingestion_run_id = :r"), {"r": rid})
        conn.execute(sa.text("DELETE FROM pipeline_runs WHERE ingestion_run_id = :r"), {"r": rid})
        conn.execute(sa.text("DELETE FROM ingestion_runs WHERE id = :r"), {"r": rid})
    # a fonte só é removida se não sobrou nenhuma ingestão apontando para ela
    conn.execute(sa.text(
        "DELETE FROM source_connections c WHERE c.name = :n AND c.source_type = 'SYNTHETIC' "
        "AND NOT EXISTS (SELECT 1 FROM ingestion_runs r WHERE r.source_connection_id = c.id)"),
        {"n": SOURCE_NAME})
