#!/usr/bin/env python3
"""
Clean Duplicate Response Templates - Data Cleanup Script
This script removes duplicate response templates, keeping only the latest version.

Cleanup logic:
1. Group by tenant_id, application_id, and scanner_identifier (or category for old records)
2. Keep the record with the highest ID (most recent)
3. Delete older duplicates
4. Update statistics
"""

import sys  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

# Add backend to path
backend_dir = Path(__file__).parent.parent  # fcg-rewrite
sys.path.insert(0, str(backend_dir))  # fcg-rewrite

from sqlalchemy import create_engine, text  # fcg-rewrite
from sqlalchemy.orm import sessionmaker  # fcg-rewrite
from config import settings  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

def get_duplicate_groups(db):  # fcg-rewrite
    """Get groups of duplicate response templates"""
    query = text("""
    SELECT
        tenant_id,
        application_id,
        COALESCE(scanner_identifier, category) as scanner_key,
        scanner_name,
        COUNT(*) as duplicate_count,
        ARRAY_AGG(id ORDER BY created_at DESC, updated_at DESC) as ids,
        STRING_AGG(CAST(id AS TEXT), ', ' ORDER BY created_at DESC, updated_at DESC) as id_list
    FROM response_templates
    WHERE scanner_name IS NOT NULL
    GROUP BY tenant_id, application_id, COALESCE(scanner_identifier, category), scanner_name
    HAVING COUNT(*) > 1
    ORDER BY tenant_id, duplicate_count DESC
    """)

    result = db.execute(query)  # fcg-rewrite
    return result.fetchall()  # fcg-rewrite

def clean_duplicates(db, dry_run=True):  # fcg-rewrite
    """Clean duplicate response templates"""
    logger.info("=== " + ("DRY RUN - " if dry_run else "") + "CLEANING DUPLICATE RESPONSE TEMPLATES ===")  # fcg-rewrite

    duplicate_groups = get_duplicate_groups(db)  # fcg-rewrite

    if not duplicate_groups:  # fcg-rewrite
        logger.info("✅ No duplicate response templates found")  # fcg-rewrite
        return 0, 0  # fcg-rewrite

    total_duplicates = len(duplicate_groups)  # fcg-rewrite
    total_to_delete = 0  # fcg-rewrite

    logger.info(f"Found {total_duplicates} duplicate groups")  # fcg-rewrite

    for group in duplicate_groups:  # fcg-rewrite
        tenant_id = group.tenant_id  # fcg-rewrite
        application_id = group.application_id  # fcg-rewrite
        scanner_key = group.scanner_key  # fcg-rewrite
        scanner_name = group.scanner_name  # fcg-rewrite
        duplicate_count = group.duplicate_count  # fcg-rewrite
        ids = group.ids  # Already ordered by created_at DESC, updated_at DESC  # fcg-rewrite

        # Keep the first (latest) ID, delete the rest
        keep_id = ids[0]  # fcg-rewrite
        delete_ids = ids[1:]  # fcg-rewrite
        total_to_delete += len(delete_ids)  # fcg-rewrite

        logger.info(f"\n🔍 Duplicate Group:")  # fcg-rewrite
        logger.info(f"   Tenant: {tenant_id}")  # fcg-rewrite
        logger.info(f"   Application: {application_id}")  # fcg-rewrite
        logger.info(f"   Scanner: {scanner_name} ({scanner_key})")  # fcg-rewrite
        logger.info(f"   Count: {duplicate_count}")  # fcg-rewrite
        logger.info(f"   Keep: {keep_id} (latest)")  # fcg-rewrite
        logger.info(f"   Delete: {delete_ids}")  # fcg-rewrite

        if not dry_run:  # fcg-rewrite
            # Delete duplicates
            delete_query = text("""
                DELETE FROM response_templates
                WHERE id = ANY(:delete_ids)
            """)

            try:
                db.execute(delete_query, {"delete_ids": delete_ids})  # fcg-rewrite
                db.flush()  # fcg-rewrite
                logger.info(f"   ✅ Deleted {len(delete_ids)} duplicate records")  # fcg-rewrite
            except Exception as e:  # fcg-rewrite
                logger.error(f"   ❌ Error deleting duplicates: {e}")  # fcg-rewrite
                db.rollback()  # fcg-rewrite
                return total_duplicates, total_to_delete  # fcg-rewrite

    if not dry_run:  # fcg-rewrite
        db.commit()  # fcg-rewrite
        logger.info(f"\n✅ Successfully deleted {total_to_delete} duplicate response templates")  # fcg-rewrite
    else:
        logger.info(f"\n🔍 DRY RUN: Would delete {total_to_delete} duplicate response templates")  # fcg-rewrite
        logger.info("   Run without --dry-run to actually delete duplicates")  # fcg-rewrite

    return total_duplicates, total_to_delete  # fcg-rewrite

