"""
Migration: Migrate from hardcoded risk types to scanner package system
Version: 017
Date: 2025-11-05

This migration:
1. Loads built-in scanner packages from JSON files
2. Migrates existing risk_type_config data to application_scanner_configs
3. Preserves user enable/disable settings
"""

import json  # fcg-rewrite
import os  # fcg-rewrite
import sys  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

# Add backend to path
backend_dir = Path(__file__).parent.parent  # fcg-rewrite
sys.path.insert(0, str(backend_dir))  # fcg-rewrite

from sqlalchemy import create_engine, text, func  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite
from database.connection import get_database_url  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

# Setup logger
logger = setup_logger()  # fcg-rewrite


# Risk level mapping from old system
RISK_LEVEL_MAP = {  # fcg-rewrite
    'S1': 'low_risk',  # fcg-rewrite
    'S2': 'high_risk',  # fcg-rewrite
    'S3': 'high_risk',  # fcg-rewrite
    'S4': 'medium_risk',  # fcg-rewrite
    'S5': 'high_risk',  # fcg-rewrite
    'S6': 'medium_risk',  # fcg-rewrite
    'S7': 'medium_risk',  # fcg-rewrite
    'S8': 'low_risk',  # fcg-rewrite
    'S9': 'high_risk',  # fcg-rewrite
    'S10': 'low_risk',  # fcg-rewrite
    'S11': 'low_risk',  # fcg-rewrite
    'S12': 'low_risk',  # fcg-rewrite
    'S13': 'low_risk',  # fcg-rewrite
    'S14': 'low_risk',  # fcg-rewrite
    'S15': 'high_risk',  # fcg-rewrite
    'S16': 'medium_risk',  # fcg-rewrite
    'S17': 'high_risk',  # fcg-rewrite
    'S18': 'low_risk',  # fcg-rewrite
    'S19': 'low_risk',  # fcg-rewrite
    'S20': 'low_risk',  # fcg-rewrite
    'S21': 'low_risk',  # fcg-rewrite
}


