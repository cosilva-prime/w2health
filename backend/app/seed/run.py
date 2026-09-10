"""Orquestrador do seed sintético. Uso:

    uv run python -m app.seed.run --beneficiarios 20000 --seed 42
    uv run python -m app.seed.run --beneficiarios 100000        # base cheia
"""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime

import numpy as np
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import RegraAlerta, SeedManifest, Tenant
from app.seed.aggregate import rebuild_aggregations
from app.seed.config import SeedConfig
from app.seed.generator import (
    generate_beneficiarios,
    generate_eventos,
    generate_receitas,
    load_catalogos,
    wipe_dados,
)


def run_seed(cfg: SeedConfig, session: Session, *, verbose: bool = True) -> dict:
    rng = np.random.default_rng(cfg.seed)
    t0 = time.perf_counter()

    def log(msg: str) -> None:
        if verbose:
            print(f"[seed +{time.perf_counter() - t0:6.1f}s] {msg}", flush=True)

    log("limpando dados...")
    wipe_dados(session)

    # tenant do ambiente (v1.2) — upsert idempotente
    if session.get(Tenant, cfg.tenant_id) is None:
        session.add(Tenant(id=cfg.tenant_id, nome="W2Health Demo", status="ativo"))
        session.flush()

    log("catálogos...")
    cat = load_catalogos(session, cfg, rng)

    log(f"carteira ({cfg.n_beneficiarios} beneficiários)...")
    cart = generate_beneficiarios(session, cfg, rng, cat)

    hooks = []
    gabarito_rows: list = []
    supr_reajuste: set[int] = set()
    owned_proc_ids: set[int] = set()
    blocked_prestador_ids: set[int] = set()
    glosa_mult_por_mes: dict[date, float] = {}
    copart_mult_por_mes: dict[date, float] = {}
    receita_ajuste_pontual: dict[date, float] = {}
    if cfg.aplicar_cenarios:
        from app.seed.scenarios import build_scenarios

        (
            hooks, gabarito_rows, supr_reajuste, owned_proc_ids, blocked_prestador_ids,
            glosa_mult_por_mes, copart_mult_por_mes, receita_ajuste_pontual,
        ) = build_scenarios(cat, cfg, rng, cart)
        log(f"cenários plantados: {len(gabarito_rows)}")

    log("eventos assistenciais...")
    stats = generate_eventos(
        session, cfg, rng, cat, cart, scenario_hooks=hooks,
        owned_proc_ids=owned_proc_ids, blocked_prestador_ids=blocked_prestador_ids,
        glosa_mult_por_mes=glosa_mult_por_mes, copart_mult_por_mes=copart_mult_por_mes,
    )
    log(f"  {stats['total_eventos']} eventos")

    log("receitas (calibrando sinistralidade-alvo)...")
    generate_receitas(
        session, cfg, rng, cat, stats, suprimir_reajuste=supr_reajuste,
        receita_ajuste_pontual=receita_ajuste_pontual,
    )

    if gabarito_rows:
        for g in gabarito_rows:
            g.tenant_id = cfg.tenant_id
        session.add_all(gabarito_rows)
        session.flush()

    log("reconstruindo camada analítica...")
    counts = rebuild_aggregations(session, tenant_id=cfg.tenant_id)
    log(f"  {counts}")

    _seed_regras_alerta_default(session, cfg.tenant_id)

    manifest = SeedManifest(
        tenant_id=cfg.tenant_id,
        seed=cfg.seed,
        beneficiarios=cfg.n_beneficiarios,
        inicio=cfg.inicio,
        fim=cfg.fim,
        escala_eventos=cfg.escala_eventos,
        criado_em=datetime.now(),
        contagens={
            "eventos": stats["total_eventos"],
            "competencias": len(cfg.competencias()),
            "cenarios": len(gabarito_rows),
            **counts,
        },
    )
    session.add(manifest)
    session.commit()
    log("commit concluído.")
    return manifest.contagens


def _seed_regras_alerta_default(session: Session, tenant_id: str) -> None:
    """Regras de exemplo (v1.1 Etapa C + v1.2 C6) — inseridas só se a tabela estiver vazia,
    para NUNCA apagar configuração que o gestor já tenha criado/editado num reseed."""
    if session.query(RegraAlerta).count() > 0:
        return
    session.add_all(
        [
            RegraAlerta(
                tenant_id=tenant_id,
                nome="Beneficiário de alto impacto", entidade="beneficiario",
                indicador="participacao_variacao", operador=">=", limite=50.0,
                severidade="critica",
                escopo={"nota": "exemplo do enunciado — em carteiras grandes, calibre "
                                 "para um valor menor (ver regra calibrada abaixo)"},
            ),
            RegraAlerta(
                tenant_id=tenant_id,
                nome="Beneficiário de alto impacto (calibrado para esta carteira)",
                entidade="beneficiario", indicador="participacao_variacao",
                operador=">=", limite=0.35, severidade="critica",
            ),
            RegraAlerta(
                tenant_id=tenant_id,
                nome="Prestador com crescimento relevante", entidade="prestador",
                indicador="crescimento_despesa", operador=">=", limite=30.0,
                severidade="atencao",
            ),
            # v1.2 — C6
            RegraAlerta(
                tenant_id=tenant_id,
                nome="Contrato com concentração alta", entidade="contrato",
                indicador="concentracao", operador=">=", limite=55.0, severidade="atencao",
            ),
            RegraAlerta(
                tenant_id=tenant_id,
                nome="Novo caso de alto custo no mês", entidade="beneficiario",
                indicador="novo_caso_alto_custo", operador=">=", limite=1.0,
                severidade="atencao",
            ),
        ]
    )
    session.commit()


def _parse_month(s: str) -> date:
    y, m = s.split("-")
    return date(int(y), int(m), 1)


def main() -> None:
    p = argparse.ArgumentParser(description="Gerador de dados sintéticos do W2Health Intelligence")
    p.add_argument("--beneficiarios", type=int, default=20_000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--inicio", type=_parse_month, default="2025-01")
    p.add_argument("--fim", type=_parse_month, default="2026-12")
    p.add_argument("--escala", type=float, default=1.0, dest="escala_eventos")
    p.add_argument("--no-cenarios", action="store_true")
    args = p.parse_args()

    cfg = SeedConfig(
        seed=args.seed,
        n_beneficiarios=args.beneficiarios,
        inicio=args.inicio if isinstance(args.inicio, date) else _parse_month(args.inicio),
        fim=args.fim if isinstance(args.fim, date) else _parse_month(args.fim),
        escala_eventos=args.escala_eventos,
        aplicar_cenarios=not args.no_cenarios,
    )
    with SessionLocal() as session:
        run_seed(cfg, session)


if __name__ == "__main__":
    main()
