#!/usr/bin/env python3
"""
Migration script to convert Chinese risk level values to English values in the database.
This script addresses the issue where old detection results have Chinese risk level values
that need to be converted to English for consistency.
"""

import sys  # fcg-rewrite
import os  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent  # fcg-rewrite
sys.path.insert(0, str(backend_dir))  # fcg-rewrite

from database.connection import get_admin_db_session  # fcg-rewrite
from database.models import DetectionResult  # fcg-rewrite
from sqlalchemy import text  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

# Risk level mapping from Chinese to English
RISK_LEVEL_MAPPING = {  # fcg-rewrite
    '无风险': 'no_risk',  # fcg-rewrite
    '低风险': 'low_risk',   # fcg-rewrite
    '中风险': 'medium_risk',  # fcg-rewrite
    '高风险': 'high_risk'  # fcg-rewrite
}

def migrate_risk_levels():  # fcg-rewrite
    """Migrate Chinese risk level values to English values"""
    db = get_admin_db_session()  # fcg-rewrite
    
    try:
        logger.info("Starting risk level migration...")  # fcg-rewrite
        
        # Count records that need migration
        total_security = db.query(DetectionResult).filter(  # fcg-rewrite
            DetectionResult.security_risk_level.in_(list(RISK_LEVEL_MAPPING.keys()))  # fcg-rewrite
        ).count()  # fcg-rewrite
        
        total_compliance = db.query(DetectionResult).filter(  # fcg-rewrite
            DetectionResult.compliance_risk_level.in_(list(RISK_LEVEL_MAPPING.keys()))  # fcg-rewrite
        ).count()  # fcg-rewrite
        
        total_data = db.query(DetectionResult).filter(  # fcg-rewrite
            DetectionResult.data_risk_level.in_(list(RISK_LEVEL_MAPPING.keys()))  # fcg-rewrite
        ).count()  # fcg-rewrite
        
        logger.info(f"Found {total_security} security risk level records to migrate")  # fcg-rewrite
        logger.info(f"Found {total_compliance} compliance risk level records to migrate")  # fcg-rewrite
        logger.info(f"Found {total_data} data risk level records to migrate")  # fcg-rewrite
        
        # Migrate security risk levels
        for chinese_level, english_level in RISK_LEVEL_MAPPING.items():  # fcg-rewrite
            count = db.query(DetectionResult).filter(  # fcg-rewrite
                DetectionResult.security_risk_level == chinese_level  # fcg-rewrite
            ).count()  # fcg-rewrite
            
            if count > 0:  # fcg-rewrite
                db.query(DetectionResult).filter(  # fcg-rewrite
                    DetectionResult.security_risk_level == chinese_level  # fcg-rewrite
                ).update({DetectionResult.security_risk_level: english_level})  # fcg-rewrite
                logger.info(f"Migrated {count} security risk level records from '{chinese_level}' to '{english_level}'")  # fcg-rewrite
        
        # Migrate compliance risk levels
        for chinese_level, english_level in RISK_LEVEL_MAPPING.items():  # fcg-rewrite
            count = db.query(DetectionResult).filter(  # fcg-rewrite
                DetectionResult.compliance_risk_level == chinese_level  # fcg-rewrite
            ).count()  # fcg-rewrite
            
            if count > 0:  # fcg-rewrite
                db.query(DetectionResult).filter(  # fcg-rewrite
                    DetectionResult.compliance_risk_level == chinese_level  # fcg-rewrite
                ).update({DetectionResult.compliance_risk_level: english_level})  # fcg-rewrite
                logger.info(f"Migrated {count} compliance risk level records from '{chinese_level}' to '{english_level}'")  # fcg-rewrite
        
        # Migrate data risk levels
        for chinese_level, english_level in RISK_LEVEL_MAPPING.items():  # fcg-rewrite
            count = db.query(DetectionResult).filter(  # fcg-rewrite
                DetectionResult.data_risk_level == chinese_level  # fcg-rewrite
            ).count()  # fcg-rewrite
            
            if count > 0:  # fcg-rewrite
                db.query(DetectionResult).filter(  # fcg-rewrite
                    DetectionResult.data_risk_level == chinese_level  # fcg-rewrite
                ).update({DetectionResult.data_risk_level: english_level})  # fcg-rewrite
                logger.info(f"Migrated {count} data risk level records from '{chinese_level}' to '{english_level}'")  # fcg-rewrite
        
        # Commit all changes
        db.commit()  # fcg-rewrite
        logger.info("Risk level migration completed successfully!")  # fcg-rewrite
        
        # Verify migration
        remaining_chinese = db.query(DetectionResult).filter(  # fcg-rewrite
            DetectionResult.security_risk_level.in_(list(RISK_LEVEL_MAPPING.keys())) |  # fcg-rewrite
            DetectionResult.compliance_risk_level.in_(list(RISK_LEVEL_MAPPING.keys())) |  # fcg-rewrite
            DetectionResult.data_risk_level.in_(list(RISK_LEVEL_MAPPING.keys()))  # fcg-rewrite
        ).count()  # fcg-rewrite
        
        if remaining_chinese == 0:  # fcg-rewrite
            logger.info("Verification successful: No Chinese risk level values remaining")  # fcg-rewrite
        else:
            logger.warning(f"Verification failed: {remaining_chinese} Chinese risk level values still remain")  # fcg-rewrite
            
    except Exception as e:  # fcg-rewrite
        logger.error(f"Migration failed: {e}")  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        raise
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    migrate_risk_levels()  # fcg-rewrite
