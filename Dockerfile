# ── Stage 1: Dependency builder ────────────────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy only manifests — code changes don't bust this cache layer
COPY pyproject.toml uv.lock ./

# Install production dependencies into isolated virtualenv
RUN uv sync --frozen --no-dev --no-install-project

# ── Stage 2: Runtime image ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# WeasyPrint HTML→PDF engine requires Pango, Cairo, and GDK-Pixbuf system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libffi8 \
    fontconfig \
    fonts-liberation \
    gobject-introspection \
    libgirepository-1.0-1 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN useradd --create-home --uid 1000 app

WORKDIR /app

# Virtualenv from builder stage
COPY --from=builder /app/.venv /app/.venv

# Application source
COPY --chown=app:app . .

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

# entrypoint.sh runs as root to create /data and fix volume permissions,
# then starts alembic + uvicorn
ENTRYPOINT ["/entrypoint.sh"]
