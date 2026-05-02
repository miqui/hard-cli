# hard-cli

A hardened Python CLI template focused on robust argument handling and structured error handling. The CLI is a no-op — every command validates its inputs and then shows a summary of what *would* happen, making the patterns easy to copy into real projects.

## What it demonstrates

**Argument handling**
- Required and optional arguments with type coercion (typer)
- Integer and float range constraints (`min=` / `max=` on `typer.Option`)
- File path validation: must exist, must be a file / directory
- Enum choices (`--format json|csv|table`)
- Cross-field constraints via Pydantic `@model_validator`
- Config file (TOML) loaded with `pydantic-settings TomlConfigSettingsSource`
- Environment variable overrides with `APP_` prefix
- `--config` flag to select a non-default TOML file at runtime

**Error handling**
- Typed exception hierarchy with unique exit codes (see `cli/core/errors.py`)
- Single top-level error handler in `cli/main.py:run()`
- `--debug` flag switches from clean one-liners to full rich tracebacks
- `tenacity` retry with exponential back-off for transient network errors
- Distinct handling for: ValidationError, ConfigError, PathError, NetworkError, TimeoutError, PermissionDeniedError, and unexpected exceptions

## Prerequisites

- Python 3.11+
- uv >= 0.11.7
- Docker (for image builds)

## Installation

```bash
uv sync
```

## Running locally

```bash
# Show help
uv run python -m cli.main --help

# process run — file path + range validation
uv run python -m cli.main process run ./pyproject.toml
uv run python -m cli.main process run ./pyproject.toml --count 500 --format json
uv run python -m cli.main process run /no/such/file.csv            # → PathError

# ping host — network error + tenacity retry
uv run python -m cli.main ping host api.example.com
uv run python -m cli.main ping host api.example.com --retries 0   # → NetworkError (no retry)
uv run python -m cli.main ping host timeout.local                  # → TimeoutError

# config show — resolved settings from TOML + env
uv run python -m cli.main config show
uv run python -m cli.main config validate --path .hard-cli.toml.example

# Debug mode — full tracebacks
uv run python -m cli.main --debug ping host timeout.local
```

## Docker

```bash
docker build -t hard-cli:latest .
docker buildx build --platform linux/amd64,linux/arm64 -t hard-cli:latest .

docker run --rm hard-cli:latest --help
docker run --rm hard-cli:latest process run /no/such/file   # PathError, exit 4
```

## Configuration

Priority (highest → lowest):

| Source           | Example                             |
|------------------|-------------------------------------|
| Environment var  | `APP_LOG_LEVEL=DEBUG`               |
| .env file        | `APP_DEBUG=true`                    |
| TOML config file | `log_level = "DEBUG"` in `.toml`    |
| Built-in default | `"INFO"`                            |

Copy `.hard-cli.toml.example` to `~/.hard-cli.toml` to use the default location, or pass `--config ./path/to/file.toml`.

## Environment variables

| Variable             | Description                          | Default          |
|----------------------|--------------------------------------|------------------|
| APP_LOG_LEVEL        | Logging level                        | `INFO`           |
| APP_JSON_LOGS        | Emit JSON log lines                  | `false`          |
| APP_DEBUG            | Full tracebacks on error             | `false`          |
| APP_CONFIG_FILE      | Path to TOML config file             | `~/.hard-cli.toml` |
| APP_DEFAULT_PORT     | Default port for `ping host`         | `80`             |
| APP_DEFAULT_TIMEOUT  | Default timeout for `ping host`      | `5.0`            |
| APP_DEFAULT_RETRIES  | Default retries for `ping host`      | `3`              |

## Exit codes

| Code | Meaning              |
|------|----------------------|
| 0    | OK                   |
| 1    | Generic error        |
| 2    | Validation error     |
| 3    | Config error         |
| 4    | Path error           |
| 5    | Network error        |
| 6    | Permission error     |
| 7    | Timeout error        |
| 99   | Unexpected exception |

## Project structure

```
hard-cli/
  cli/
    main.py              Entry point; global flags; top-level error handler
    commands/
      process.py         process run — file path + range args
      ping.py            ping host — network errors + tenacity retry
      config.py          config show / validate — TOML inspection
    core/
      errors.py          Exception hierarchy, ExitCode enum, handle_error()
      config.py          Settings (TOML + env + defaults via pydantic-settings)
      logging.py         structlog setup → stderr
      validation.py      Pydantic models for semantic arg validation
  tests/
    test_errors.py       Unit tests: error classes, exit codes, handle_error()
    test_validation.py   Unit tests: ProcessArgs, PingArgs validators
    test_process.py      Integration: process run happy + error paths
    test_ping.py         Integration: ping host validation + network errors
    test_config_cmd.py   Integration: config show / validate
  .github/workflows/ci.yml
  Dockerfile
  .hard-cli.toml.example
  .env.example
  pyproject.toml
```

## Running tests

```bash
uv run pytest
uv run pytest -v
uv run pytest --tb=short -q     # compact CI style
```
