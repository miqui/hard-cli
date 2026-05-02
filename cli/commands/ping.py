"""
`ping` command — demonstrates network error handling and tenacity retry.

Error scenarios covered:
  - Host blank / whitespace                 → ValidationError (exit 2)
  - port out of range 1–65535               → caught by typer
  - timeout < 1.0 with retries > 0         → ValidationError (exit 2) via Pydantic
  - Simulated connection refused            → NetworkError (exit 5)
  - Simulated timeout                       → TimeoutError (exit 7)
  - retry exhausted after N attempts        → NetworkError (exit 5)

Hosts that trigger specific simulated errors:
  - "timeout.local"   → TimeoutError on every attempt
  - anything else     → NetworkError (connection refused) on every attempt

The command body is a no-op: it never opens a real socket.
"""

from __future__ import annotations

import time
from typing import Annotated

import pydantic
import structlog
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from cli.core.errors import NetworkError, TimeoutError, ValidationError, error_handler
from cli.core.validation import PingArgs, format_pydantic_error
from cli.state import state

logger = structlog.get_logger(__name__)
console = Console()

app = typer.Typer(help="Network connectivity commands.")


# ── Retry callback (shown to the user between attempts) ──────────────────────

def _on_retry(retry_state: RetryCallState) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    exc_name = type(exc).__name__ if exc else "Error"
    wait = getattr(retry_state.next_action, "sleep", 0.0)
    console.print(
        f"  [yellow]↩ Attempt {retry_state.attempt_number} failed "
        f"({exc_name}). Retrying in {wait:.1f}s…[/yellow]"
    )


# ── Simulated network call (always fails — demo only) ────────────────────────

def _simulate_connect(host: str, port: int, timeout: float) -> None:
    """Pretend to connect; always raises an error for demo purposes.

    Args:
        host:    Target hostname.
        port:    Target port.
        timeout: Connection timeout in seconds.

    Raises:
        TimeoutError: When host is "timeout.local".
        NetworkError: For all other hosts (simulated connection refused).
    """
    logger.debug("simulating_connect", host=host, port=port, timeout=timeout)
    time.sleep(0.05)  # Simulate network latency

    if host == "timeout.local":
        raise TimeoutError(
            f"Connection to {host}:{port} timed out after {timeout}s",
            hint="Check the host is reachable and try a longer --timeout.",
        )
    raise NetworkError(
        f"Connection refused: {host}:{port}",
        hint="Verify the host is running and the port is open.",
    )


# ── Retry-wrapped connector ───────────────────────────────────────────────────

def _connect_with_retry(host: str, port: int, timeout: float, retries: int) -> None:
    """Wrap _simulate_connect with tenacity retry logic.

    Retries only on NetworkError (not TimeoutError — a timeout on every attempt
    is a different failure mode than a transient connection refusal).
    """
    if retries == 0:
        _simulate_connect(host, port, timeout)
        return

    @retry(
        stop=stop_after_attempt(retries + 1),   # +1: first attempt is not a retry
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
        retry=retry_if_exception_type(NetworkError),
        before_sleep=_on_retry,
        reraise=True,
    )
    def _inner() -> None:
        _simulate_connect(host, port, timeout)

    _inner()


# ── Command ───────────────────────────────────────────────────────────────────

@app.command("host")
def ping_host(
    host: Annotated[
        str,
        typer.Argument(help="Target hostname or IP address."),
    ],
    port: Annotated[
        int,
        typer.Option(
            "--port", "-p",
            min=1, max=65535,
            help="Target port. Range: 1–65535.",
        ),
    ] = 80,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout", "-t",
            help="Connection timeout in seconds. Range: 0.1–60.0.",
        ),
    ] = 5.0,
    retries: Annotated[
        int,
        typer.Option(
            "--retries", "-r",
            min=0, max=10,
            help="Retry attempts on transient NetworkError. Range: 0–10.",
        ),
    ] = 3,
) -> None:
    """Check connectivity to a host.

    This command is a no-op template. It demonstrates network error handling
    and tenacity retry with exponential back-off.

    Simulated error triggers:

    \b
        hard-cli ping host timeout.local     → TimeoutError (no retry)
        hard-cli ping host any-other-host    → NetworkError (retried N times)

    Examples:

    \b
        hard-cli ping host api.example.com
        hard-cli ping host api.example.com --port 443 --timeout 10 --retries 5
        hard-cli ping host timeout.local
    """
    with error_handler(debug=state.debug):
        logger.info(
            "ping_called", host=host, port=port, timeout=timeout, retries=retries
        )

        # ── Semantic validation ───────────────────────────────────────────────────
        try:
            args = PingArgs(host=host, port=port, timeout=timeout, retries=retries)
        except pydantic.ValidationError as exc:
            raise ValidationError(
                format_pydantic_error(exc),
                hint="Run `hard-cli ping host --help` for allowed ranges.",
            ) from exc

        # ── Display resolved args ─────────────────────────────────────────────────
        _print_summary(args)

        # ── Attempt connection (always fails — demo only) ─────────────────────────
        console.print(f"[dim]Connecting to {args.host}:{args.port}…[/dim]")

        _connect_with_retry(
            host=args.host,
            port=args.port,
            timeout=args.timeout,
            retries=args.retries,
        )

        # Unreachable in this demo — illustrates the happy path.
        console.print(  # pragma: no cover
            f"[green]✓[/green] Connected to {args.host}:{args.port}"
        )


def _print_summary(args: PingArgs) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Host",    args.host)
    table.add_row("Port",    str(args.port))
    table.add_row("Timeout", f"{args.timeout}s")
    table.add_row("Retries", str(args.retries))

    console.print(
        Panel(
            table,
            title="[bold]ping host[/bold] — resolved arguments",
            border_style="blue",
        )
    )
