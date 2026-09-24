import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:////tmp/estatepulse.db" if os.getenv("VERCEL") else "sqlite:///./portfolio.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    session_secret: str = "change-me-in-production"
    demo_access_code: str = "demo"
    admin_token: str = "admin-demo"
    frontend_origin: str = "http://localhost:5173"
    seed_data_dir: Path = Field(default=ROOT_DIR / "data")
    static_dir: Path = Field(default=ROOT_DIR / "frontend" / "dist")


@lru_cache
def get_settings() -> Settings:
    return Settings()
