"""
Configuration management.

Priority (highest → lowest):
  1. Programmatic / init values
  2. Environment variables  (prefix: APP_)
  3. .env file
  4. TOML config file       (~/.hard-cli.toml or APP_CONFIG_FILE)
  5. Field defaults

TOML config file location:
  - Default: ~/.hard-cli.toml
  - Override via APP_CONFIG_FILE env var or --config CLI flag
    (the flag sets APP_CONFIG_FILE before Settings() is constructed)
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

import structlog
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

logger = structlog.get_logger(__name__)

_DEFAULT_TOML = Path.home() / ".hard-cli.toml"

# Module-level singleton — initialised once by init_settings() in main.py
_settings: Settings | None = None


class Settings(BaseSettings):
    """Resolved application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = Field(default="hard-cli", description="Application display name")
    app_version: str = Field(default="0.1.0", description="Application version")

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Logging level")
    json_logs: bool = Field(default=False, description="Emit JSON log lines")

    # ── Behaviour ─────────────────────────────────────────────────────────────
    debug: bool = Field(
        default=False, description="Enable debug mode (verbose tracebacks)"
    )

    # ── Network defaults (used by ping command) ───────────────────────────────
    default_port: int = Field(default=80, ge=1, le=65535)
    default_timeout: float = Field(default=5.0, ge=0.1, le=60.0)
    default_retries: int = Field(default=3, ge=0, le=10)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        toml_source = _build_toml_source(settings_cls)
        sources: tuple[PydanticBaseSettingsSource, ...] = (
            init_settings,
            env_settings,
            dotenv_settings,
        )
        if toml_source is not None:
            sources = (*sources, toml_source)
        return (*sources, file_secret_settings)


def _build_toml_source(
    settings_cls: type[BaseSettings],
) -> TomlConfigSettingsSource | None:
    """Return a TOML settings source if a config file can be located."""
    raw = os.environ.get("APP_CONFIG_FILE")
    path = Path(raw) if raw else _DEFAULT_TOML

    if not path.exists():
        logger.debug("toml_config_not_found", path=str(path))
        return None

    # Validate the TOML is parseable before handing it to pydantic-settings.
    # A parse error here surfaces as ConfigError in main.py, not a cryptic
    # pydantic internal stack trace.
    try:
        with path.open("rb") as fh:
            tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        # Delay import to avoid circular; errors module does not import config.
        from cli.core.errors import ConfigError  # noqa: PLC0415

        raise ConfigError(
            f"TOML config is malformed: {path}",
            hint=f"Fix the syntax error: {exc}",
        ) from exc

    logger.debug("toml_config_loaded", path=str(path))
    return TomlConfigSettingsSource(settings_cls, toml_file=path)


def get_field_sources(settings: Settings) -> dict[str, Any]:
    """Return a dict of {field_name: resolved_value} for display purposes."""
    return settings.model_dump()


# ── Public API ────────────────────────────────────────────────────────────────

def init_settings(config_file: Path | None = None) -> Settings:
    """Construct and cache the Settings singleton.

    Call this exactly once from ``@app.callback()`` before any command runs.
    Subsequent calls to ``get_settings()`` return the cached instance.

    Args:
        config_file: Explicit config file path (from --config flag).
    """
    global _settings
    if config_file is not None:
        os.environ["APP_CONFIG_FILE"] = str(config_file)
    _settings = Settings()
    return _settings


def get_settings() -> Settings:
    """Return the cached Settings singleton.

    Raises:
        RuntimeError: If called before ``init_settings()``.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
