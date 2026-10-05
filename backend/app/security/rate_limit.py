"""Limitador simples de tentativas por chave (IP) em janela deslizante de 60 s.

Complementa o bloqueio por conta (`users.failed_login_count/locked_until`). É EM MEMÓRIA:
vale por processo — suficiente para uma instância; com várias réplicas precisa de um
backend compartilhado (Redis) — registrado como P1 em docs/V1_ROADMAP.md.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        """Registra uma tentativa. True = permitida; False = excedeu o limite."""
        agora = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and agora - q[0] > 60:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(agora)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
