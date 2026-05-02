"""Integration tests for the `ping host` command via typer CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

from cli.core.errors import ExitCode
from cli.main import app

runner = CliRunner()


# ── Validation errors (never reaches network call) ────────────────────────────

def test_ping_blank_host() -> None:
    result = runner.invoke(app, ["ping", "host", "   "])
    assert result.exit_code == ExitCode.VALIDATION_ERROR


def test_ping_port_out_of_range() -> None:
    result = runner.invoke(app, ["ping", "host", "example.com", "--port", "99999"])
    assert result.exit_code != 0


def test_ping_short_timeout_with_retries() -> None:
    # timeout=0.5 + retries=3 → cross-field Pydantic error → ValidationError
    result = runner.invoke(
        app,
        ["ping", "host", "example.com", "--timeout", "0.5", "--retries", "3"],
    )
    assert result.exit_code == ExitCode.VALIDATION_ERROR


# ── Network error (simulated — all hosts fail) ────────────────────────────────

def test_ping_network_error_no_retry() -> None:
    result = runner.invoke(
        app,
        ["ping", "host", "down.example.com", "--retries", "0"],
    )
    assert result.exit_code == ExitCode.NETWORK_ERROR


def test_ping_network_error_with_retry() -> None:
    # Exhausts retries, re-raises NetworkError
    result = runner.invoke(
        app,
        ["ping", "host", "down.example.com", "--retries", "2"],
    )
    assert result.exit_code == ExitCode.NETWORK_ERROR


def test_ping_timeout_error() -> None:
    result = runner.invoke(
        app,
        ["ping", "host", "timeout.local", "--retries", "0"],
    )
    assert result.exit_code == ExitCode.TIMEOUT_ERROR


def test_ping_displays_resolved_args() -> None:
    # Even though the connection fails, the summary table is printed first.
    result = runner.invoke(
        app,
        ["ping", "host", "api.example.com", "--port", "443", "--retries", "0"],
    )
    assert "api.example.com" in result.output
    assert "443" in result.output
