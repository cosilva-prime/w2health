"""Configuração da aplicação, carregada de variáveis de ambiente / arquivo .env.

Fundação SaaS V1: além dos metadados/CORS, concentra os parâmetros de segurança
(JWT, criptografia de segredos, cookies, bloqueio de login) e as duas URLs de banco:

* `DATABASE_URL`        — papel de RUNTIME da API (`w2health_app`, sem superusuário, sujeito
                          a Row-Level Security);
* `DATABASE_ADMIN_URL`  — papel DONO do schema (migrations, seed, jobs de agregação).

Segredos nunca têm default no código. Em ambientes de desenvolvimento, a ausência de
`JWT_SECRET_KEY` gera uma chave efêmera por processo (sessões caem a cada restart) e a
ausência de `DATA_ENCRYPTION_KEY` desabilita o cadastro de MFA/segredos com erro claro.
Em produção/staging, a aplicação **não sobe** sem eles (`validate_for_runtime`).
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Ambientes em que a configuração de segurança é obrigatória (falha na subida).
PRODUCTION_LIKE = frozenset({"production", "staging"})


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
    version: str = Field(default="0.2.0")

    # Origens permitidas para CORS. Na variável de ambiente, informar como array JSON.
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # ---------------------------------------------------------------- banco de dados
    # Papel de runtime da API. Em produção NÃO pode ser superusuário (RLS seria ignorado).
    database_url: str = Field(
        default="postgresql+psycopg://w2health:w2health@localhost:5432/w2health"
    )
    # Papel dono do schema — migrations, seed e jobs. Se ausente, usa `database_url`.
    database_admin_url: str | None = Field(default=None)
    # Papel de runtime criado/garantido pela migration de RLS.
    app_db_role: str = Field(default="w2health_app")
    app_db_password: SecretStr | None = Field(default=None)

    # ------------------------------------------------------------------ autenticação
    jwt_secret_key: SecretStr | None = Field(default=None)
    jwt_issuer: str = Field(default="w2health-api")
    jwt_audience: str = Field(default="w2health-app")
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_hours: int = Field(default=12, ge=1, le=24 * 7)
    # Validade do desafio intermediário (MFA / troca obrigatória de senha).
    challenge_token_minutes: int = Field(default=5, ge=1, le=15)

    # Equipe de plataforma (SUPER_ADMIN) obrigada a usar MFA — recomendado sempre ligado.
    super_admin_require_mfa: bool = Field(default=True)

    login_max_failures: int = Field(default=5, ge=3, le=20)
    login_lockout_minutes: int = Field(default=15, ge=1, le=24 * 60)
    # Limite por IP (janela de 1 min) nas rotas de autenticação — proteção de força bruta.
    auth_rate_limit_per_minute: int = Field(default=20, ge=1, le=1000)

    # Cookie do refresh token (httpOnly). `secure` obrigatório fora de dev.
    refresh_cookie_name: str = Field(default="w2h_refresh")
    cookie_secure: bool = Field(default=False)
    cookie_samesite: str = Field(default="strict")

    # Só confiar em X-Forwarded-For atrás de proxy conhecido.
    trust_proxy_headers: bool = Field(default=False)

    # ------------------------------------------------------------------ criptografia
    # Chave(s) Fernet para segredos em repouso (MFA, credenciais de integração).
    # Várias chaves separadas por vírgula = rotação (a 1ª cifra, todas decifram).
    data_encryption_key: SecretStr | None = Field(default=None)

    @property
    def admin_database_url(self) -> str:
        return self.database_admin_url or self.database_url

    @property
    def is_production_like(self) -> bool:
        return self.environment.lower() in PRODUCTION_LIKE

    def validate_for_runtime(self) -> list[str]:
        """Problemas de configuração. Em produção/staging, qualquer item impede a subida."""
        problems: list[str] = []
        key = self.jwt_secret_key.get_secret_value() if self.jwt_secret_key else ""
        if len(key) < 32:
            problems.append("JWT_SECRET_KEY ausente ou curta (mínimo 32 caracteres)")
        if not self.data_encryption_key:
            problems.append("DATA_ENCRYPTION_KEY ausente (MFA e segredos indisponíveis)")
        if self.is_production_like and not self.cookie_secure:
            problems.append("COOKIE_SECURE deve ser true fora de desenvolvimento")
        return problems


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância única (cacheada) das configurações."""
    return Settings()
