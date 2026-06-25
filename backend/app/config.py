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


# --- rule editing (the Rules screen writes here) ----------------------------
# The checks engine looks up its REF -> value maps by normalize_ref(REF) (uppercase + trim,
# hyphen preserved), so we normalize keys on save and the lookups can't silently miss.

_SECTION_DEFAULTS = {
    "gtin": {"configured": False, "ai240_hyphen": "optional", "map": {}},
    "descriptions": {"configured": False, "match_mode": "normalized", "map": {}},
    "ifu": {"configured": False, "required_on_label": True},
    "static_content": {"configured": False, "families": {}, "ref_to_family": {}},
}


def _norm_ref(raw) -> str:
    return str(raw or "").strip().upper()


def validate_rules(data: dict) -> list[str]:
    """Return a list of human-readable validation errors ([] means valid)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["rules payload must be an object"]

    if not str(data.get("rules_version") or "").strip():
        errors.append("rules_version is required")

    def _is_str_map(v) -> bool:
        return isinstance(v, dict) and all(
            isinstance(k, str) and isinstance(val, str) for k, val in v.items())

    gtin = data.get("gtin") or {}
    if not isinstance(gtin.get("configured", False), bool):
        errors.append("gtin.configured must be true/false")
    if gtin.get("ai240_hyphen", "optional") not in ("optional", "required"):
        errors.append("gtin.ai240_hyphen must be 'optional' or 'required'")
    if not _is_str_map(gtin.get("map", {})):
        errors.append("gtin.map must be a REF -> GTIN string map")
    elif gtin.get("configured"):
        for ref, code in gtin.get("map", {}).items():
            if not (code.isdigit() and len(code) == 14):
                errors.append(f"gtin.map[{ref}] = '{code}' is not a 14-digit GTIN")

    desc = data.get("descriptions") or {}
    if not isinstance(desc.get("configured", False), bool):
        errors.append("descriptions.configured must be true/false")
    if desc.get("match_mode", "normalized") not in ("exact", "normalized", "contains"):
        errors.append("descriptions.match_mode must be exact/normalized/contains")
    if not _is_str_map(desc.get("map", {})):
        errors.append("descriptions.map must be a REF -> description string map")

    ifu = data.get("ifu") or {}
    for k in ("configured", "required_on_label"):
        if k in ifu and not isinstance(ifu[k], bool):
            errors.append(f"ifu.{k} must be true/false")

    static = data.get("static_content") or {}
    if not isinstance(static.get("configured", False), bool):
        errors.append("static_content.configured must be true/false")
    if "families" in static and not isinstance(static["families"], dict):
        errors.append("static_content.families must be an object")
    if "ref_to_family" in static and not isinstance(static["ref_to_family"], dict):
        errors.append("static_content.ref_to_family must be an object")

    return errors


def save_rules(data: dict) -> dict:
    """Validate, normalize REF keys, and persist the rule set to the active rules file.

    Raises ValueError(joined-errors) on validation failure. Returns the saved (normalized) dict.
    """
    import yaml

    errors = validate_rules(data)
    if errors:
        raise ValueError("; ".join(errors))

    # Merge over the section defaults so a partial payload never drops required keys, then
    # normalize the REF map keys so engine lookups (which normalize the incoming REF) hit.
    out: dict = {"rules_version": str(data["rules_version"]).strip()}
    for section, defaults in _SECTION_DEFAULTS.items():
        merged = {**defaults, **(data.get(section) or {})}
        if "map" in merged and isinstance(merged["map"], dict):
            merged["map"] = {_norm_ref(k): v for k, v in merged["map"].items()}
        if "ref_to_family" in merged and isinstance(merged["ref_to_family"], dict):
            merged["ref_to_family"] = {_norm_ref(k): v for k, v in merged["ref_to_family"].items()}
        out[section] = merged

    path = Path(settings().rules_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ("# Maxx Label Approval rule set — managed by the in-app Rules screen.\n"
              "# Edits here flip the dependent checks (C-AI(01), D, E, F) between\n"
              "# DEFERRED and active. Hand-edit only if you know the schema.\n")
    path.write_text(header + yaml.safe_dump(out, sort_keys=False, allow_unicode=True))
    return out
