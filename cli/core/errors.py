"""
Error hierarchy, exit codes, and the central error handler.

Design:
  - Every application error is a HardCLIError subclass.
  - Each subclass declares a unique exit_code so callers (CI, scripts) can
    distinguish error classes without parsing text.
  - An optional `hint` gives the user a next-action suggestion.
  - handle_error() is the single place that formats and prints errors;
    --debug enables rich tracebacks with local variables.
  - error_handler() is a context manager for use inside command functions;
    it catches HardCLIError and unexpected exceptions, prints them via
    handle_error(), and re-raises as typer.Exit(code) so that typer (and
    CliRunner in tests) propagates the correct exit code.
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager
from enum import IntEnum
from typing import ClassVar

from rich.console import Console
from rich.panel import Panel

_err = Console(stderr=True)


# ── Exit codes ────────────────────────────────────────────────────────────────

class ExitCode(IntEnum):
    OK               = 0
    GENERIC_ERROR    = 1
    VALIDATION_ERROR = 2   # Bad user input (wrong type, out of range, …)
    CONFIG_ERROR     = 3   # Malformed or missing config file
    PATH_ERROR       = 4   # File / directory not found or not accessible
    NETWORK_ERROR    = 5   # Remote host unreachable or refused connection
    PERMISSION_ERROR = 6   # Insufficient OS permissions
    TIMEOUT_ERROR    = 7   # Operation exceeded time limit
    UNEXPECTED_ERROR = 99  # Unhandled exception — likely a bug


# ── Exception hierarchy ───────────────────────────────────────────────────────

class HardCLIError(Exception):
    """Base class for all application errors.

    Args:
        message: Human-readable description shown to the user.
        hint: Optional follow-up suggestion (e.g. "Run `config show` to …").
    """

    exit_code: ClassVar[int] = ExitCode.GENERIC_ERROR

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ValidationError(HardCLIError):
    """Raised when CLI arguments fail semantic validation."""
    exit_code = ExitCode.VALIDATION_ERROR


class ConfigError(HardCLIError):
    """Raised when the TOML config file is missing, unreadable, or malformed."""
    exit_code = ExitCode.CONFIG_ERROR


class PathError(HardCLIError):
    """Raised when a required file or directory does not exist."""
    exit_code = ExitCode.PATH_ERROR


class NetworkError(HardCLIError):
    """Raised when a remote host is unreachable or returns an error."""
    exit_code = ExitCode.NETWORK_ERROR


class PermissionDeniedError(HardCLIError):
    """Raised when the process lacks permissions to perform an operation."""
    exit_code = ExitCode.PERMISSION_ERROR


class TimeoutError(HardCLIError):
    """Raised when an operation exceeds its time limit."""
    exit_code = ExitCode.TIMEOUT_ERROR


# ── Error handler ─────────────────────────────────────────────────────────────

_BUG_REPORT_URL = "https://github.com/miqui/hard-cli/issues"


def handle_error(exc: BaseException, *, debug: bool = False) -> int:
    """Format *exc*, print it to stderr, and return the appropriate exit code.

    Args:
        exc:   The caught exception.
        debug: When True, print a full rich traceback with local variables.

    Returns:
        Integer exit code suitable for ``sys.exit()``.
    """
    import typer  # local import avoids circular at module level

    if isinstance(exc, HardCLIError):
        _print_cli_error(exc, debug=debug)
        return exc.exit_code

    # typer.Exit / typer.Abort — not our errors, just exit cleanly
    if isinstance(exc, typer.Exit):
        return int(exc.exit_code) if exc.exit_code is not None else ExitCode.OK
    if isinstance(exc, typer.Abort):
        _err.print("\n[yellow]Aborted.[/yellow]")
        return ExitCode.GENERIC_ERROR

    # Anything else is a bug
    _print_unexpected_error(exc, debug=debug)
    return ExitCode.UNEXPECTED_ERROR


@contextmanager
def error_handler(debug: bool = False) -> Generator[None, None, None]:
    """Context manager for use inside command functions.

    Catches HardCLIError and unexpected exceptions, formats them via
    handle_error(), then raises ``typer.Exit(code)`` so that typer and
    CliRunner propagate the correct integer exit code.

    Usage::

        @app.command()
        def my_command(...) -> None:
            with error_handler(debug=state.debug):
                # all business logic here
                ...

    Args:
        debug: Forward to handle_error() to enable rich tracebacks.
    """
    import typer  # local import avoids circular

    try:
        yield
    except (HardCLIError, Exception) as exc:
        # Let typer's own Exit/Abort pass through unmodified.
        if isinstance(exc, (typer.Exit, typer.Abort, SystemExit)):
            raise
        code = handle_error(exc, debug=debug)
        raise typer.Exit(code) from exc


def _print_cli_error(exc: HardCLIError, *, debug: bool) -> None:
    label = type(exc).__name__.replace("Error", " Error")
    _err.print(f"\n[bold red]✗ {label}[/bold red]  [red]{exc.message}[/red]")
    if exc.hint:
        _err.print(f"  [dim]→ {exc.hint}[/dim]")
    if debug:
        _err.print()
        _err.print_exception(show_locals=True)
    _err.print()


def _print_unexpected_error(exc: BaseException, *, debug: bool) -> None:
    _err.print(
        Panel(
            f"[red]{type(exc).__name__}[/red]: {exc}\n\n"
            f"[dim]This looks like a bug. Please report it at[/dim]\n"
            f"[link={_BUG_REPORT_URL}]{_BUG_REPORT_URL}[/link]"
            + (
                ""
                if debug
                else (
                    "\n\n[dim]Run with [bold]--debug[/bold] "
                    "for a full traceback.[/dim]"
                )
            ),
            title="[bold red]✗ Unexpected Error[/bold red]",
            border_style="red",
        )
    )
    if debug:
        _err.print()
        _err.print_exception(show_locals=True)
    sys.stderr.flush()
