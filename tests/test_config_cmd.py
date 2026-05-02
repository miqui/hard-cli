"""Integration tests for the `config` command group."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cli.core.errors import ExitCode
from cli.main import app

runner = CliRunner()


# ── config show ───────────────────────────────────────────────────────────────

def test_config_show_runs() -> None:
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "app_name" in result.output
    assert "log_level" in result.output


def test_config_show_reflects_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")
    # Re-init settings so the new env var is picked up.
    import cli.core.config as _cfg
    _cfg._settings = None
    result = runner.invoke(app, ["--log-level", "DEBUG", "config", "show"])
    assert result.exit_code == 0


# ── config validate ───────────────────────────────────────────────────────────

def test_config_validate_valid_toml(tmp_path: Path) -> None:
    cfg = tmp_path / "test.toml"
    cfg.write_text('log_level = "DEBUG"\ndebug = true\n')
    result = runner.invoke(app, ["config", "validate", "--path", str(cfg)])
    assert result.exit_code == 0
    assert "valid TOML" in result.output


def test_config_validate_file_not_found(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["config", "validate", "--path", str(tmp_path / "missing.toml")]
    )
    assert result.exit_code == ExitCode.CONFIG_ERROR


def test_config_validate_malformed_toml(tmp_path: Path) -> None:
    cfg = tmp_path / "bad.toml"
    cfg.write_text("this is not = [valid toml\n")
    result = runner.invoke(app, ["config", "validate", "--path", str(cfg)])
    assert result.exit_code == ExitCode.CONFIG_ERROR


def test_config_validate_unknown_keys(tmp_path: Path) -> None:
    cfg = tmp_path / "unknown.toml"
    cfg.write_text('unknown_key = "value"\n')
    result = runner.invoke(app, ["config", "validate", "--path", str(cfg)])
    assert result.exit_code == ExitCode.CONFIG_ERROR


def test_config_validate_empty_file_is_ok(tmp_path: Path) -> None:
    cfg = tmp_path / "empty.toml"
    cfg.write_text("")
    result = runner.invoke(app, ["config", "validate", "--path", str(cfg)])
    assert result.exit_code == 0
