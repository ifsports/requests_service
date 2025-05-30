set -e

echo "Database is reported as healthy by Docker Compose. Running migrations..."
alembic upgrade head

exec "$@"