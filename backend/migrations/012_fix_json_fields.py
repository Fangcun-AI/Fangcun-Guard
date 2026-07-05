#!/usr/bin/env python3
"""
Migration: Fix JSON fields in detection_results table
Date: 2025-10-29
Description: Convert string '[]' values to proper JSON arrays and update column types to jsonb
"""

import os  # fcg-rewrite
import sys  # fcg-rewrite
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # fcg-rewrite

from database.connection import get_db_session  # fcg-rewrite
from sqlalchemy import text  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

def run_migration():  # fcg-rewrite
    """Run the migration to fix JSON fields"""
    db = get_db_session()  # fcg-rewrite
    
    try:
        logger.info("Starting migration: Fix JSON fields in detection_results table")  # fcg-rewrite
        
        # Check current state
        total_count = db.execute(text('SELECT COUNT(*) FROM detection_results')).scalar()  # fcg-rewrite
        logger.info(f"Total detection_results records: {total_count}")  # fcg-rewrite
        
        # Fix data_categories field
        data_string_count = db.execute(text("SELECT COUNT(*) FROM detection_results WHERE data_categories::text = '[]'")).scalar()  # fcg-rewrite
        data_null_count = db.execute(text('SELECT COUNT(*) FROM detection_results WHERE data_categories IS NULL')).scalar()  # fcg-rewrite
        
        if data_string_count > 0:  # fcg-rewrite
            result = db.execute(text("UPDATE detection_results SET data_categories = '[]'::jsonb WHERE data_categories::text = '[]'")).rowcount  # fcg-rewrite
            logger.info(f"Updated {result} records with string data_categories to proper JSON arrays")  # fcg-rewrite
        
        if data_null_count > 0:  # fcg-rewrite
            result = db.execute(text("UPDATE detection_results SET data_categories = '[]'::jsonb WHERE data_categories IS NULL")).rowcount  # fcg-rewrite
            logger.info(f"Updated {result} records with NULL data_categories to proper JSON arrays")  # fcg-rewrite
        
        # Fix security_categories field
        security_string_count = db.execute(text("SELECT COUNT(*) FROM detection_results WHERE security_categories::text = '[]'")).scalar()  # fcg-rewrite
        if security_string_count > 0:  # fcg-rewrite
            result = db.execute(text("UPDATE detection_results SET security_categories = '[]'::jsonb WHERE security_categories::text = '[]'")).rowcount  # fcg-rewrite
            logger.info(f"Updated {result} records with string security_categories to proper JSON arrays")  # fcg-rewrite
        
        # Fix compliance_categories field
        compliance_string_count = db.execute(text("SELECT COUNT(*) FROM detection_results WHERE compliance_categories::text = '[]'")).scalar()  # fcg-rewrite
        if compliance_string_count > 0:  # fcg-rewrite
            result = db.execute(text("UPDATE detection_results SET compliance_categories = '[]'::jsonb WHERE compliance_categories::text = '[]'")).rowcount  # fcg-rewrite
            logger.info(f"Updated {result} records with string compliance_categories to proper JSON arrays")  # fcg-rewrite
        
        # Fix image_paths field
        image_string_count = db.execute(text("SELECT COUNT(*) FROM detection_results WHERE image_paths::text = '[]'")).scalar()  # fcg-rewrite
        if image_string_count > 0:  # fcg-rewrite
            result = db.execute(text("UPDATE detection_results SET image_paths = '[]'::jsonb WHERE image_paths::text = '[]'")).rowcount  # fcg-rewrite
            logger.info(f"Updated {result} records with string image_paths to proper JSON arrays")  # fcg-rewrite
        
        # Fix NULL risk level fields
        data_risk_null = db.execute(text('SELECT COUNT(*) FROM detection_results WHERE data_risk_level IS NULL')).scalar()  # fcg-rewrite
        if data_risk_null > 0:  # fcg-rewrite
            result = db.execute(text("UPDATE detection_results SET data_risk_level = 'no_risk' WHERE data_risk_level IS NULL")).rowcount  # fcg-rewrite
            logger.info(f"Updated {result} records with NULL data_risk_level to 'no_risk'")  # fcg-rewrite
        
        # Convert column types to jsonb
        logger.info("Converting column types to jsonb...")  # fcg-rewrite
        db.execute(text('ALTER TABLE detection_results ALTER COLUMN data_categories TYPE jsonb USING data_categories::jsonb'))  # fcg-rewrite
        db.execute(text('ALTER TABLE detection_results ALTER COLUMN security_categories TYPE jsonb USING security_categories::jsonb'))  # fcg-rewrite
        db.execute(text('ALTER TABLE detection_results ALTER COLUMN compliance_categories TYPE jsonb USING compliance_categories::jsonb'))  # fcg-rewrite
        db.execute(text('ALTER TABLE detection_results ALTER COLUMN image_paths TYPE jsonb USING image_paths::jsonb'))  # fcg-rewrite
        
        # Commit all changes
        db.commit()  # fcg-rewrite
        logger.info("All changes committed successfully")  # fcg-rewrite
        
        # Verify the fixes
        data_json_count = db.execute(text("SELECT COUNT(*) FROM detection_results WHERE jsonb_typeof(data_categories::jsonb) = 'array'")).scalar()  # fcg-rewrite
        security_json_count = db.execute(text("SELECT COUNT(*) FROM detection_results WHERE jsonb_typeof(security_categories::jsonb) = 'array'")).scalar()  # fcg-rewrite
        compliance_json_count = db.execute(text("SELECT COUNT(*) FROM detection_results WHERE jsonb_typeof(compliance_categories::jsonb) = 'array'")).scalar()  # fcg-rewrite
        image_json_count = db.execute(text("SELECT COUNT(*) FROM detection_results WHERE jsonb_typeof(image_paths::jsonb) = 'array'")).scalar()  # fcg-rewrite
        
        logger.info(f"Verification results:")  # fcg-rewrite
        logger.info(f"  - Records with proper JSON array data_categories: {data_json_count}")  # fcg-rewrite
        logger.info(f"  - Records with proper JSON array security_categories: {security_json_count}")  # fcg-rewrite
        logger.info(f"  - Records with proper JSON array compliance_categories: {compliance_json_count}")  # fcg-rewrite
        logger.info(f"  - Records with proper JSON array image_paths: {image_json_count}")  # fcg-rewrite
        
        if data_json_count == total_count and security_json_count == total_count and compliance_json_count == total_count and image_json_count == total_count:  # fcg-rewrite
            logger.info("✅ Migration completed successfully - all JSON fields are now proper arrays")  # fcg-rewrite
            return True  # fcg-rewrite
        else:
            logger.error("❌ Migration failed - some records still have incorrect JSON field types")  # fcg-rewrite
            return False  # fcg-rewrite
            
    except Exception as e:  # fcg-rewrite
        logger.error(f"Migration failed with error: {e}")  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        return False  # fcg-rewrite
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    success = run_migration()  # fcg-rewrite
    sys.exit(0 if success else 1)  # fcg-rewrite
