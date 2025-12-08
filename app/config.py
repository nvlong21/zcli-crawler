import os
import logging
from typing import List, Optional
from pydantic import AnyHttpUrl, ValidationInfo, field_validator, model_validator, Field, EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class Settings(BaseSettings):
    """Application configuration settings loaded from .env file and environment variables."""

    # --- Core Application Settings ---
    PROJECT_NAME: str = "my_fastapi_project"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", pattern=r"^(development|testing|staging|production)$")
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str

    CORS_ORIGINS: str = Field(default="", alias="CORS_ORIGINS")
    CORS_ORIGINS_LIST: List[str] = []

    # Preprocess ENVIRONMENT and CACHE_TYPE to strip comments
    @field_validator("ENVIRONMENT", "CACHE_TYPE", mode="before")
    @classmethod
    def strip_comments(cls, v: str) -> str:
        if isinstance(v, str):
            # Split on '#' and take the first part, then strip whitespace
            return v.split("#")[0].strip()
        return v

    @field_validator("CORS_ORIGINS_LIST", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: List[str], info: ValidationInfo) -> List[str]:
        cors_origins_str = info.data.get("CORS_ORIGINS", "")
        log.debug(f"Raw CORS_ORIGINS input: {cors_origins_str!r}")
        if isinstance(cors_origins_str, str) and cors_origins_str:
            origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]
            valid_origins = []
            for origin in origins:
                if origin == "*" or origin.startswith("http://") or origin.startswith("https://"):
                    valid_origins.append(origin)
                else:
                    log.warning(f"Invalid CORS origin skipped: '{origin}'")
            return valid_origins
        return []

    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO_LOG: bool = False

    @model_validator(mode="after")
    def set_db_echo_log(self) -> "Settings":
        if self.ENVIRONMENT == "development":
            self.DB_ECHO_LOG = True
        return self

    CACHE_TYPE: str = Field(default="memory", pattern=r"^(memory|redis)$")
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: Optional[str] = None
    REDIS_MAX_CONNECTIONS: int = 10

    EMAIL_SERVICE_URL: str = "grpc://localhost:50051"
    EMAIL_SERVICE_TOKEN: Optional[str] = None
    EMAIL_SENDER_ADDRESS: EmailStr = "noreply@example.com"
    PAYMENT_SERVICE_URL: AnyHttpUrl = "http://localhost:8001"
    PAYMENT_API_KEY: Optional[str] = None
    NOTIFICATION_SERVICE_URL: AnyHttpUrl = "http://localhost:8002"
    NOTIFICATION_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

@lru_cache()
def get_settings() -> Settings:
    log.info("Loading application settings...")
    try:
        settings = Settings()
        sensitive_keys = {"SECRET_KEY", "DATABASE_URL", "REDIS_PASSWORD", "EMAIL_SERVICE_TOKEN", "PAYMENT_API_KEY", "NOTIFICATION_API_KEY"}
        log_data = settings.model_dump(exclude=sensitive_keys)
        log.debug(f"Settings loaded: {log_data}")
        return settings
    except Exception as e:
        log.exception(f"CRITICAL: Error loading settings: {e}")
        raise ValueError(f"Configuration loading failed: {e}") from e

settings = get_settings()
