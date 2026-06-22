#!/bin/bash
set -e

mkdir -p /data /app/reports
chown -R app:app /data /app/reports

# Guarantee the DB lives on the persistent volume even if EasyPanel env var is missing.
# docker-compose overrides this correctly; this fallback protects bare Docker/EasyPanel runs.
export DATABASE_URL="${DATABASE_URL:-sqlite:////data/seg.db}"

alembic upgrade head
python -m app.scripts.seed_admin
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*'
