import os
import logging
from typing import List, Optional, ClassVar, Tuple, Callable
from pydantic import AnyHttpUrl, ValidationInfo, field_validator, model_validator, Field, EmailStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from kombu import Queue

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
class DatabaseSettings(BaseSettings):
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO_LOG: bool = False    
def route_task(name, args, kwargs, options, task=None, **kw):
    if ":" in name:
        queue, _ = name.split(":")
        return {"queue": queue}
    return {"queue": "default"}

class SQLiteSettings(DatabaseSettings):
    SQLITE_URI: str = "./sql_app.db"
    SQLITE_SYNC_PREFIX: str = "sqlite:///"
    SQLITE_ASYNC_PREFIX: str = "sqlite+aiosqlite:///"

class PostgresSettings(DatabaseSettings):
    POSTGRES_USER: str = Field(default="postgres", env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(default="postgres", env="POSTGRES_PASSWORD")
    POSTGRES_HOST: str = Field(default="localhost", env="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(default=5432, env="POSTGRES_PORT")
    POSTGRES_DB: str = Field(default="postgres", env="POSTGRES_DB")
    POSTGRES_ASYNC_ENABLED: bool = Field(default=False, env="POSTGRES_ASYNC_ENABLED")
    POSTGRES_SYNC_PREFIX: str = "postgresql://"
    POSTGRES_ASYNC_PREFIX: str = "postgresql+asyncpg://"
    DATABASE_URL_ENV: str | None = Field(default=None, env="DATABASE_URL")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:       
        if self.DATABASE_URL_ENV:
            return self.DATABASE_URL_ENV
        credentials = f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
        location = f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        prefix = self.POSTGRES_SYNC_PREFIX
        if self.POSTGRES_ASYNC_ENABLED:
            prefix = self.POSTGRES_ASYNC_PREFIX
        return f"{prefix}{credentials}@{location}"


class S3Settings(DatabaseSettings):
    S3_ENABLE: bool = Field(default=False, env="S3_ENABLED")
    S3_ENDPOOINT: str = Field(default="", env="S3_ENDPOOINT")    
    S3_ACCESSKEY: str = Field(default="", env="S3_ACCESSKEY")
    S3_SECRETKEY: str = Field(default="", env="S3_SECRETKEY")
    S3_USESSL: bool = Field(default=True, env="S3_USESSL")
    S3_BUCKETNAME: str = Field(default="", env="S3_BUCKETNAME")
    S3_USEIAM: bool = Field(default=False, env="S3_USEIAM")
    S3_CLOUDPROVIDER: str = Field(default="aws", env="S3_CLOUDPROVIDER")
    S3_ROOTPATH: str = Field(default="", env="S3_ROOTPATH")
    S3_IAM_ENDPOINT: str = Field(default="", env="S3_IAM_ENDPOINT")
    S3_REGION: str = Field(default="", env="S3_REGION")
    S3_USEVIRTUALHOST: bool = Field(default=False, env="S3_USEVIRTUALHOST") 
    AWS_ACCESS_KEY_ID: str = ""  
    AWS_SECRET_ACCESS_KEY: str = ""    
    AWS_DEFAULT_REGION: str = ""   

    def model_post_init(self, __context):
        if not self.AWS_ACCESS_KEY_ID:
            self.AWS_ACCESS_KEY_ID = self.S3_ACCESSKEY or os.getenv("AWS_ACCESS_KEY_ID", "")
        if not self.AWS_SECRET_ACCESS_KEY:
            self.AWS_SECRET_ACCESS_KEY = self.S3_SECRETKEY or os.getenv("AWS_SECRET_ACCESS_KEY", "")
        if not self.AWS_DEFAULT_REGION:
            self.AWS_DEFAULT_REGION = self.S3_REGION or os.getenv("AWS_DEFAULT_REGION", "")

class CelerySettings(BaseSettings):
    CELERY_BROKER_URL: str =  Field(default="redis://:g9Bl0s4bi9J5QD08KQsxo4Oh0G2atsmWmQIzwkqw@127.0.0.1:6379/0", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str =  Field(default="redis://:g9Bl0s4bi9J5QD08KQsxo4Oh0G2atsmWmQIzwkqw@127.0.0.1:6379/0", env="CELERY_RESULT_BACKEND")
    WS_MESSAGE_QUEUE: str = Field(default="redis://127.0.0.1:6379/0", env="WS_MESSAGE_QUEUE")
    CELERY_BEAT_SCHEDULE: dict = {
        # "task-schedule-work": {
        #     "task": "task_schedule_work",
        #     "schedule": 5.0,  # five seconds
        # },
    }

    CELERY_TASK_DEFAULT_QUEUE: str = Field(default="default", env="CELERY_TASK_DEFAULT_QUEUE")

    # Force all queues to be explicitly listed in `CELERY_TASK_QUEUES` to help prevent typos
    CELERY_TASK_CREATE_MISSING_QUEUES: bool = False

    CELERY_TASK_QUEUES: list = (
        # need to define default queue here or exception would be raised
        Queue("default"),

        Queue("high_priority"),
        Queue("low_priority"),
    )

    CELERY_TASK_ROUTES: ClassVar[Tuple[Callable, ...]] = (route_task,)


class Settings(SQLiteSettings,
    PostgresSettings,
    S3Settings, CelerySettings, BaseSettings):
    """Application configuration settings loaded from .env file and environment variables."""

    # --- Core Application Settings ---
    PROJECT_NAME: str = "my_fastapi_project"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", pattern=r"^(development|testing|staging|production)$")
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str

    CORS_ORIGINS: str = Field(default="", alias="CORS_ORIGINS")
    CORS_ORIGINS_LIST: List[str] = []
    DATA_DIR: str = "/tmp"
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
    PREFER_RED_CODEC:str =  "wav"
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

@lru_cache()
def get_settings() -> Settings:
    log.info("Loading application settings...")
    # try:
    settings = Settings()
    sensitive_keys = {"SECRET_KEY", "DATABASE_URL", "REDIS_PASSWORD", "EMAIL_SERVICE_TOKEN", "PAYMENT_API_KEY", "NOTIFICATION_API_KEY"}
    log_data = settings.model_dump(exclude=sensitive_keys)
    log.debug(f"Settings loaded: {log_data}")
    return settings
    # except Exception as e:
    #     log.exception(f"CRITICAL: Error loading settings: {e}")
    #     raise ValueError(f"Configuration loading failed: {e}") from e

settings = get_settings()
