"""CLI da Data Platform — tenant SEMPRE explícito (não existe "processar todos").

    python -m app.data_platform.cli register-source --tenant vida-plena-csv \
        --name "Pacote CSV" --source-system generic_csv --mapping generic_operator --version 1
    python -m app.data_platform.cli ingest --tenant vida-plena-csv --source 3 \
        --dir data_platform/examples/generic_operator/pacote --by "cli:operador"
    python -m app.data_platform.cli readiness --tenant vida-plena-csv
    python -m app.data_platform.cli lineage --tenant vida-plena-csv --competencia 2026-06

Escritas de dados usam o papel `w2health_pipeline` (DATABASE_PIPELINE_URL). O cadastro da
fonte usa a mesma sessão de pipeline? Não: fontes são cadastradas pela administração;
aqui, por conveniência de DEV, usa a sessão do papel dono (`DATABASE_ADMIN_URL`) amarrada
ao tenant — e registra auditoria.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.data_platform import connections, lineage, onboarding, readiness
from app.data_platform.runner import run_file_ingestion
from app.db.session import AdminSessionLocal
from app.db.tenant_scope import bind_tenant
from app.models import SourceConnection, Tenant
from app.saas import audit

CLI_ACTOR = audit.Actor(email="cli", role="PLATFORM_CLI")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m app.data_platform.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("register-source")
    p.add_argument("--tenant", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--source-system", required=True)
    p.add_argument("--mapping", required=True)
    p.add_argument("--version", type=int, default=1)
    p = sub.add_parser("ingest")
    p.add_argument("--tenant", required=True)
    p.add_argument("--source", type=int, required=True)
    p.add_argument("--dir", required=True)
    p.add_argument("--by", default="cli")
    p = sub.add_parser("readiness")
    p.add_argument("--tenant", required=True)
    p = sub.add_parser("lineage")
    p.add_argument("--tenant", required=True)
    p.add_argument("--competencia", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "register-source":
        with AdminSessionLocal() as s:
            if s.get(Tenant, a.tenant) is None:
                sys.exit("tenant inexistente")
            bind_tenant(s, a.tenant)
            cfg = connections.validate_payload("FILE", a.name, a.source_system,
                                               {"mapping_id": a.mapping, "mapping_version": a.version}, None)
            c = SourceConnection(tenant_id=a.tenant, name=a.name, source_type="FILE",
                                 source_system=a.source_system, configuration=cfg)
            s.add(c)
            s.flush()
            onboarding.advance(s, a.tenant, "SOURCE_REGISTERED", by="cli")
            ok = connections.validate_connectivity(c)
            if ok["ok"]:
                onboarding.advance(s, a.tenant, "CONNECTION_VALIDATED", by="cli")
            audit.add(s, "integration.source_created", actor=CLI_ACTOR, tenant_id=a.tenant,
                      entity_type="source_connection", entity_id=c.id, details={"tipo": "FILE"})
            s.commit()
            print(json.dumps({"source_connection_id": c.id, "validacao": ok}, ensure_ascii=False))
    elif a.cmd == "ingest":
        pasta = Path(a.dir)
        files = {f.name: f.read_bytes() for f in sorted(pasta.glob("*.csv"))}
        s = get_settings()
        r = run_file_ingestion(tenant_id=a.tenant, source_connection_id=a.source, files=files,
                               triggered_by=a.by, max_bytes=s.upload_max_file_mb * 1024 * 1024,
                               max_files=s.upload_max_files)
        print(json.dumps(r.as_dict(), ensure_ascii=False, default=str, indent=2))
        if r.status == "FAILED":
            sys.exit(1)
    elif a.cmd == "readiness":
        with AdminSessionLocal() as s:
            bind_tenant(s, a.tenant)
            res = readiness.refresh(s, a.tenant)
            s.commit()
            for r in res.values():
                print(f"{r.feature_key:<28} {r.status:<10} {r.reason}")
    elif a.cmd == "lineage":
        y, m = a.competencia.split("-")
        with AdminSessionLocal() as s:
            bind_tenant(s, a.tenant)
            print(json.dumps(lineage.metric_lineage(s, a.tenant, date(int(y), int(m), 1)),
                             ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
