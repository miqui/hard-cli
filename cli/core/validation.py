"""
Pydantic validation models for CLI command arguments.

Typer handles basic type coercion and simple range checks.
These models handle semantic validation:
  - File path must exist and be a regular file.
  - Directory path must exist and be a directory.
  - Cross-field constraints.

Pattern:
    In each command, construct the Pydantic model from the parsed typer args,
    catch pydantic.ValidationError, and convert it to the appropriate
    HardCLIError subclass so the central handler formats it consistently.

Example:
    try:
        args = ProcessArgs(path=path, count=count, output_dir=output_dir)
    except pydantic.ValidationError as exc:
        raise ValidationError(format_pydantic_error(exc)) from exc
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import pydantic
from pydantic import BaseModel, Field, field_validator, model_validator

# ── Shared helpers ────────────────────────────────────────────────────────────

def format_pydantic_error(exc: pydantic.ValidationError) -> str:
    """Flatten a pydantic ValidationError into a single readable string."""
    lines = []
    for err in exc.errors(include_url=False):
        loc = " → ".join(str(p) for p in err["loc"]) if err["loc"] else "value"
        lines.append(f"  [{loc}] {err['msg']}")
    return "Argument validation failed:\n" + "\n".join(lines)


# ── Output format enum ────────────────────────────────────────────────────────

class OutputFormat(StrEnum):
    json  = "json"
    csv   = "csv"
    table = "table"


# ── process command args ──────────────────────────────────────────────────────

class ProcessArgs(BaseModel):
    """Validated arguments for the `process` command."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    path: Path = Field(..., description="Input file to process")
    count: int = Field(default=10, ge=1, le=1000, description="Number of records")
    output_dir: Path | None = Field(default=None, description="Output directory")
    fmt: OutputFormat = Field(default=OutputFormat.table, description="Output format")

    @field_validator("path", mode="after")
    @classmethod
    def path_must_be_existing_file(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"file not found: {v}")
        if not v.is_file():
            raise ValueError(f"path is not a regular file: {v}")
        return v.resolve()

    @field_validator("output_dir", mode="after")
    @classmethod
    def output_dir_must_be_existing_dir(cls, v: Path | None) -> Path | None:
        if v is None:
            return v
        if not v.exists():
            raise ValueError(f"directory not found: {v}")
        if not v.is_dir():
            raise ValueError(f"path is not a directory: {v}")
        return v.resolve()


# ── ping command args ─────────────────────────────────────────────────────────

class PingArgs(BaseModel):
    """Validated arguments for the `ping` command."""

    host: str = Field(..., min_length=1, description="Target hostname or IP")
    port: int = Field(default=80, ge=1, le=65535, description="Target port")
    timeout: float = Field(
        default=5.0, ge=0.1, le=60.0, description="Seconds before timeout"
    )
    retries: int = Field(
        default=3, ge=0, le=10, description="Retry attempts on failure"
    )

    @field_validator("host", mode="after")
    @classmethod
    def host_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("host cannot be blank or whitespace")
        return v.strip()

    @model_validator(mode="after")
    def timeout_must_exceed_minimum_for_retries(self) -> PingArgs:
        """Warn-level constraint: retrying with sub-second timeout is usually wrong."""
        if self.retries > 0 and self.timeout < 1.0:
            raise ValueError(
                f"timeout {self.timeout}s is very short for {self.retries} retries; "
                "use --timeout >= 1.0 or --retries 0"
            )
        return self
