from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _replace_query_key(url: str, old_key: str, new_key: str) -> str:
    parts = urlsplit(url)
    query_items = []
    for key, query_value in parse_qsl(parts.query, keep_blank_values=True):
        query_items.append((new_key if key == old_key else key, query_value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))


def _normalize_database_url(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("postgres://"):
        normalized = normalized.replace("postgres://", "postgresql+asyncpg://", 1)
    elif normalized.startswith("postgresql://") and "+asyncpg" not in normalized:
        normalized = normalized.replace("postgresql://", "postgresql+asyncpg://", 1)
    if normalized.startswith("postgresql+asyncpg://"):
        normalized = _replace_query_key(normalized, "sslmode", "ssl")
    return normalized


def make_sync_database_url(value: str) -> str:
    normalized = value.strip().replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return _replace_query_key(normalized, "ssl", "sslmode")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = "AtendeCRM SaaS API"
    api_v1_str: str = "/api/v1"
    environment: str = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/atendecrm_saas"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    refresh_token_expire_days: int = 7
    data_encryption_secret: str = "change-me-encryption"
    billing_provider: str = "asaas"
    asaas_api_base_url: str = "https://api-sandbox.asaas.com"
    asaas_api_key: str = ""
    asaas_webhook_auth_token: str = ""
    meta_graph_api_base_url: str = "https://graph.facebook.com"
    meta_default_graph_api_version: str = "v21.0"
    meta_global_app_secret: str = ""
    meta_global_verify_token: str = ""
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_default_queue: str = "atendecrm"
    celery_task_always_eager: bool = False
    queue_max_attempts: int = 5
    queue_retry_backoff_seconds: int = 30
    queue_retry_backoff_max_seconds: int = 900
    runtime_agent_token: str = ""
    store_heartbeat_stale_after_seconds: int = 300

    auto_create_tables: bool = False
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    seed_superadmin: bool = True
    superadmin_full_name: str = "Administrador da Plataforma"
    superadmin_login: str = "owner"
    superadmin_email: EmailStr = "owner@example.com"
    superadmin_password: str = "TroqueEstaSenha123!"

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def split_comma_values(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        return _normalize_database_url(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
