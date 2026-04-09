"""
서버 설정 로드 — config.yaml 파일에서 읽어옴
"""

from pathlib import Path
from functools import lru_cache

import yaml
from pydantic_settings import BaseSettings
from pydantic import BaseModel


class AuthConfig(BaseModel):
    jwt_secret: str = "vaultline-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_hours: int = 8
    refresh_token_expire_days: int = 30
    password_min_length: int = 8
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./data/app.db"


class StorageConfig(BaseModel):
    data_dir: str = "./data"
    cache_dir: str = "./data/cache"
    preview_max_size_mb: int = 5000
    preview_max_age_days: int = 30


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1
    debug: bool = False


class SyncConfig(BaseModel):
    heartbeat_timeout_seconds: int = 180
    auto_sync_warning_hours: int = 48


class LogRetentionConfig(BaseModel):
    hot_months: int = 6
    cold_months: int = 24


class Settings(BaseSettings):
    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    storage: StorageConfig = StorageConfig()
    auth: AuthConfig = AuthConfig()
    sync: SyncConfig = SyncConfig()
    log_retention: LogRetentionConfig = LogRetentionConfig()


def load_yaml_config() -> dict:
    """config.yaml 파일 로드"""
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


@lru_cache
def get_settings() -> Settings:
    """설정 싱글턴 반환"""
    raw = load_yaml_config()
    return Settings(**raw)
