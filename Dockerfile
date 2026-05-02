# syntax=docker/dockerfile:1

# ── builder stage ─────────────────────────────────────────────────────────────
FROM python:3.11.13-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --compile-bytecode

# ── runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11.13-slim-bookworm AS runtime

WORKDIR /app

# Harden: strip setuid/setgid bits.
RUN find / -xdev \( -perm -4000 -o -perm -2000 \) -exec chmod ug-s {} + 2>/dev/null || true

# Harden: drop tools that expand attack surface in compromised containers.
RUN apt-get update \
    && apt-get purge -y --auto-remove wget curl 2>/dev/null || true \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --gid 1001 appgroup && \
    adduser --disabled-password --gecos "" --uid 1001 --gid 1001 appuser

COPY --from=builder --chown=appuser:appgroup /app/.venv ./.venv
COPY --chown=appuser:appgroup cli/ ./cli/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

LABEL org.opencontainers.image.base.name="python:3.11.13-slim-bookworm" \
      org.opencontainers.image.source="https://github.com/miqui/hard-cli" \
      org.opencontainers.image.title="hard-cli" \
      org.opencontainers.image.description="Hardened CLI template — robust arg and error handling"

USER appuser

# Run as a module so __main__.py is not needed and the package root is clean.
ENTRYPOINT ["python", "-m", "cli.main"]
CMD ["--help"]
