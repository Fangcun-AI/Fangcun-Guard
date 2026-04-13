"""
Plugin migration runner — runs SQL migrations from plugin directories.
Uses a separate 'plugin_migrations' table (plugin_name + version composite key).
"""

from pathlib import Path
from typing import Dict
from plugins.base import FangcunPlugin
from utils.logger import setup_logger

logger = setup_logger()

PLUGIN_MIGRATION_TABLE = "plugin_migrations"


def run_plugin_migrations(plugins: Dict[str, FangcunPlugin]) -> None:
    """
    Run pending SQL migrations for all registered plugins.
    Each plugin's migrations are tracked independently via (plugin_name, version).
    """
    from sqlalchemy import text
    from database.connection import admin_engine

    plugins_with_migrations = {}
    for name, plugin in plugins.items():
        migrations_dir = plugin.get_migrations_dir()
        if migrations_dir and migrations_dir.exists():
            plugins_with_migrations[name] = migrations_dir

    if not plugins_with_migrations:
        logger.debug("No plugin migrations to run")
        return

    with admin_engine.connect() as conn:
        # Create plugin migration tracking table
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {PLUGIN_MIGRATION_TABLE} (
                plugin_name VARCHAR(100) NOT NULL,
                version INTEGER NOT NULL,
                description VARCHAR(255) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT true,
                error_message TEXT,
                PRIMARY KEY (plugin_name, version)
            );
        """))
        conn.commit()

        for plugin_name, migrations_dir in plugins_with_migrations.items():
            _run_migrations_for_plugin(conn, plugin_name, migrations_dir)


def _run_migrations_for_plugin(conn, plugin_name: str, migrations_dir: Path) -> None:
    """Run pending migrations for a single plugin"""
    from sqlalchemy import text

    # Discover migration files
    migration_files = []
    for f in sorted(migrations_dir.glob("*.sql")):
        try:
            parts = f.name.replace(".sql", "").split("_", 1)
            version = int(parts[0])
            description = parts[1] if len(parts) > 1 else "unnamed"
            migration_files.append((version, description, f))
        except (ValueError, IndexError):
            logger.warning(f"Skipping invalid plugin migration filename: {f.name}")

    if not migration_files:
        return

    # Get already executed versions
    result = conn.execute(
        text(f"SELECT version FROM {PLUGIN_MIGRATION_TABLE} WHERE plugin_name = :name AND success = true"),
        {"name": plugin_name},
    )
    executed = {row[0] for row in result}

    pending = [(v, d, f) for v, d, f in migration_files if v not in executed]
    if not pending:
        return

    logger.info(f"Plugin '{plugin_name}': {len(pending)} pending migration(s)")

    for version, description, file_path in pending:
        try:
            sql_content = file_path.read_text(encoding="utf-8")
            conn.execute(text(sql_content))
            conn.execute(
                text(f"""
                    INSERT INTO {PLUGIN_MIGRATION_TABLE}
                    (plugin_name, version, description, filename, success)
                    VALUES (:name, :version, :desc, :fname, true)
                    ON CONFLICT (plugin_name, version) DO UPDATE SET
                        description = EXCLUDED.description,
                        filename = EXCLUDED.filename,
                        executed_at = CURRENT_TIMESTAMP,
                        success = true,
                        error_message = NULL
                """),
                {"name": plugin_name, "version": version, "desc": description, "fname": file_path.name},
            )
            conn.commit()
            logger.info(f"Plugin '{plugin_name}' migration {version} OK")
        except Exception as e:
            conn.rollback()
            logger.error(f"Plugin '{plugin_name}' migration {version} FAILED: {e}")
            try:
                conn.execute(
                    text(f"""
                        INSERT INTO {PLUGIN_MIGRATION_TABLE}
                        (plugin_name, version, description, filename, success, error_message)
                        VALUES (:name, :version, :desc, :fname, false, :err)
                        ON CONFLICT (plugin_name, version) DO UPDATE SET
                            executed_at = CURRENT_TIMESTAMP,
                            success = false,
                            error_message = EXCLUDED.error_message
                    """),
                    {"name": plugin_name, "version": version, "desc": description, "fname": file_path.name, "err": str(e)[:1000]},
                )
                conn.commit()
            except Exception:
                pass
            break  # Stop on first failure
