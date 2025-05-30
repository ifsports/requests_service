#!/bin/sh

set -e

echo "Entrypoint: Database (db_requests) is reported as healthy. Running migrations for requests_service..."

alembic upgrade head

echo "Entrypoint: Migrations finished. Starting application (Uvicorn)..."

exec "$@"