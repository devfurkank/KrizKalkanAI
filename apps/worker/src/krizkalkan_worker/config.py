"""İşçi yapılandırması."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KK_", env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+psycopg://krizkalkan:krizkalkan@localhost:5432/krizkalkan"


settings = Settings()
