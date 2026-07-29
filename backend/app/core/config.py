from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MEDIALENS_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "MediaLens"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:////data/medialens.db"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    auto_scan_enabled: bool = True
    file_stability_seconds: int = Field(default=60, ge=10, le=3600)
    reconcile_minutes: int = Field(default=15, ge=1, le=1440)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
