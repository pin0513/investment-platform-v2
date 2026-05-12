from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_url: str = Field(..., min_length=10)
    jwt_secret: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    google_oauth_client_id: str

    first_admin_email: str = "pin0513@gmail.com"
    allowed_origins: str = "http://localhost:8000"

    log_level: str = "INFO"
    environment: str = "dev"

    @field_validator("jwt_secret")
    @classmethod
    def _check_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 chars")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
