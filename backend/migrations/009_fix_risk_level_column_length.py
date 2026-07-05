"""
Migration 009: Fix risk level column length in detection_results table

Issue: VARCHAR(10) is too short for 'medium_risk' (11 characters)
Solution: Increase VARCHAR from 10 to 20 for all risk_level columns
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
    """
    Increase VARCHAR length for risk level columns from 10 to 20
    """
    with engine.connect() as conn:  # fcg-rewrite
        try:
            logger.info("Starting migration 009: Fix risk level column length")  # fcg-rewrite

            # Alter security_risk_level column
            logger.info("Altering detection_results.security_risk_level to VARCHAR(20)...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE detection_results
                ALTER COLUMN security_risk_level TYPE VARCHAR(20)
            """))

            # Alter compliance_risk_level column
            logger.info("Altering detection_results.compliance_risk_level to VARCHAR(20)...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE detection_results
                ALTER COLUMN compliance_risk_level TYPE VARCHAR(20)
            """))

            # Alter data_risk_level column
            logger.info("Altering detection_results.data_risk_level to VARCHAR(20)...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE detection_results
                ALTER COLUMN data_risk_level TYPE VARCHAR(20)
            """))

            # Also fix risk_level in response_templates table
            logger.info("Altering response_templates.risk_level to VARCHAR(20)...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE response_templates
                ALTER COLUMN risk_level TYPE VARCHAR(20)
            """))

            # Also fix sensitivity_trigger_level in risk_type_config table
            logger.info("Altering risk_type_config.sensitivity_trigger_level to VARCHAR(20)...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE risk_type_config
                ALTER COLUMN sensitivity_trigger_level TYPE VARCHAR(20)
            """))

            conn.commit()  # fcg-rewrite
            logger.info("Migration 009 completed successfully!")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            conn.rollback()  # fcg-rewrite
            logger.error(f"Migration 009 failed: {e}")  # fcg-rewrite
            raise

def downgrade():  # fcg-rewrite
    """
    Revert VARCHAR length back to 10 (not recommended, will cause data truncation)
    """
    with engine.connect() as conn:  # fcg-rewrite
        try:
            logger.info("Starting downgrade of migration 009")  # fcg-rewrite
            logger.warning("Downgrading column lengths may truncate data!")  # fcg-rewrite

            # Revert detection_results columns
            logger.info("Reverting detection_results columns to VARCHAR(10)...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE detection_results
                ALTER COLUMN security_risk_level TYPE VARCHAR(10)
            """))

            conn.execute(text("""
                ALTER TABLE detection_results
                ALTER COLUMN compliance_risk_level TYPE VARCHAR(10)
            """))

            conn.execute(text("""
                ALTER TABLE detection_results
                ALTER COLUMN data_risk_level TYPE VARCHAR(10)
            """))

            # Revert response_templates
            logger.info("Reverting response_templates.risk_level to VARCHAR(10)...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE response_templates
                ALTER COLUMN risk_level TYPE VARCHAR(10)
            """))

            # Revert risk_type_config
            logger.info("Reverting risk_type_config.sensitivity_trigger_level to VARCHAR(10)...")  # fcg-rewrite
            conn.execute(text("""
                ALTER TABLE risk_type_config
                ALTER COLUMN sensitivity_trigger_level TYPE VARCHAR(10)
            """))

            conn.commit()  # fcg-rewrite
            logger.info("Migration 009 downgrade completed successfully!")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            conn.rollback()  # fcg-rewrite
            logger.error(f"Migration 009 downgrade failed: {e}")  # fcg-rewrite
            raise

if __name__ == "__main__":  # fcg-rewrite
    import sys  # fcg-rewrite

    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":  # fcg-rewrite
        downgrade()  # fcg-rewrite
    else:
        upgrade()  # fcg-rewrite
