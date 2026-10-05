"""Localização do diretório `data_platform/` (contratos, mappings, regras, exemplos).

Ordem: `DATA_PLATFORM_DIR` → `<repo>/data_platform` (desenvolvimento) → `/data_platform`
(imagem Docker do backend).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


@lru_cache
def data_platform_dir() -> str:
    configurado = get_settings().data_platform_dir
    candidatos = [Path(configurado)] if configurado else []
    candidatos += [Path(__file__).resolve().parents[3] / "data_platform", Path("/data_platform")]
    for c in candidatos:
        if (c / "contracts").is_dir():
            return str(c)
    raise RuntimeError("diretório data_platform não encontrado (defina DATA_PLATFORM_DIR)")
