"""
`config` command group — inspect and validate the resolved configuration.

Error scenarios covered:
  - Config file path given but file missing  → ConfigError (exit 3)
  - Config file exists but is malformed TOML → ConfigError (exit 3)
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Annotated

import structlog
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.core.config import get_settings
from cli.core.errors import ConfigError, error_handler
from cli.state import state

logger = structlog.get_logger(__name__)
console = Console()

app = typer.Typer(help="Configuration inspection commands.")


@app.command("show")
def config_show() -> None:
    """Display the fully resolved configuration and its active sources.

    Values are merged from (highest → lowest priority):
      1. Environment variables  (APP_ prefix)
      2. .env file
      3. TOML config file       (~/.hard-cli.toml or APP_CONFIG_FILE)
      4. Built-in defaults

    Examples:

    \b
        hard-cli config show
        APP_LOG_LEVEL=DEBUG hard-cli config show
    """
    with error_handler(debug=state.debug):
        settings = get_settings()

        table = Table(title="Resolved Configuration", show_lines=True)
        table.add_column("Key",     style="cyan",  no_wrap=True, width=24)
        table.add_column("Value",   style="green", no_wrap=True)
        table.add_column("Env var", style="dim",   no_wrap=True)

        rows: list[tuple[str, str, str]] = [
            ("app_name",        settings.app_name,               "APP_APP_NAME"),
            ("app_version",     settings.app_version,            "APP_APP_VERSION"),
            ("log_level",       settings.log_level,              "APP_LOG_LEVEL"),
            ("json_logs",       str(settings.json_logs),         "APP_JSON_LOGS"),
            ("debug",           str(settings.debug),             "APP_DEBUG"),
            ("default_port",    str(settings.default_port),      "APP_DEFAULT_PORT"),
            ("default_timeout", f"{settings.default_timeout}s",  "APP_DEFAULT_TIMEOUT"),
            ("default_retries", str(settings.default_retries),   "APP_DEFAULT_RETRIES"),
        ]

        config_file = os.environ.get("APP_CONFIG_FILE", "~/.hard-cli.toml")
        for key, value, env_var in rows:
            table.add_row(key, value, env_var)

        console.print(table)
        console.print(f"[dim]TOML source: {config_file}[/dim]")


@app.command("validate")
def config_validate(
    path: Annotated[
        Path | None,
        typer.Option(
            "--path", "-p",
            help=(
                "TOML config file to validate. "
                "Defaults to APP_CONFIG_FILE or ~/.hard-cli.toml."
            ),
        ),
    ] = None,
) -> None:
    """Validate a TOML config file without applying it.

    Checks:
      - File exists
      - File is valid TOML syntax
      - All keys are recognised settings fields

    Examples:

    \b
        hard-cli config validate
        hard-cli config validate --path ./my-config.toml
    """
    with error_handler(debug=state.debug):
        raw = os.environ.get("APP_CONFIG_FILE", "~/.hard-cli.toml")
        config_path = path or Path(raw).expanduser()

        logger.info("config_validate_called", path=str(config_path))

        # ── Existence check ───────────────────────────────────────────────────────
        if not config_path.exists():
            raise ConfigError(
                f"Config file not found: {config_path}",
                hint=(
                    f"Create it with `touch {config_path}` or pass --path to a "
                    "valid file. See .hard-cli.toml.example for the schema."
                ),
            )

        # ── TOML syntax check ─────────────────────────────────────────────────────
        try:
            with config_path.open("rb") as fh:
                data: dict = tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(
                f"TOML syntax error in {config_path}",
                hint=str(exc),
            ) from exc

        # ── Unknown keys check ────────────────────────────────────────────────────
        from cli.core.config import Settings  # noqa: PLC0415

        known = set(Settings.model_fields.keys())
        unknown = set(data.keys()) - known
        if unknown:
            raise ConfigError(
                f"Unknown config key(s): {', '.join(sorted(unknown))}",
                hint=f"Valid keys are: {', '.join(sorted(known))}",
            )

        # ── All good ──────────────────────────────────────────────────────────────
        console.print(
            Panel(
                f"[green]✓[/green] {config_path} is valid TOML with "
                f"[bold]{len(data)}[/bold] key(s).",
                title="config validate",
                border_style="green",
            )
        )
        logger.info("config_validate_ok", path=str(config_path), keys=len(data))
