"""Configuração da aplicação, carregada de variáveis de ambiente / arquivo .env.

Etapa 1 do MVP: apenas o essencial para subir a API (metadados, prefixo da API e CORS).
`DATABASE_URL` já é lida aqui para ficar pronta, mas nenhuma conexão é aberta ainda —
a integração com o PostgreSQL entra na Etapa 2 (modelo de dados + migrations).
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação.

    Observação sobre `cors_origins`: por ser uma coleção, o pydantic-settings tenta
    decodificar a variável de ambiente como JSON. Portanto `CORS_ORIGINS` deve ser um
    array JSON válido, ex.: `CORS_ORIGINS=["http://localhost:3000"]`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = Field(default="W2Health Intelligence")
    environment: str = Field(default="development")
    api_v1_prefix: str = Field(default="/api")
    version: str = Field(default="0.1.0")

    # Origens permitidas para CORS. Na variável de ambiente, informar como array JSON.
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # Preparada para a Etapa 2 — ainda não utilizada nesta etapa.
    database_url: str = Field(
        default="postgresql+psycopg://w2health:w2health@localhost:5432/w2health"
    )


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância única (cacheada) das configurações."""
    return Settings()
