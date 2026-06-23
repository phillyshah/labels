"""Runtime configuration, loaded from environment (matches the user's .env convention)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- auth (V1: single shared password; swappable for Supabase Auth later) ---
    app_password: str = "changeme"        # APP_PASSWORD
    session_secret: str = "dev-insecure-session-secret"  # SESSION_SECRET
    session_ttl_seconds: int = 60 * 60 * 12

    # --- processor internal contract ---
    processor_shared_secret: str = "dev-processor-secret"  # PROCESSOR_SHARED_SECRET

    # --- rules ---
    rules_path: str = "config/rules.yaml"  # RULES_PATH

    # --- persistence ---
    database_url: str = ""                 # DATABASE_URL (Supabase Postgres); empty => local store
    supabase_url: str = ""                 # SUPABASE_URL
    supabase_service_role_key: str = ""    # SUPABASE_SERVICE_ROLE_KEY
    storage_bucket: str = "submissions"    # STORAGE_BUCKET
    local_data_dir: str = "backend/.localdata"  # used only when database_url is empty

    # --- misc ---
    cors_origins: str = "*"                # comma-separated


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()


def rules() -> dict:
    """Load the active rule set (file-based for V1). Falls back to the example/unconfigured set."""
    import yaml

    candidates = [settings().rules_path, "config/rules.yaml", "config/rules.example.yaml"]
    for c in candidates:
        p = Path(c)
        if p.exists():
            return yaml.safe_load(p.read_text()) or {}
    return {"rules_version": "unconfigured"}
