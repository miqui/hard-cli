"""Integration tests for the `process run` command via typer CliRunner."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cli.core.errors import ExitCode
from cli.main import app

runner = CliRunner()


# ── Happy path ────────────────────────────────────────────────────────────────

def test_process_run_valid_file(tmp_path: Path) -> None:
    f = tmp_path / "data.csv"
    f.write_text("a,b")
    result = runner.invoke(app, ["process", "run", str(f)])
    assert result.exit_code == 0
    assert "Arguments validated" in result.output


def test_process_run_with_count(tmp_path: Path) -> None:
    f = tmp_path / "data.csv"
    f.write_text("x")
    result = runner.invoke(app, ["process", "run", str(f), "--count", "100"])
    assert result.exit_code == 0
    assert "100" in result.output


def test_process_run_with_output_dir(tmp_path: Path) -> None:
    f = tmp_path / "data.csv"
    f.write_text("x")
    out = tmp_path / "out"
    out.mkdir()
    result = runner.invoke(app, ["process", "run", str(f), "--output-dir", str(out)])
    assert result.exit_code == 0


def test_process_run_all_formats(tmp_path: Path) -> None:
    f = tmp_path / "data.csv"
    f.write_text("x")
    for fmt in ("json", "csv", "table"):
        result = runner.invoke(app, ["process", "run", str(f), "--format", fmt])
        assert result.exit_code == 0, f"format={fmt} failed: {result.output}"


# ── Error paths ───────────────────────────────────────────────────────────────

def test_process_run_file_not_found() -> None:
    result = runner.invoke(app, ["process", "run", "/no/such/file.csv"])
    assert result.exit_code == ExitCode.PATH_ERROR


def test_process_run_path_is_directory(tmp_path: Path) -> None:
    result = runner.invoke(app, ["process", "run", str(tmp_path)])
    assert result.exit_code == ExitCode.PATH_ERROR


def test_process_run_output_dir_missing(tmp_path: Path) -> None:
    f = tmp_path / "data.csv"
    f.write_text("x")
    result = runner.invoke(
        app, ["process", "run", str(f), "--output-dir", str(tmp_path / "missing")]
    )
    assert result.exit_code == ExitCode.PATH_ERROR


def test_process_run_count_out_of_range(tmp_path: Path) -> None:
    f = tmp_path / "data.csv"
    f.write_text("x")
    # typer rejects values outside min=1 max=1000
    result = runner.invoke(app, ["process", "run", str(f), "--count", "9999"])
    assert result.exit_code != 0


def test_process_run_count_zero(tmp_path: Path) -> None:
    f = tmp_path / "data.csv"
    f.write_text("x")
    result = runner.invoke(app, ["process", "run", str(f), "--count", "0"])
    assert result.exit_code != 0
