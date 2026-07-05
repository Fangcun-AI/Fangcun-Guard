#!/usr/bin/env python3
"""
Database Migration Runner
Automatically runs pending SQL migrations in order
"""

import os  # fcg-rewrite
import sys  # fcg-rewrite
from pathlib import Path  # fcg-rewrite
from typing import List, Tuple  # fcg-rewrite
import asyncio  # fcg-rewrite
from sqlalchemy import text  # fcg-rewrite

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))  # fcg-rewrite

from config import settings  # fcg-rewrite
from database.connection import admin_engine  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

MIGRATIONS_DIR = Path(__file__).parent / "versions"  # fcg-rewrite
MIGRATION_TABLE = "schema_migrations"  # fcg-rewrite


def get_migration_files() -> List[Tuple[int, str, Path]]:  # fcg-rewrite
    """
    Get all migration files sorted by version number

    Returns:
        List of tuples: (version_number, description, file_path)
    """
    migrations = []  # fcg-rewrite

    if not MIGRATIONS_DIR.exists():  # fcg-rewrite
        logger.warning(f"Migrations directory not found: {MIGRATIONS_DIR}")  # fcg-rewrite
        return migrations  # fcg-rewrite

    for file_path in MIGRATIONS_DIR.glob("*.sql"):  # fcg-rewrite
        filename = file_path.name  # fcg-rewrite

        # Parse filename: 001_description.sql
        try:
            parts = filename.replace(".sql", "").split("_", 1)  # fcg-rewrite
            version = int(parts[0])  # fcg-rewrite
            description = parts[1] if len(parts) > 1 else "unnamed"  # fcg-rewrite
            migrations.append((version, description, file_path))  # fcg-rewrite
        except (ValueError, IndexError) as e:  # fcg-rewrite
            logger.warning(f"Skipping invalid migration filename: {filename} ({e})")  # fcg-rewrite
            continue  # fcg-rewrite

    # Sort by version number
    migrations.sort(key=lambda x: x[0])  # fcg-rewrite
    return migrations  # fcg-rewrite


def create_migration_table(conn):  # fcg-rewrite
    """Create the schema_migrations table if it doesn't exist"""
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
        version INTEGER PRIMARY KEY,
        description VARCHAR(255) NOT NULL,
        filename VARCHAR(255) NOT NULL,
        executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        success BOOLEAN DEFAULT true,
        error_message TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_schema_migrations_executed_at
    ON {MIGRATION_TABLE}(executed_at);
    """

    conn.execute(text(create_table_sql))  # fcg-rewrite
    conn.commit()  # fcg-rewrite
    logger.info(f"Migration tracking table '{MIGRATION_TABLE}' ready")  # fcg-rewrite


def get_executed_migrations(conn) -> set:  # fcg-rewrite
    """Get set of already executed migration versions"""
    result = conn.execute(  # fcg-rewrite
        text(f"SELECT version FROM {MIGRATION_TABLE} WHERE success = true")  # fcg-rewrite
    )
    return {row[0] for row in result}  # fcg-rewrite


def execute_migration(conn, version: int, description: str, file_path: Path) -> bool:  # fcg-rewrite
    """
    Execute a single migration file

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Executing migration {version}: {description}")  # fcg-rewrite

    try:
        # Read SQL file
        with open(file_path, 'r', encoding='utf-8') as f:  # fcg-rewrite
            sql_content = f.read()  # fcg-rewrite

        # Execute SQL (may contain multiple statements)
        conn.execute(text(sql_content))  # fcg-rewrite

        # Record successful execution (use INSERT ON CONFLICT for idempotency)
        conn.execute(  # fcg-rewrite
            text(f"""
                INSERT INTO {MIGRATION_TABLE}
                (version, description, filename, success)
                VALUES (:version, :description, :filename, true)
                ON CONFLICT (version) DO UPDATE SET
                    description = EXCLUDED.description,
                    filename = EXCLUDED.filename,
                    executed_at = CURRENT_TIMESTAMP,
                    success = true,
                    error_message = NULL
            """),
            {
                "version": version,  # fcg-rewrite
                "description": description,  # fcg-rewrite
                "filename": file_path.name  # fcg-rewrite
            }
        )

        conn.commit()  # fcg-rewrite
        logger.info(f"✓ Migration {version} completed successfully")  # fcg-rewrite
        return True  # fcg-rewrite

    except Exception as e:  # fcg-rewrite
        conn.rollback()  # fcg-rewrite
        error_msg = str(e)  # fcg-rewrite
        logger.error(f"✗ Migration {version} failed: {error_msg}")  # fcg-rewrite

        # Record failed execution (use INSERT ON CONFLICT for idempotency)
        try:
            conn.execute(  # fcg-rewrite
                text(f"""
                    INSERT INTO {MIGRATION_TABLE}
                    (version, description, filename, success, error_message)
                    VALUES (:version, :description, :filename, false, :error)
                    ON CONFLICT (version) DO UPDATE SET
                        description = EXCLUDED.description,
                        filename = EXCLUDED.filename,
                        executed_at = CURRENT_TIMESTAMP,
                        success = false,
                        error_message = EXCLUDED.error_message
                """),
                {
                    "version": version,  # fcg-rewrite
                    "description": description,  # fcg-rewrite
                    "filename": file_path.name,  # fcg-rewrite
                    "error": error_msg[:1000]  # Limit error message length  # fcg-rewrite
                }
            )
            conn.commit()  # fcg-rewrite
        except Exception as record_error:  # fcg-rewrite
            logger.error(f"Failed to record migration failure: {record_error}")  # fcg-rewrite

        return False  # fcg-rewrite