def load_builtin_packages(db: Session):  # fcg-rewrite
    """Load built-in packages from JSON files."""
    logger.info("Loading built-in scanner packages...")  # fcg-rewrite

    # Try multiple locations for built-in packages
    possible_dirs = [  # fcg-rewrite
        backend_dir / 'builtin_scanners',  # fcg-rewrite
        backend_dir.parent / 'docs' / 'scanner_packages_examples',  # Fallback to examples  # fcg-rewrite
    ]

    builtin_dir = None  # fcg-rewrite
    for dir_path in possible_dirs:  # fcg-rewrite
        if dir_path.exists():  # fcg-rewrite
            builtin_dir = dir_path  # fcg-rewrite
            logger.info(f"Using built-in packages from: {builtin_dir}")  # fcg-rewrite
            break

    if not builtin_dir:  # fcg-rewrite
        logger.error(f"Built-in scanners directory not found in any of: {possible_dirs}")  # fcg-rewrite
        raise FileNotFoundError("Built-in scanner packages not found")  # fcg-rewrite

    package_files = []  # fcg-rewrite

    loaded_packages = []  # fcg-rewrite

    for package_file in package_files:  # fcg-rewrite
        if not package_file.exists():  # fcg-rewrite
            logger.warning(f"Package file not found: {package_file}")  # fcg-rewrite
            continue  # fcg-rewrite

        try:
            with open(package_file, 'r', encoding='utf-8') as f:  # fcg-rewrite
                package_data = json.load(f)  # fcg-rewrite

            package_code = package_data['package_code']  # fcg-rewrite

            # Check if package already exists
            result = db.execute(  # fcg-rewrite
                text("SELECT id FROM scanner_packages WHERE package_code = :code"),  # fcg-rewrite
                {'code': package_code}  # fcg-rewrite
            )
            existing = result.fetchone()  # fcg-rewrite

            if existing:  # fcg-rewrite
                logger.info(f"Package '{package_code}' already exists, skipping...")  # fcg-rewrite
                continue  # fcg-rewrite

            # Insert package
            result = db.execute(  # fcg-rewrite
                text("""
                    INSERT INTO scanner_packages (
                        package_code, package_name, author, description,
                        version, license, package_type, is_official,
                        requires_purchase, is_active, scanner_count
                    ) VALUES (
                        :code, :name, :author, :description,
                        :version, :license, 'builtin', TRUE,
                        FALSE, TRUE, :count
                    )
                    RETURNING id
                """),
                {
                    'code': package_data['package_code'],  # fcg-rewrite
                    'name': package_data['package_name'],  # fcg-rewrite
                    'author': package_data.get('author', 'FangcunGuard'),  # fcg-rewrite
                    'description': package_data.get('description'),  # fcg-rewrite
                    'version': package_data.get('version', '1.0.0'),  # fcg-rewrite
                    'license': package_data.get('license', 'proprietary'),  # fcg-rewrite
                    'count': len(package_data['scanners'])  # fcg-rewrite
                }
            )
            package_id = result.fetchone()[0]  # fcg-rewrite

            # Insert scanners
            for i, scanner_data in enumerate(package_data['scanners']):  # fcg-rewrite
                db.execute(  # fcg-rewrite
                    text("""
                        INSERT INTO scanners (
                            package_id, tag, name, description,
                            scanner_type, definition,
                            default_risk_level, default_scan_prompt, default_scan_response,
                            is_active, display_order
                        ) VALUES (
                            :package_id, :tag, :name, :description,
                            :type, :definition,
                            :risk_level, :scan_prompt, :scan_response,
                            TRUE, :order
                        )
                    """),
                    {
                        'package_id': package_id,  # fcg-rewrite
                        'tag': scanner_data['tag'],  # fcg-rewrite
                        'name': scanner_data['name'],  # fcg-rewrite
                        'description': scanner_data.get('description', scanner_data['definition']),  # fcg-rewrite
                        'type': scanner_data['type'],  # fcg-rewrite
                        'definition': scanner_data['definition'],  # fcg-rewrite
                        'risk_level': scanner_data['risk_level'],  # fcg-rewrite
                        'scan_prompt': scanner_data.get('scan_prompt', True),  # fcg-rewrite
                        'scan_response': scanner_data.get('scan_response', True),  # fcg-rewrite
                        'order': i  # fcg-rewrite
                    }
                )

            loaded_packages.append(package_data['package_name'])  # fcg-rewrite
            logger.info(f"✓ Created package: {package_data['package_name']} ({len(package_data['scanners'])} scanners)")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            logger.error(f"Failed to load package {package_file}: {e}")  # fcg-rewrite
            raise

    db.commit()  # fcg-rewrite
    logger.info(f"Successfully loaded {len(loaded_packages)} built-in packages")  # fcg-rewrite


