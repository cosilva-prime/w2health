"""Limitador de tentativas — interface + adapters (sem acoplamento à memória do processo).

* `RateLimiter` (protocolo): `hit(key) -> bool`, `reset()`.
* `DatabaseRateLimiter` — PADRÃO: janela fixa (60 s por padrão) numa tabela do control plane
  (`auth_rate_limits`); compartilhado entre processos e réplicas da API. A chave é o
  SHA-256 do identificador (IP) — o IP em claro não é persistido.
* `InMemoryRateLimiter` — só por processo (testes/dev isolado).
* Produção com tráfego alto: adapter Redis (`INCR` + `EXPIRE` na chave da janela)
  implementando o mesmo protocolo — documentado em docs/SECURITY_AND_TENANT_ISOLATION.md.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import text

log = logging.getLogger(__name__)


class RateLimiter(Protocol):
    limit: int

    def hit(self, key: str) -> bool: ...
    def reset(self) -> None: ...


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int, window_seconds: int = 60) -> None:
        self.limit = limit_per_minute
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        agora = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and agora - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(agora)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


#: compatibilidade com o nome usado na Fase 1
SlidingWindowLimiter = InMemoryRateLimiter

_UPSERT = text("""
    INSERT INTO auth_rate_limits (key, window_start, hits) VALUES (:k, :w, 1)
    ON CONFLICT (key, window_start) DO UPDATE SET hits = auth_rate_limits.hits + 1
    RETURNING hits
""")


class DatabaseRateLimiter:
    """Janela fixa por minuto. Falha do banco = permite (fail-open) e registra — o bloqueio
    por conta (`users.locked_until`) continua protegendo contra força bruta."""

    def __init__(self, limit_per_minute: int, engine_factory, window_seconds: int = 60) -> None:
        self.limit = limit_per_minute
        self.window = window_seconds
        self._engine_factory = engine_factory
        self._ultimo_expurgo = 0.0

    @staticmethod
    def _key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def hit(self, key: str) -> bool:
        agora = datetime.now(UTC)
        epoch = int(agora.timestamp())
        janela = datetime.fromtimestamp(epoch - epoch % self.window, UTC)
        try:
            with self._engine_factory().begin() as conn:
                hits = conn.execute(_UPSERT, {"k": self._key(key), "w": janela}).scalar_one()
                if time.monotonic() - self._ultimo_expurgo > 300:
                    conn.execute(text("DELETE FROM auth_rate_limits WHERE window_start < :c"),
                                 {"c": janela - timedelta(seconds=max(600, 2 * self.window))})
                    self._ultimo_expurgo = time.monotonic()
            return hits <= self.limit
        except Exception:  # noqa: BLE001
            log.exception("rate limit indisponível — liberando tentativa")
            return True

    def reset(self) -> None:
        with self._engine_factory().begin() as conn:
            conn.execute(text("DELETE FROM auth_rate_limits"))


def build_limiter(backend: str, limit: int, window_seconds: int = 60) -> RateLimiter:
    """`limit` tentativas por janela de `window_seconds`. Chaves devem ter prefixo de escopo
    (ex.: "upload:user:<id>") — limitadores diferentes compartilham a tabela."""
    if backend == "memory":
        return InMemoryRateLimiter(limit, window_seconds)
    if backend == "database":
        from app.db.session import get_engine

        return DatabaseRateLimiter(limit, get_engine, window_seconds)
    raise ValueError(f"RATE_LIMIT_BACKEND desconhecido: {backend}")
