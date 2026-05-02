"""
`process` command — demonstrates file-path and range argument validation.

Error scenarios covered:
  - Input file does not exist         → PathError (exit 4)
  - Input path is a directory         → PathError (exit 4)
  - count out of range                → caught by typer before reaching Pydantic
  - output_dir does not exist         → PathError (exit 4)
  - output_dir exists but is a file   → PathError (exit 4)
  - Pydantic multi-field failure      → ValidationError (exit 2)

The command body is a no-op: it prints a rich summary of what *would* happen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pydantic
import structlog
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.core.errors import PathError, ValidationError, error_handler
from cli.core.validation import OutputFormat, ProcessArgs, format_pydantic_error
from cli.state import state

logger = structlog.get_logger(__name__)
console = Console()

app = typer.Typer(help="File processing commands.")


@app.command("run")
def process_run(
    path: Annotated[
        Path,
        typer.Argument(help="Input file to process. Must exist and be a regular file."),
    ],
    count: Annotated[
        int,
        typer.Option(
            "--count", "-c",
            min=1, max=1000,
            help="Number of records to process. Range: 1–1000.",
        ),
    ] = 10,
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir", "-o",
            help="Directory to write results. Must exist.",
        ),
    ] = None,
    fmt: Annotated[
        OutputFormat,
        typer.Option(
            "--format", "-f",
            help="Output format.",
        ),
    ] = OutputFormat.table,
) -> None:
    """Process an input file and write results.

    This command is a no-op template. It demonstrates how to validate
    file paths and integer ranges before executing business logic.

    Examples:

    \b
        hard-cli process run ./data.csv
        hard-cli process run ./data.csv --count 500 --format json
        hard-cli process run ./data.csv --output-dir ./out/
    """
    with error_handler(debug=state.debug):
        logger.info("process_run_called", path=str(path), count=count, fmt=fmt.value)

        # ── Semantic validation via Pydantic ──────────────────────────────────────
        # Typer already checked count is in [1, 1000]. Pydantic checks that the
        # paths actually exist on disk and have the right type (file vs dir).
        try:
            args = ProcessArgs(path=path, count=count, output_dir=output_dir, fmt=fmt)
        except pydantic.ValidationError as exc:
            msg = format_pydantic_error(exc)
            # Inspect which fields failed to emit a more specific error type.
            failed = {e["loc"][0] for e in exc.errors() if e["loc"]}
            if failed & {"path", "output_dir"}:
                raise PathError(
                    msg,
                    hint="Check that the paths exist and have the right type.",
                ) from exc
            raise ValidationError(msg) from exc

        # ── No-op: display resolved args ─────────────────────────────────────────
        _print_summary(args)
        logger.info("process_run_complete", path=str(args.path), count=args.count)


def _print_summary(args: ProcessArgs) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Input file",   str(args.path))
    table.add_row("Record count", str(args.count))
    table.add_row(
        "Output dir",
        str(args.output_dir) if args.output_dir else "[dim]stdout[/dim]",
    )
    table.add_row("Format", args.fmt.value)

    console.print(
        Panel(
            table,
            title="[bold]process run[/bold] — resolved arguments",
            subtitle="[dim](no-op)[/dim]",
            border_style="blue",
        )
    )
    console.print("[green]✓[/green] Arguments validated. Nothing was written.")