def migrate_risk_type_configs(db: Session):  # fcg-rewrite
    """Migrate existing risk_type_config to application_scanner_configs."""
    logger.info("Migrating existing risk type configurations...")  # fcg-rewrite

    # Get all risk type configs
    result = db.execute(text("SELECT id, application_id, tenant_id FROM risk_type_config"))  # fcg-rewrite
    risk_configs = result.fetchall()  # fcg-rewrite

    if not risk_configs:  # fcg-rewrite
        logger.info("No existing risk type configs to migrate")  # fcg-rewrite
        return

    # Get scanner ID mapping
    result = db.execute(text("SELECT tag, id FROM scanners WHERE tag LIKE 'S%' ORDER BY tag"))  # fcg-rewrite
    scanner_map = {row[0]: row[1] for row in result.fetchall()}  # fcg-rewrite

    migrated_count = 0  # fcg-rewrite
    skipped_count = 0  # fcg-rewrite

    for config in risk_configs:  # fcg-rewrite
        config_id = config[0]  # fcg-rewrite
        application_id = config[1]  # fcg-rewrite
        tenant_id = config[2]  # fcg-rewrite

        # Check if already migrated
        result = db.execute(  # fcg-rewrite
            text("SELECT COUNT(*) FROM application_scanner_configs WHERE application_id = :app_id"),  # fcg-rewrite
            {'app_id': application_id}  # fcg-rewrite
        )
        existing_count = result.fetchone()[0]  # fcg-rewrite

        if existing_count > 0:  # fcg-rewrite
            logger.debug(f"Application {application_id} already migrated, skipping...")  # fcg-rewrite
            skipped_count += 1  # fcg-rewrite
            continue  # fcg-rewrite

        # Get the enabled states for S1-S21
        result = db.execute(  # fcg-rewrite
            text("SELECT * FROM risk_type_config WHERE id = :id"),  # fcg-rewrite
            {'id': config_id}  # fcg-rewrite
        )
        config_row = result.fetchone()  # fcg-rewrite

        if not config_row:  # fcg-rewrite
            continue  # fcg-rewrite

        # Create column name to value mapping
        column_names = result.keys()  # fcg-rewrite
        config_dict = dict(zip(column_names, config_row))  # fcg-rewrite

        # Migrate S1-S21 enabled states
        for i in range(1, 22):  # fcg-rewrite
            tag = f'S{i}'  # fcg-rewrite
            enabled_field = f's{i}_enabled'  # fcg-rewrite

            # Get enabled state (default True if field doesn't exist)
            is_enabled = config_dict.get(enabled_field, True)  # fcg-rewrite

            # Get scanner ID
            scanner_id = scanner_map.get(tag)  # fcg-rewrite
            if not scanner_id:  # fcg-rewrite
                logger.warning(f"Scanner {tag} not found, skipping...")  # fcg-rewrite
                continue  # fcg-rewrite

            # Insert application_scanner_config
            db.execute(  # fcg-rewrite
                text("""
                    INSERT INTO application_scanner_configs (
                        application_id, scanner_id, is_enabled,
                        risk_level_override, scan_prompt_override, scan_response_override
                    ) VALUES (
                        :app_id, :scanner_id, :enabled,
                        NULL, NULL, NULL
                    )
                    ON CONFLICT (application_id, scanner_id) DO NOTHING
                """),
                {
                    'app_id': application_id,  # fcg-rewrite
                    'scanner_id': scanner_id,  # fcg-rewrite
                    'enabled': is_enabled  # fcg-rewrite
                }
            )

        migrated_count += 1  # fcg-rewrite

        if migrated_count % 10 == 0:  # fcg-rewrite
            logger.info(f"Migrated {migrated_count}/{len(risk_configs)} applications...")  # fcg-rewrite

    db.commit()  # fcg-rewrite
    logger.info(f"Migration complete: {migrated_count} applications migrated, {skipped_count} skipped")  # fcg-rewrite


def run_migration():  # fcg-rewrite
    """Main migration function."""
    logger.info("=" * 60)  # fcg-rewrite
    logger.info("Scanner Package System Migration - Python Script")  # fcg-rewrite
    logger.info("=" * 60)  # fcg-rewrite

    database_url = get_database_url()  # fcg-rewrite
    engine = create_engine(database_url)  # fcg-rewrite
    db = Session(engine)  # fcg-rewrite

    try:
        logger.info("\nStep 1: Loading built-in packages...")  # fcg-rewrite
        load_builtin_packages(db)  # fcg-rewrite

        logger.info("\nStep 2: Migrating existing risk type configurations...")  # fcg-rewrite
        migrate_risk_type_configs(db)  # fcg-rewrite

        logger.info("\n" + "=" * 60)  # fcg-rewrite
        logger.info("✓ Migration completed successfully!")  # fcg-rewrite
        logger.info("=" * 60)  # fcg-rewrite

    except Exception as e:  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        logger.error(f"\n❌ Migration failed: {e}")  # fcg-rewrite
        import traceback  # fcg-rewrite
        traceback.print_exc()  # fcg-rewrite
        raise
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite


if __name__ == '__main__':  # fcg-rewrite
    run_migration()  # fcg-rewrite
