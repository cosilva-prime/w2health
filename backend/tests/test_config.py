"""Testes da configuração (campo cors_origins e defaults)."""

import pytest

from app.core.config import Settings


def test_cors_origins_default() -> None:
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:3000"]


def test_cors_origins_explicit_list() -> None:
    settings = Settings(cors_origins=["http://localhost:3000", "http://127.0.0.1:3000"])
    assert settings.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_cors_origins_from_env_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """A variável de ambiente é decodificada como JSON pelo pydantic-settings."""
    monkeypatch.setenv("CORS_ORIGINS", '["http://a.test","http://b.test"]')
    settings = Settings()
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_defaults_present() -> None:
    settings = Settings()
    assert settings.api_v1_prefix == "/api"
    assert settings.project_name