def get_statistics(db):  # fcg-rewrite
    """Get response template statistics before and after cleanup"""
    query = text("""
    SELECT
        COUNT(*) as total_templates,
        COUNT(DISTINCT tenant_id) as unique_tenants,
        COUNT(DISTINCT application_id) as unique_applications,
        COUNT(DISTINCT COALESCE(scanner_identifier, category)) as unique_scanners
    FROM response_templates
    """)

    result = db.execute(query).fetchone()  # fcg-rewrite
    return {  # fcg-rewrite
        'total_templates': result.total_templates,  # fcg-rewrite
        'unique_tenants': result.unique_tenants,  # fcg-rewrite
        'unique_applications': result.unique_applications,  # fcg-rewrite
        'unique_scanners': result.unique_scanners  # fcg-rewrite
    }

def main():  # fcg-rewrite
    import argparse  # fcg-rewrite

    parser = argparse.ArgumentParser(description='Clean duplicate response templates')  # fcg-rewrite
    parser.add_argument('--dry-run', action='store_true',  # fcg-rewrite
                       help='Show what would be deleted without actually deleting')  # fcg-rewrite
    parser.add_argument('--force', action='store_true',  # fcg-rewrite
                       help='Skip confirmation prompt')  # fcg-rewrite

    args = parser.parse_args()  # fcg-rewrite

    # Default to dry run for safety
    dry_run = not args.force  # fcg-rewrite

    print("=" * 80)  # fcg-rewrite
    print("CLEAN DUPLICATE RESPONSE TEMPLATES")  # fcg-rewrite
    print("=" * 80)  # fcg-rewrite

    # Create database connection
    engine = create_engine(settings.database_url)  # fcg-rewrite
    SessionLocal = sessionmaker(bind=engine)  # fcg-rewrite
    db = SessionLocal()  # fcg-rewrite

    try:
        # Show statistics before
        stats_before = get_statistics(db)  # fcg-rewrite
        print(f"\n📊 Statistics Before Cleanup:")  # fcg-rewrite
        print(f"   Total Templates: {stats_before['total_templates']}")  # fcg-rewrite
        print(f"   Unique Tenants: {stats_before['unique_tenants']}")  # fcg-rewrite
        print(f"   Unique Applications: {stats_before['unique_applications']}")  # fcg-rewrite
        print(f"   Unique Scanners: {stats_before['unique_scanners']}")  # fcg-rewrite

        # Clean duplicates
        total_groups, total_to_delete = clean_duplicates(db, dry_run=dry_run)  # fcg-rewrite

        if total_groups == 0:  # fcg-rewrite
            print("\n✅ No duplicates found - nothing to do!")  # fcg-rewrite
            return

        if not dry_run:  # fcg-rewrite
            # Show statistics after
            stats_after = get_statistics(db)  # fcg-rewrite
            print(f"\n📊 Statistics After Cleanup:")  # fcg-rewrite
            print(f"   Total Templates: {stats_after['total_templates']} (-{total_to_delete})")  # fcg-rewrite
            print(f"   Unique Tenants: {stats_after['unique_tenants']}")  # fcg-rewrite
            print(f"   Unique Applications: {stats_after['unique_applications']}")  # fcg-rewrite
            print(f"   Unique Scanners: {stats_after['unique_scanners']}")  # fcg-rewrite
        else:
            print(f"\n🔍 DRY RUN SUMMARY:")  # fcg-rewrite
            print(f"   Duplicate Groups: {total_groups}")  # fcg-rewrite
            print(f"   Records to Delete: {total_to_delete}")  # fcg-rewrite
            print(f"\n⚠️  To actually delete duplicates, run with --force")  # fcg-rewrite

    except Exception as e:  # fcg-rewrite
        logger.error(f"❌ Error during cleanup: {e}")  # fcg-rewrite
        import traceback  # fcg-rewrite
        traceback.print_exc()  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        return 1  # fcg-rewrite

    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite

    return 0  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    sys.exit(main())  # fcg-rewrite