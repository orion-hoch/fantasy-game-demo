"""Application settings for the FastAPI strangler backend."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fantasy Game API"
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///../fantasy.db"
    upstash_redis_rest_url: str | None = None
    upstash_redis_rest_token: str | None = None
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
