"""Uygulama yapılandırması (ortam değişkenlerinden okunur)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KK_", env_file=".env", extra="ignore")

    app_name: str = "KrizKalkan AI API"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+psycopg://krizkalkan:krizkalkan@localhost:5432/krizkalkan"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "krizkalkan-media"
    s3_access_key: str = "krizkalkan"
    s3_secret_key: str = "krizkalkan"

    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
