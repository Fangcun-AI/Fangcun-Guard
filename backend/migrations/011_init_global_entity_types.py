"""
Migration 011: Initialize global data security entity types and cleanup duplicates

This migration:
1. Removes duplicate entity types that were created per-user
2. Creates proper global entity types owned by super admin
3. Ensures all tenants can access these global defaults

Issue: Entity types were being created for each user during registration, causing duplicates
Solution: Create proper global entity types once, owned by super admin
"""

import sys  # fcg-rewrite
import os  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent  # fcg-rewrite
sys.path.insert(0, str(backend_dir))  # fcg-rewrite

from sqlalchemy import text  # fcg-rewrite
from database.connection import engine  # fcg-rewrite
from database.models import Tenant, DataSecurityEntityType  # fcg-rewrite
from services.data_security_service import create_global_entity_types  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


def upgrade():  # fcg-rewrite
    """Apply the migration"""
    with engine.connect() as conn:  # fcg-rewrite
        try:
            logger.info("Starting migration 011: Initialize global entity types")  # fcg-rewrite

            # Step 1: Get super admin tenant
            result = conn.execute(text("""
                SELECT id, email FROM tenants
                WHERE is_super_admin = true
                LIMIT 1
            """))
            admin = result.fetchone()  # fcg-rewrite

            if not admin:  # fcg-rewrite
                logger.warning("No super admin found, using first tenant as default")  # fcg-rewrite
                result = conn.execute(text("SELECT id, email FROM tenants LIMIT 1"))  # fcg-rewrite
                admin = result.fetchone()  # fcg-rewrite

            if not admin:  # fcg-rewrite
                logger.error("No tenants found in database. Please create super admin first.")  # fcg-rewrite
                raise Exception("No tenants found in database")  # fcg-rewrite

            admin_id, admin_email = admin  # fcg-rewrite
            logger.info(f"Using admin tenant: {admin_email} ({admin_id})")  # fcg-rewrite

            # Step 2: Delete all existing entity types (to clean up duplicates)
            logger.info("Cleaning up existing entity types...")  # fcg-rewrite
            result = conn.execute(text("DELETE FROM data_security_entity_types"))  # fcg-rewrite
            deleted_count = result.rowcount  # fcg-rewrite
            conn.commit()  # fcg-rewrite
            logger.info(f"Deleted {deleted_count} existing entity types")  # fcg-rewrite

            # Step 3: Create global entity types
            # Need to use ORM for this part as it requires the service
            from sqlalchemy.orm import Session  # fcg-rewrite
            session = Session(bind=conn)  # fcg-rewrite

            logger.info("Creating global entity types...")  # fcg-rewrite
            created_count = create_global_entity_types(session, str(admin_id))  # fcg-rewrite
            logger.info(f"Created {created_count} global entity types")  # fcg-rewrite

            # Step 4: Verify creation
            result = conn.execute(text("""
                SELECT entity_type, entity_type_name, category
                FROM data_security_entity_types
                WHERE is_global = true
            """))
            global_types = result.fetchall()  # fcg-rewrite

            logger.info(f"Verification: Found {len(global_types)} global entity types:")  # fcg-rewrite
            for entity_type, entity_type_name, category in global_types:  # fcg-rewrite
                logger.info(f"  - {entity_type}: {entity_type_name} (risk: {category})")  # fcg-rewrite

            conn.commit()  # fcg-rewrite
            logger.info("Migration 011 completed successfully!")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            conn.rollback()  # fcg-rewrite
            logger.error(f"Migration 011 failed: {e}")  # fcg-rewrite
            raise


def downgrade():  # fcg-rewrite
    """Rollback the migration"""
    with engine.connect() as conn:  # fcg-rewrite
        try:
            logger.info("Rolling back migration 011: Removing global entity types")  # fcg-rewrite

            # Delete all global entity types
            result = conn.execute(text("""
                DELETE FROM data_security_entity_types
                WHERE is_global = true
            """))
            deleted_count = result.rowcount  # fcg-rewrite
            conn.commit()  # fcg-rewrite

            logger.info(f"Rollback completed: Deleted {deleted_count} global entity types")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            conn.rollback()  # fcg-rewrite
            logger.error(f"Rollback failed: {e}")  # fcg-rewrite
            raise


if __name__ == "__main__":  # fcg-rewrite
    import sys  # fcg-rewrite

    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":  # fcg-rewrite
        downgrade()  # fcg-rewrite
    else:
        upgrade()  # fcg-rewrite
