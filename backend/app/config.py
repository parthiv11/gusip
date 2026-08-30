from functools import lru_cache
import json
import os
from urllib.parse import urlsplit

# Sentinel §2: must be set before any `import cv2` (OpenCV / Ultralytics).
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GUSIP"
    app_env: str = "poc"
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"
    session_cookie_name: str = "gusip_session"
    csrf_cookie_name: str = "gusip_csrf"
    session_cookie_secure: bool = False
    local_auth_enabled: bool = True
    auth_provider: str = "local"  # local | oidc
    oidc_issuer: str = ""
    oidc_audience: str = "gusip"
    oidc_jwks_url: str = ""
    oidc_authorization_url: str = ""
    oidc_token_url: str = ""
    oidc_client_id: str = "gusip"
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "https://gusip.example.in/api/v1/auth/oidc/callback"
    oidc_username_claim: str = "preferred_username"

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
    inference_model_path: str = "/tmp/gusip/models/yolov8n.pt"
    inference_plate_model_path: str = "/tmp/gusip/models/license-plate-yolo11n.pt"
    kafka_bootstrap_servers: str = "localhost:19092"
    use_kafka: bool = False
    audit_enabled: bool = True
    encryption_key: str = "poc-dev-key-change-me-32bytes!!"
    adapter_keys_json: str = "{}"
    ingest_max_clock_skew_seconds: int = 300
    sentinel_base_url: str = "https://live.corp8.cloud"
    sentinel_enabled: bool = True
    sentinel_anpr_enabled: bool = True
    sentinel_anpr_interval_s: float = 10.0
    sentinel_rtsp_enabled: bool = True
    sentinel_allowed_hosts: str = "live.sentinelgujarat.in,live.corp8.cloud"
    sentinel_user_agent: str = "Mozilla/5.0 (compatible; GUSIP/1.0; Sentinel ingest)"
    sentinel_referer: str = "https://sentinel.gujarat.gov.in/resource"
    # Internal MediaMTX that republishes catalogue HLS as RTSP when :8554 is not on the public host.
    sentinel_local_rtsp_url: str = ""
    face_enabled: bool = True
    face_model: str = "buffalo_l"
    face_model_root: str = "/app/data/insightface"
    face_pack_url: str = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
    face_min_det_score: float = 0.4
    face_det_size: int = 640

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env.lower() not in {"production", "prod"}:
            return self

        errors: list[str] = []
        known_secret_fragments = ("change-me", "poc-dev", "gusipsecret")
        if len(self.secret_key) < 32 or any(value in self.secret_key.lower() for value in known_secret_fragments):
            errors.append("SECRET_KEY must be a unique secret of at least 32 characters")
        if len(self.encryption_key) < 32 or any(value in self.encryption_key.lower() for value in known_secret_fragments):
            errors.append("ENCRYPTION_KEY must be a unique secret of at least 32 characters")
        if not self.audit_enabled:
            errors.append("AUDIT_ENABLED cannot be false")
        if not self.session_cookie_secure:
            errors.append("SESSION_COOKIE_SECURE must be true")
        if self.local_auth_enabled:
            errors.append("LOCAL_AUTH_ENABLED cannot be true")
        if self.auth_provider != "oidc":
            errors.append("AUTH_PROVIDER must be oidc")
        for name, url in {
            "OIDC_ISSUER": self.oidc_issuer,
            "OIDC_JWKS_URL": self.oidc_jwks_url,
            "OIDC_AUTHORIZATION_URL": self.oidc_authorization_url,
            "OIDC_TOKEN_URL": self.oidc_token_url,
            "OIDC_REDIRECT_URI": self.oidc_redirect_uri,
        }.items():
            if urlsplit(url).scheme != "https":
                errors.append(f"{name} must be an HTTPS URL")
        if self.simulation_enabled:
            errors.append("SIMULATION_ENABLED cannot be true")
        if not self.minio_secure:
            errors.append("MINIO_SECURE must be true")
        if self.minio_access_key.lower() == "gusip" or any(
            value in self.minio_secret_key.lower() for value in known_secret_fragments
        ):
            errors.append("default object-storage credentials are forbidden")

        origins = self.cors_origin_list
        if not origins:
            errors.append("CORS_ORIGINS must contain an explicit trusted origin")
        for origin in origins:
            parsed = urlsplit(origin)
            if origin == "*" or parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
                errors.append("CORS_ORIGINS must contain only explicit HTTPS production origins")
                break
        if not self.adapter_key_map:
            errors.append("ADAPTER_KEYS_JSON must define at least one adapter")
        elif any(
            len(key) < 32 or any(value in key.lower() for value in known_secret_fragments)
            for key in self.adapter_key_map.values()
        ):
            errors.append("every adapter key must be unique and contain at least 32 characters")
        sentinel_host = (urlsplit(self.sentinel_base_url).hostname or "").lower()
        if not self.sentinel_allowed_host_set or sentinel_host not in self.sentinel_allowed_host_set:
            errors.append("SENTINEL_BASE_URL host must be present in SENTINEL_ALLOWED_HOSTS")

        if errors:
            raise ValueError("unsafe production configuration: " + "; ".join(errors))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def adapter_key_map(self) -> dict[str, str]:
        try:
            value = json.loads(self.adapter_keys_json)
        except json.JSONDecodeError as exc:
            raise ValueError("ADAPTER_KEYS_JSON must be valid JSON") from exc
        if not isinstance(value, dict) or not all(
            isinstance(adapter_id, str) and isinstance(key, str) for adapter_id, key in value.items()
        ):
            raise ValueError("ADAPTER_KEYS_JSON must be a JSON object of string keys")
        return value

    @property
    def sentinel_allowed_host_set(self) -> frozenset[str]:
        return frozenset(host.strip().lower() for host in self.sentinel_allowed_hosts.split(",") if host.strip())

    def sentinel_headers(self, accept: str = "application/json, */*") -> dict[str, str]:
        return {
            "User-Agent": self.sentinel_user_agent,
            "Accept": accept,
            "Referer": self.sentinel_referer,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
