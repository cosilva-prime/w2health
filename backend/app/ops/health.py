"""Checagens de prontidão (readiness) — dependências necessárias para atender tráfego.

Resposta só com `ok` / `fail` / `disabled` por dependência: nenhuma URL, host, versão,
mensagem de erro ou credencial é exposta. O motivo detalhado vai para o log.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

log = logging.getLogger("app.health")


def readiness_checks() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from app.db.session import get_engine

        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
        out["database"] = "ok"
    except Exception:  # noqa: BLE001
        log.warning("readiness: banco indisponível", exc_info=True)
        out["database"] = "fail"
    try:
        from app.db.pipeline import PipelineDatabaseNotConfigured, get_pipeline_engine

        try:
            with get_pipeline_engine().connect() as c:
                c.execute(text("SELECT 1"))
            out["pipeline_database"] = "ok"
        except PipelineDatabaseNotConfigured:
            out["pipeline_database"] = "disabled"
    except Exception:  # noqa: BLE001
        log.warning("readiness: banco do pipeline indisponível", exc_info=True)
        out["pipeline_database"] = "fail"
    try:
        from app.data_platform.storage import get_raw_storage

        get_raw_storage().ping()
        out["object_storage"] = "ok"
    except Exception:  # noqa: BLE001
        log.warning("readiness: object storage indisponível", exc_info=True)
        out["object_storage"] = "fail"
    return out
