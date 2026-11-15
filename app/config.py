from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DATABASE_URL: str | None = None
    API_KEY: str | None = None
    ALLOWED_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_runtime_settings(self):
        env = (self.ENVIRONMENT or "development").lower()

        if env == "production":
            if not self.DATABASE_URL:
                raise ValueError("DATABASE_URL is required in production")
            if not self.API_KEY:
                raise ValueError("API_KEY is required in production")
        else:
            if not self.DATABASE_URL:
                self.DATABASE_URL = "sqlite:///./clinic_booking.db"
            if not self.API_KEY:
                self.API_KEY = "dev-api-key"

        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
