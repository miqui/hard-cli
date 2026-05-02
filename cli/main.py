"""
Entry point for hard-cli.

Global responsibilities:
  1. Parse global flags: --debug, --config, --log-level, --json-logs, --version
  2. Initialise Settings (TOML + env merge) before any command runs.
  3. Configure structlog.
  4. Populate cli.state.state so command functions can read the debug flag.
  5. Provide a top-level run() wrapper that catches any exception that slips
     past a command's error_handler() and calls sys.exit() with the right code.

Error handling flow (normal path):
  command raises HardCLIError
    → caught by error_handler() context manager inside the command
    → handle_error() formats + prints it
    → re-raised as typer.Exit(code)
    → typer.CliRunner / sys.exit propagates correct exit code

Error handling flow (safety-net path):
  unexpected exception escapes error_handler()
    → caught by run()'s bare except
    → handle_error() formats + prints it
    → sys.exit(99)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from cli.commands import config, ping, process
from cli.core.config import get_settings, init_settings
from cli.core.errors import handle_error
from cli.core.logging import configure_logging
from cli.state import state

console = Console()

app = typer.Typer(
    name="hard-cli",
    help=(
        "Hardened CLI — demonstrates robust argument handling and "
        "structured error handling patterns."
    ),
    add_completion=True,
    no_args_is_help=True,
    pretty_exceptions_enable=False,   # We handle pretty printing ourselves.
)

app.add_typer(process.app, name="process")
app.add_typer(ping.app,    name="ping")
app.add_typer(config.app,  name="config")


# ── Version callback ──────────────────────────────────────────────────────────

def _version_cb(value: bool) -> None:
    if value:
        s = get_settings()
        console.print(
            f"[bold]{s.app_name}[/bold] version [green]{s.app_version}[/green]"
        )
        raise typer.Exit()


# ── Global callback ───────────────────────────────────────────────────────────

@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version", "-V",
            callback=_version_cb,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            envvar="APP_CONFIG_FILE",
            help=(
                "TOML config file path. "
                "Overrides APP_CONFIG_FILE and ~/.hard-cli.toml."
            ),
            exists=False,   # We validate existence ourselves for better messages.
        ),
    ] = None,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            envvar="APP_LOG_LEVEL",
            help="Logging level: DEBUG | INFO | WARNING | ERROR.",
        ),
    ] = "INFO",
    json_logs: Annotated[
        bool,
        typer.Option(
            "--json-logs",
            envvar="APP_JSON_LOGS",
            help="Emit structured JSON log lines (useful in CI).",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            envvar="APP_DEBUG",
            help="Enable debug mode: full rich tracebacks with local variables.",
        ),
    ] = False,
) -> None:
    """hard-cli — global flags available on every sub-command."""
    # 1. Initialise settings so every command can call get_settings().
    settings = init_settings(config_file=config_file)

    # 2. CLI flags beat config file values.
    effective_level = log_level if log_level != "INFO" else settings.log_level
    effective_json  = json_logs or settings.json_logs
    effective_debug = debug or settings.debug

    # 3. Configure logging.
    configure_logging(level=effective_level, json=effective_json)

    # 4. Publish debug flag to shared state so command error_handler()s can read it.
    state.debug = effective_debug


# ── Entry-point wrapper ───────────────────────────────────────────────────────

def run() -> None:
    """Invoke the typer app and handle any exception that escapes commands."""
    try:
        app()
    except Exception as exc:
        code = handle_error(exc, debug=state.debug)
        sys.exit(code)


if __name__ == "__main__":
    run()
