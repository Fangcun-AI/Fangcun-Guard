#!/bin/bash
set -e

echo "=== FangcunGuard Platform Container Starting ==="
echo "Current time: $(date)"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h "${DATABASE_HOST:-postgres}" -U "${DATABASE_USER:-fangcunguard}" -d "${DATABASE_NAME:-fangcunguard}" > /dev/null 2>&1; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is ready!"

# Initialize database schema first (creates all tables)
echo "Initializing database schema..."
cd /app
python3 -c "
import asyncio
from database.connection import init_db
async def main():
    try:
        await init_db(minimal=False)
        print('Database initialization completed successfully')
    except Exception as e:
        print(f'Database initialization failed: {e}')
        raise
asyncio.run(main())
"

# Then run database migrations (only once for the platform container)
echo "Running database migrations..."
python3 migrations/run_migrations.py

# Create necessary directories if they don't exist
echo "Creating necessary directories..."
mkdir -p /mnt/data/fangcunguard-data/media
mkdir -p /mnt/data/fangcunguard-data/logs
mkdir -p /mnt/data/fangcunguard-data/logs/detection

# Set proper permissions
chmod -R 755 /mnt/data/fangcunguard-data

echo "=== Platform Container Initialization Complete ==="
echo "Starting services via supervisord..."

# Execute the CMD passed to the container
exec "$@"
