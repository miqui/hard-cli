"""Tests for the error hierarchy and handle_error()."""

from __future__ import annotations

import pytest
import typer

from cli.core.errors import (
    ConfigError,
    ExitCode,
    HardCLIError,
    NetworkError,
    PathError,
    PermissionDeniedError,
    TimeoutError,
    ValidationError,
    handle_error,
)

# ── Exit code assertions ──────────────────────────────────────────────────────

def test_exit_codes_are_unique() -> None:
    codes = [e.value for e in ExitCode]
    assert len(codes) == len(set(codes)), "Exit codes must be unique"


@pytest.mark.parametrize("cls,expected_code", [
    (HardCLIError,        ExitCode.GENERIC_ERROR),
    (ValidationError,     ExitCode.VALIDATION_ERROR),
    (ConfigError,         ExitCode.CONFIG_ERROR),
    (PathError,           ExitCode.PATH_ERROR),
    (NetworkError,        ExitCode.NETWORK_ERROR),
    (PermissionDeniedError, ExitCode.PERMISSION_ERROR),
    (TimeoutError,        ExitCode.TIMEOUT_ERROR),
])
def test_error_exit_codes(cls: type[HardCLIError], expected_code: ExitCode) -> None:
    exc = cls("test message")
    assert exc.exit_code == expected_code


# ── HardCLIError construction ─────────────────────────────────────────────────

def test_hard_cli_error_message() -> None:
    exc = HardCLIError("something went wrong")
    assert exc.message == "something went wrong"
    assert exc.hint is None


def test_hard_cli_error_with_hint() -> None:
    exc = ValidationError("bad value", hint="Try a number between 1 and 100.")
    assert exc.hint == "Try a number between 1 and 100."


def test_hard_cli_error_is_exception() -> None:
    with pytest.raises(HardCLIError):
        raise PathError("not found")


# ── handle_error() ────────────────────────────────────────────────────────────

def test_handle_error_returns_correct_exit_code() -> None:
    exc = NetworkError("connection refused")
    code = handle_error(exc, debug=False)
    assert code == ExitCode.NETWORK_ERROR


def test_handle_error_typer_exit_zero() -> None:
    exc = typer.Exit(code=0)
    assert handle_error(exc) == ExitCode.OK


def test_handle_error_typer_exit_nonzero() -> None:
    exc = typer.Exit(code=2)
    assert handle_error(exc) == 2


def test_handle_error_unexpected_returns_99() -> None:
    exc = RuntimeError("oops")
    code = handle_error(exc, debug=False)
    assert code == ExitCode.UNEXPECTED_ERROR


def test_handle_error_typer_abort() -> None:
    exc = typer.Abort()
    code = handle_error(exc, debug=False)
    assert code == ExitCode.GENERIC_ERROR