def run_migrations(dry_run: bool = False) -> Tuple[int, int]:  # fcg-rewrite
    """
    Run all pending migrations

    Args:
        dry_run: If True, only show what would be executed

    Returns:
        Tuple of (executed_count, failed_count)
    """
    logger.info("=" * 60)  # fcg-rewrite
    logger.info("Database Migration Runner")  # fcg-rewrite
    logger.info("=" * 60)  # fcg-rewrite

    # Get all migration files
    migrations = get_migration_files()  # fcg-rewrite

    if not migrations:  # fcg-rewrite
        logger.info("No migration files found")  # fcg-rewrite
        return 0, 0  # fcg-rewrite

    logger.info(f"Found {len(migrations)} migration file(s)")  # fcg-rewrite

    # Use a migration-specific lock to prevent concurrent migration execution
    migration_lock_key = 0x4D49_4752_4154_494F  # "MIGRATIO" in hex  # fcg-rewrite

    # Connect to database with autocommit to manage locks
    with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock_conn:  # fcg-rewrite
        # Try to acquire migration lock with a short timeout
        result = lock_conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": migration_lock_key})  # fcg-rewrite
        lock_acquired = result.scalar()  # fcg-rewrite

        if not lock_acquired:  # fcg-rewrite
            logger.info("Another process is running migrations, skipping...")  # fcg-rewrite
            return 0, 0  # fcg-rewrite

        try:
            # Now run migrations in a separate connection/transaction
            executed, failed = _apply_migrations(migrations, dry_run)  # fcg-rewrite
            return executed, failed  # fcg-rewrite
        finally:  # fcg-rewrite
            # Release migration lock
            lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": migration_lock_key})  # fcg-rewrite


def _apply_migrations(migrations: List[Tuple[int, str, Path]], dry_run: bool) -> Tuple[int, int]:  # fcg-rewrite
    """Internal migration runner with separate connection"""
    # Connect to database
    with admin_engine.connect() as conn:  # fcg-rewrite
        # Create migration tracking table
        create_migration_table(conn)  # fcg-rewrite

        # Get already executed migrations
        executed = get_executed_migrations(conn)  # fcg-rewrite

        # Filter pending migrations
        pending = [m for m in migrations if m[0] not in executed]  # fcg-rewrite

        if not pending:  # fcg-rewrite
            logger.info("✓ All migrations are up to date")  # fcg-rewrite
            return 0, 0  # fcg-rewrite

        logger.info(f"Found {len(pending)} pending migration(s):")  # fcg-rewrite
        for version, description, file_path in pending:  # fcg-rewrite
            logger.info(f"  - {version:03d}: {description}")  # fcg-rewrite

        if dry_run:  # fcg-rewrite
            logger.info("\n[DRY RUN] No migrations were executed")  # fcg-rewrite
            return 0, 0  # fcg-rewrite

        logger.info("\nExecuting pending migrations...")  # fcg-rewrite

        executed_count = 0  # fcg-rewrite
        failed_count = 0  # fcg-rewrite

        for version, description, file_path in pending:  # fcg-rewrite
            success = execute_migration(conn, version, description, file_path)  # fcg-rewrite

            if success:  # fcg-rewrite
                executed_count += 1  # fcg-rewrite
            else:
                failed_count += 1  # fcg-rewrite
                logger.error(f"Migration {version} failed. Stopping migration process.")  # fcg-rewrite
                break

        logger.info("=" * 60)  # fcg-rewrite
        logger.info(f"Migration Summary:")  # fcg-rewrite
        logger.info(f"  Executed: {executed_count}")  # fcg-rewrite
        logger.info(f"  Failed: {failed_count}")  # fcg-rewrite
        logger.info("=" * 60)  # fcg-rewrite

        return executed_count, failed_count  # fcg-rewrite


def main():  # fcg-rewrite
    """Main entry point"""
    import argparse  # fcg-rewrite

    parser = argparse.ArgumentParser(description="Run database migrations")  # fcg-rewrite
    parser.add_argument(  # fcg-rewrite
        "--dry-run",  # fcg-rewrite
        action="store_true",  # fcg-rewrite
        help="Show pending migrations without executing them"  # fcg-rewrite
    )

    args = parser.parse_args()  # fcg-rewrite

    try:
        executed, failed = run_migrations(dry_run=args.dry_run)  # fcg-rewrite

        if failed > 0:  # fcg-rewrite
            sys.exit(1)  # fcg-rewrite

        sys.exit(0)  # fcg-rewrite

    except Exception as e:  # fcg-rewrite
        logger.error(f"Migration runner failed: {e}")  # fcg-rewrite
        import traceback  # fcg-rewrite
        traceback.print_exc()  # fcg-rewrite
        sys.exit(1)  # fcg-rewrite


if __name__ == "__main__":  # fcg-rewrite
    main()
