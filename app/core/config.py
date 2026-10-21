"""Configuração da aplicação, lida de variáveis de ambiente / `.env`."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

APP_NAME = "CPTM REO API"
APP_VERSION = "0.1.0"


class Settings(BaseSettings):
    """Todas as configurações vêm do ambiente; nada sensível tem valor padrão."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"
    app_port: int = 4000
    log_level: str = "INFO"

    database_url: str
    test_database_url: str | None = None

    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 7
    invite_token_hours: int = 72
    # Base do link de convite; o site monta a tela em `<base>/convite/<token>`.
    invite_base_url: str = "http://localhost:5173"

    cors_origins: Annotated[list[str], NoDecode] = []

    seed_admin_name: str = "Administrador"
    seed_admin_email: str | None = None
    seed_admin_registration: str | None = None
    seed_admin_password: SecretStr | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Aceita a lista do `.env` separada por vírgula."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("jwt_secret")
    @classmethod
    def _reject_weak_secret(cls, value: SecretStr) -> SecretStr:
        """Impede subir com o segredo de exemplo ou curto demais (assinatura forjável)."""
        secret = value.get_secret_value()
        if secret == "troque-isto" or len(secret) < 32:
            raise ValueError("JWT_SECRET fraco: gere um com secrets.token_urlsafe(64)")
        return value


@lru_cache
def get_settings() -> Settings:
    """Instância única das configurações (lida uma vez por processo)."""
    return Settings()
