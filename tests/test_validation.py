"""Tests for Pydantic validation models."""

from __future__ import annotations

from pathlib import Path

import pydantic
import pytest

from cli.core.validation import (
    OutputFormat,
    PingArgs,
    ProcessArgs,
    format_pydantic_error,
)

# ── ProcessArgs ───────────────────────────────────────────────────────────────

def test_process_args_valid_file(tmp_path: Path) -> None:
    f = tmp_path / "data.csv"
    f.write_text("a,b,c")
    args = ProcessArgs(path=f, count=10)
    assert args.path == f.resolve()
    assert args.count == 10
    assert args.output_dir is None
    assert args.fmt == OutputFormat.table


def test_process_args_file_not_found() -> None:
    with pytest.raises(pydantic.ValidationError, match="file not found"):
        ProcessArgs(path=Path("/does/not/exist.csv"))


def test_process_args_path_is_directory(tmp_path: Path) -> None:
    with pytest.raises(pydantic.ValidationError, match="not a regular file"):
        ProcessArgs(path=tmp_path)


def test_process_args_output_dir_valid(tmp_path: Path) -> None:
    f = tmp_path / "input.txt"
    f.write_text("x")
    out = tmp_path / "out"
    out.mkdir()
    args = ProcessArgs(path=f, output_dir=out)
    assert args.output_dir == out.resolve()


def test_process_args_output_dir_not_found(tmp_path: Path) -> None:
    f = tmp_path / "input.txt"
    f.write_text("x")
    with pytest.raises(pydantic.ValidationError, match="directory not found"):
        ProcessArgs(path=f, output_dir=tmp_path / "missing")


def test_process_args_output_dir_is_file(tmp_path: Path) -> None:
    f = tmp_path / "input.txt"
    f.write_text("x")
    not_a_dir = tmp_path / "notdir.txt"
    not_a_dir.write_text("y")
    with pytest.raises(pydantic.ValidationError, match="not a directory"):
        ProcessArgs(path=f, output_dir=not_a_dir)


def test_process_args_count_defaults_to_10(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("x")
    assert ProcessArgs(path=f).count == 10


def test_process_args_all_output_formats(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("x")
    for fmt in OutputFormat:
        args = ProcessArgs(path=f, fmt=fmt)
        assert args.fmt == fmt


# ── PingArgs ──────────────────────────────────────────────────────────────────

def test_ping_args_valid() -> None:
    args = PingArgs(host="api.example.com", port=443, timeout=10.0, retries=2)
    assert args.host == "api.example.com"
    assert args.port == 443


def test_ping_args_host_stripped() -> None:
    args = PingArgs(host="  myhost  ", port=80, timeout=5.0, retries=0)
    assert args.host == "myhost"


def test_ping_args_blank_host() -> None:
    with pytest.raises(pydantic.ValidationError, match="blank"):
        PingArgs(host="   ", port=80, timeout=5.0, retries=0)


def test_ping_args_port_out_of_range() -> None:
    with pytest.raises(pydantic.ValidationError):
        PingArgs(host="h", port=99999, timeout=5.0, retries=0)


def test_ping_args_timeout_too_short_with_retries() -> None:
    with pytest.raises(pydantic.ValidationError, match="very short"):
        PingArgs(host="h", port=80, timeout=0.5, retries=3)


def test_ping_args_short_timeout_no_retries_ok() -> None:
    # timeout < 1.0 is fine when retries=0
    args = PingArgs(host="h", port=80, timeout=0.5, retries=0)
    assert args.timeout == 0.5


# ── format_pydantic_error ─────────────────────────────────────────────────────

def test_format_pydantic_error_contains_field_name() -> None:
    try:
        PingArgs(host="", port=80, timeout=5.0, retries=0)
    except pydantic.ValidationError as exc:
        msg = format_pydantic_error(exc)
        assert "Argument validation failed" in msg
