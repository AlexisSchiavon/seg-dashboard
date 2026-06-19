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
    libgdk-pixbuf2.0-0 \
    libcairo2 \
    libffi8 \
    fontconfig \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN useradd --create-home --uid 1000 app

WORKDIR /app

# Virtualenv from builder stage
COPY --from=builder /app/.venv /app/.venv

# Application source
COPY --chown=app:app . .

# /data → persistent SQLite volume mount point
# /app/reports → persistent PDF reports volume mount point
RUN mkdir -p /data /app/reports && chown -R app:app /data /app/reports

USER app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Run DB migrations then start (single worker — SQLite serializes writes)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
