"""
Migration 013: Add template support for entity types

This migration:
1. Adds source_type column to track entity type source (system_template, system_copy, custom)
2. Adds template_id column to track which template an entity was copied from
3. Migrates existing data:
   - is_global=true -> source_type='system_template'
   - is_global=false -> source_type='custom'

Goal: Enable admin to create system templates that get copied to each tenant,
allowing tenants to edit their own copies without affecting others.
"""

import sys  # fcg-rewrite
import os  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent  # fcg-rewrite
sys.path.insert(0, str(backend_dir))  # fcg-rewrite

from sqlalchemy import text  # fcg-rewrite
from database.connection import engine  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


def upgrade():  # fcg-rewrite
    """Apply the migration"""
    with engine.connect() as conn:  # fcg-rewrite
        try:
            logger.info("Starting migration 013: Add entity type template support")  # fcg-rewrite

            # Step 1: Add source_type column
            logger.info("Adding source_type column...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE data_security_entity_types
                ADD COLUMN IF NOT EXISTS source_type VARCHAR(20) DEFAULT 'custom'
            """))
            
            # Step 2: Add template_id column
            logger.info("Adding template_id column...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE data_security_entity_types
                ADD COLUMN IF NOT EXISTS template_id UUID
            """))
            
            # Step 3: Create index on source_type
            logger.info("Creating index on source_type...")  # fcg-rewrite
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_data_security_entity_types_source_type
                ON data_security_entity_types(source_type)
            """))
            
            # Step 4: Create index on template_id
            logger.info("Creating index on template_id...")  # fcg-rewrite
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_data_security_entity_types_template_id
                ON data_security_entity_types(template_id)
            """))
            
            # Step 5: Migrate existing data
            logger.info("Migrating existing data...")  # fcg-rewrite
            
            # Convert is_global=true to source_type='system_template'
            result = conn.execute(text("""
                UPDATE data_security_entity_types
                SET source_type = 'system_template'
                WHERE is_global = true
            """))
            templates_count = result.rowcount  # fcg-rewrite
            logger.info(f"  Converted {templates_count} global entities to system_template")  # fcg-rewrite
            
            # Convert is_global=false to source_type='custom'
            result = conn.execute(text("""
                UPDATE data_security_entity_types
                SET source_type = 'custom'
                WHERE is_global = false
            """))
            custom_count = result.rowcount  # fcg-rewrite
            logger.info(f"  Converted {custom_count} custom entities")  # fcg-rewrite
            
            conn.commit()  # fcg-rewrite
            
            # Step 6: Verify migration
            result = conn.execute(text("""
                SELECT source_type, COUNT(*) as count
                FROM data_security_entity_types
                GROUP BY source_type
            """))
            counts = result.fetchall()  # fcg-rewrite
            
            logger.info("Verification - Entity type counts by source_type:")  # fcg-rewrite
            for source_type, count in counts:  # fcg-rewrite
                logger.info(f"  {source_type}: {count}")  # fcg-rewrite
            
            logger.info("Migration 013 completed successfully!")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            conn.rollback()  # fcg-rewrite
            logger.error(f"Migration 013 failed: {e}")  # fcg-rewrite
            raise


def downgrade():  # fcg-rewrite
    """Rollback the migration"""
    with engine.connect() as conn:  # fcg-rewrite
        try:
            logger.info("Rolling back migration 013: Remove entity type template support")  # fcg-rewrite

            # Drop indexes
            logger.info("Dropping indexes...")  # fcg-rewrite
            conn.execute(text("""
                DROP INDEX IF EXISTS ix_data_security_entity_types_template_id
            """))
            conn.execute(text("""
                DROP INDEX IF EXISTS ix_data_security_entity_types_source_type
            """))
            
            # Drop columns
            logger.info("Dropping template_id column...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE data_security_entity_types
                DROP COLUMN IF EXISTS template_id
            """))
            
            logger.info("Dropping source_type column...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE data_security_entity_types
                DROP COLUMN IF EXISTS source_type
            """))
            
            conn.commit()  # fcg-rewrite
            logger.info("Rollback 013 completed successfully!")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            conn.rollback()  # fcg-rewrite
            logger.error(f"Rollback 013 failed: {e}")  # fcg-rewrite
            raise


if __name__ == "__main__":  # fcg-rewrite
    import sys  # fcg-rewrite

    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":  # fcg-rewrite
        downgrade()  # fcg-rewrite
    else:
        upgrade()  # fcg-rewrite

