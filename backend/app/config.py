from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GUSIP"
    app_env: str = "poc"
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"

    database_url: str = "postgresql+asyncpg://gusip:gusip@localhost:5432/gusip"
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "gusip"
    minio_secret_key: str = "gusipsecret"
    minio_bucket: str = "gusip-evidence"
    minio_secure: bool = False

    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:8080"
    simulation_enabled: bool = True
    simulation_cameras: int = 50
    inference_mode: str = "simulate"  # simulate | yolo
    kafka_bootstrap_servers: str = "localhost:19092"
    use_kafka: bool = False
    audit_enabled: bool = True
    encryption_key: str = "poc-dev-key-change-me-32bytes!!"
    sentinel_base_url: str = "https://live.sentinelgujarat.in"
    sentinel_enabled: bool = True
    sentinel_anpr_enabled: bool = True
    sentinel_anpr_interval_s: float = 10.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
