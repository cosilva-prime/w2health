"""Entrada do worker.

    python -m app.worker              # loop (contêiner `worker`)
    python -m app.worker healthcheck  # 0 = vivo (heartbeat recente), 1 = parado
    python -m app.worker drain        # processa o que está na fila e sai (operação/teste)

Em produção/staging o worker aplica as mesmas regras fail-closed da API
(`validate_for_runtime`) antes de consumir qualquer job.
"""

from __future__ import annotations

import os
import signal
import sys
import threading

os.environ.setdefault("SERVICE_NAME", "worker")

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "run"
    if cmd == "healthcheck":
        from app.worker.service import healthcheck

        return 0 if healthcheck() else 1
    configure_logging()
    s = get_settings()
    problemas = s.validate_for_runtime()
    if problemas and s.is_production_like:
        print("configuração inválida para produção: " + "; ".join(problemas), file=sys.stderr)
        return 2
    from app.worker.service import Worker

    w = Worker()
    if cmd == "drain":
        print(f"{w.drain()} job(s) processado(s)")
        return 0
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())  # termina o job atual e sai
    w.run_forever(stop)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
