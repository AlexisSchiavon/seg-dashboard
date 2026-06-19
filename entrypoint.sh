#!/bin/bash
set -e

mkdir -p /data /app/reports
chown -R app:app /data /app/reports

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*'
