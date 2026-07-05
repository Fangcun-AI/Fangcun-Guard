#!/usr/bin/env python3
"""
Sync Response Templates - Data Migration Script
This script creates response templates for existing scanners and blacklists.

Use this script when:
1. After implementing the automatic response template creation feature
2. To create templates for scanners and blacklists that existed before this feature
3. As part of database maintenance to ensure all scanners have templates

This is a safe operation that only creates missing templates (no duplicates).

The script will:
- Create templates for all official scanners (S1-S21) in each application
- Create templates for all custom scanners (S100+) in their respective applications
- Create templates for all purchased marketplace scanners in each application
- Create templates for all blacklists in their respective applications
"""

import sys  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent  # fcg-rewrite
sys.path.insert(0, str(backend_dir))  # fcg-rewrite

from sqlalchemy import create_engine  # fcg-rewrite
from sqlalchemy.orm import sessionmaker  # fcg-rewrite
from config import settings  # fcg-rewrite
from database.models import (  # fcg-rewrite
    Application, Scanner, ScannerPackage, CustomScanner,   # fcg-rewrite
    Blacklist, PackagePurchase, ResponseTemplate  # fcg-rewrite
)
from services.response_template_service import ResponseTemplateService  # fcg-rewrite


def sync_official_scanner_templates(db):  # fcg-rewrite
    """Create templates for official scanners (S1-S21)"""
    print("\n=== Syncing Official Scanner Templates ===")  # fcg-rewrite
    
    # Get the built-in scanner package
    builtin_package = db.query(ScannerPackage).filter(  # fcg-rewrite
        ScannerPackage.package_code == 'builtin',  # fcg-rewrite
        ScannerPackage.is_active == True  # fcg-rewrite
    ).first()  # fcg-rewrite
    
    if not builtin_package:  # fcg-rewrite
        print("⚠ No built-in scanner package found")  # fcg-rewrite
        return 0  # fcg-rewrite
    
    # Get all official scanners (S1-S21)
    official_scanners = db.query(Scanner).filter(  # fcg-rewrite
        Scanner.package_id == builtin_package.id,  # fcg-rewrite
        Scanner.is_active == True  # fcg-rewrite
    ).all()
    
    if not official_scanners:  # fcg-rewrite
        print("⚠ No official scanners found")  # fcg-rewrite
        return 0  # fcg-rewrite
    
    print(f"Found {len(official_scanners)} official scanner(s)")  # fcg-rewrite
    
    # Get all active applications
    applications = db.query(Application).filter(  # fcg-rewrite
        Application.is_active == True  # fcg-rewrite
    ).all()
    
    print(f"Found {len(applications)} active application(s)")  # fcg-rewrite
    
    template_service = ResponseTemplateService(db)  # fcg-rewrite
    created_count = 0  # fcg-rewrite
    
    for app in applications:  # fcg-rewrite
        print(f"\n  Processing application: {app.name} (ID: {app.id})")  # fcg-rewrite
        
        for scanner in official_scanners:  # fcg-rewrite
            try:
                template = template_service.create_template_for_official_scanner(  # fcg-rewrite
                    scanner=scanner,  # fcg-rewrite
                    application_id=app.id,  # fcg-rewrite
                    tenant_id=app.tenant_id  # fcg-rewrite
                )
                
                if template:  # fcg-rewrite
                    created_count += 1  # fcg-rewrite
                    print(f"    ✓ Created template for {scanner.tag} ({scanner.name})")  # fcg-rewrite
                else:
                    print(f"    - Template for {scanner.tag} already exists")  # fcg-rewrite
            
            except Exception as e:  # fcg-rewrite
                print(f"    ✗ Error creating template for {scanner.tag}: {e}")  # fcg-rewrite
    
    print(f"\n✅ Created {created_count} official scanner template(s)")  # fcg-rewrite
    return created_count  # fcg-rewrite


def sync_custom_scanner_templates(db):  # fcg-rewrite
    """Create templates for custom scanners (S100+)"""
    print("\n=== Syncing Custom Scanner Templates ===")  # fcg-rewrite
    
    # Get all custom scanners
    custom_scanners = db.query(CustomScanner).join(Scanner).filter(  # fcg-rewrite
        Scanner.is_active == True  # fcg-rewrite
    ).all()
    
    if not custom_scanners:  # fcg-rewrite
        print("✓ No custom scanners found")  # fcg-rewrite
        return 0  # fcg-rewrite
    
    print(f"Found {len(custom_scanners)} custom scanner(s)")  # fcg-rewrite
    
    template_service = ResponseTemplateService(db)  # fcg-rewrite
    created_count = 0  # fcg-rewrite
    
    for cs in custom_scanners:  # fcg-rewrite
        scanner = cs.scanner  # fcg-rewrite
        app_id = cs.application_id  # fcg-rewrite
        tenant_id = cs.created_by  # fcg-rewrite
        
        # Get application to verify it's still active
        app = db.query(Application).filter(  # fcg-rewrite
            Application.id == app_id,  # fcg-rewrite
            Application.is_active == True  # fcg-rewrite
        ).first()  # fcg-rewrite
        
        if not app:  # fcg-rewrite
            print(f"  - Skipping {scanner.tag}: Application {app_id} not active")  # fcg-rewrite
            continue  # fcg-rewrite
        
        try:
            template = template_service.create_template_for_custom_scanner(  # fcg-rewrite
                scanner=scanner,  # fcg-rewrite
                application_id=app_id,  # fcg-rewrite
                tenant_id=tenant_id  # fcg-rewrite
            )
            
            if template:  # fcg-rewrite
                created_count += 1  # fcg-rewrite
                print(f"  ✓ Created template for {scanner.tag} ({scanner.name}) in app {app.name}")  # fcg-rewrite
            else:
                print(f"  - Template for {scanner.tag} already exists")  # fcg-rewrite
        
        except Exception as e:  # fcg-rewrite
            print(f"  ✗ Error creating template for {scanner.tag}: {e}")  # fcg-rewrite
    
    print(f"\n✅ Created {created_count} custom scanner template(s)")  # fcg-rewrite
    return created_count  # fcg-rewrite


def sync_marketplace_scanner_templates(db):  # fcg-rewrite
    """Create templates for purchased marketplace scanners"""
    print("\n=== Syncing Marketplace Scanner Templates ===")  # fcg-rewrite
    
    # Get all approved purchases
    approved_purchases = db.query(PackagePurchase).filter(  # fcg-rewrite
        PackagePurchase.status == 'approved'  # fcg-rewrite
    ).all()
    
    if not approved_purchases:  # fcg-rewrite
        print("✓ No approved purchases found")  # fcg-rewrite
        return 0  # fcg-rewrite
    
    print(f"Found {len(approved_purchases)} approved purchase(s)")  # fcg-rewrite
    
    template_service = ResponseTemplateService(db)  # fcg-rewrite
    created_count = 0  # fcg-rewrite
    
    for purchase in approved_purchases:  # fcg-rewrite
        package = purchase.package  # fcg-rewrite
        tenant_id = purchase.tenant_id  # fcg-rewrite
        
        if not package or not package.is_active:  # fcg-rewrite
            print(f"  - Skipping purchase {purchase.id}: Package not active")  # fcg-rewrite
            continue  # fcg-rewrite
        
        # Get all applications for this tenant
        applications = db.query(Application).filter(  # fcg-rewrite
            Application.tenant_id == tenant_id,  # fcg-rewrite
            Application.is_active == True  # fcg-rewrite
        ).all()
        
        if not applications:  # fcg-rewrite
            print(f"  - Skipping purchase {purchase.id}: No active applications for tenant {tenant_id}")  # fcg-rewrite
            continue  # fcg-rewrite
        
        # Get all scanners in the package
        scanners = db.query(Scanner).filter(  # fcg-rewrite
            Scanner.package_id == package.id,  # fcg-rewrite
            Scanner.is_active == True  # fcg-rewrite
        ).all()
        
        if not scanners:  # fcg-rewrite
            print(f"  - Skipping package {package.package_name}: No active scanners")  # fcg-rewrite
            continue  # fcg-rewrite
        
        print(f"\n  Processing package: {package.package_name} ({len(scanners)} scanner(s))")  # fcg-rewrite
        
        for app in applications:  # fcg-rewrite
            for scanner in scanners:  # fcg-rewrite
                try:
                    template = template_service.create_template_for_marketplace_scanner(  # fcg-rewrite
                        scanner=scanner,  # fcg-rewrite
                        application_id=app.id,  # fcg-rewrite
                        tenant_id=tenant_id  # fcg-rewrite
                    )
                    
                    if template:  # fcg-rewrite
                        created_count += 1  # fcg-rewrite
                        print(f"    ✓ Created template for {scanner.tag} ({scanner.name}) in app {app.name}")  # fcg-rewrite
                    else:
                        print(f"    - Template for {scanner.tag} in app {app.name} already exists")  # fcg-rewrite
                
                except Exception as e:  # fcg-rewrite
                    print(f"    ✗ Error creating template for {scanner.tag} in app {app.name}: {e}")  # fcg-rewrite
    
    print(f"\n✅ Created {created_count} marketplace scanner template(s)")  # fcg-rewrite
    return created_count  # fcg-rewrite


def sync_blacklist_templates(db):  # fcg-rewrite
    """Create templates for all blacklists"""
    print("\n=== Syncing Blacklist Templates ===")  # fcg-rewrite
    
    # Get all active blacklists
    blacklists = db.query(Blacklist).filter(  # fcg-rewrite
        Blacklist.is_active == True  # fcg-rewrite
    ).all()
    
    if not blacklists:  # fcg-rewrite
        print("✓ No active blacklists found")  # fcg-rewrite
        return 0  # fcg-rewrite
    
    print(f"Found {len(blacklists)} active blacklist(s)")  # fcg-rewrite
    
    template_service = ResponseTemplateService(db)  # fcg-rewrite
    created_count = 0  # fcg-rewrite
    
    for blacklist in blacklists:  # fcg-rewrite
        app_id = blacklist.application_id  # fcg-rewrite
        tenant_id = blacklist.tenant_id  # fcg-rewrite
        
        # Get application to verify it's still active
        app = db.query(Application).filter(  # fcg-rewrite
            Application.id == app_id,  # fcg-rewrite
            Application.is_active == True  # fcg-rewrite
        ).first()  # fcg-rewrite
        
        if not app:  # fcg-rewrite
            print(f"  - Skipping blacklist '{blacklist.name}': Application {app_id} not active")  # fcg-rewrite
            continue  # fcg-rewrite
        
        try:
            template = template_service.create_template_for_blacklist(  # fcg-rewrite
                blacklist=blacklist,  # fcg-rewrite
                application_id=app_id,  # fcg-rewrite
                tenant_id=tenant_id  # fcg-rewrite
            )
            
            if template:  # fcg-rewrite
                created_count += 1  # fcg-rewrite
                print(f"  ✓ Created template for blacklist '{blacklist.name}' in app {app.name}")  # fcg-rewrite
            else:
                print(f"  - Template for blacklist '{blacklist.name}' already exists")  # fcg-rewrite
        
        except Exception as e:  # fcg-rewrite
            print(f"  ✗ Error creating template for blacklist '{blacklist.name}': {e}")  # fcg-rewrite
    
    print(f"\n✅ Created {created_count} blacklist template(s)")  # fcg-rewrite
    return created_count  # fcg-rewrite


def main():  # fcg-rewrite
    """Main execution"""
    print("=" * 80)  # fcg-rewrite
    print("Response Template Sync Script")  # fcg-rewrite
    print("=" * 80)  # fcg-rewrite
    print("\nThis script will create response templates for existing:")  # fcg-rewrite
    print("  1. Official scanners (S1-S21)")  # fcg-rewrite
    print("  2. Custom scanners (S100+)")  # fcg-rewrite
    print("  3. Marketplace scanners (purchased packages)")  # fcg-rewrite
    print("  4. Blacklists")  # fcg-rewrite
    print("\nOnly missing templates will be created (no duplicates).\n")  # fcg-rewrite
    
    # Confirm execution
    confirm = input("Do you want to proceed? (yes/no): ").strip().lower()  # fcg-rewrite
    if confirm not in ['yes', 'y']:  # fcg-rewrite
        print("\n❌ Operation cancelled by user")  # fcg-rewrite
        return
    
    # Create database connection
    print(f"\nConnecting to database: {settings.database_url.split('@')[1]}")  # fcg-rewrite
    engine = create_engine(settings.database_url)  # fcg-rewrite
    SessionLocal = sessionmaker(bind=engine)  # fcg-rewrite
    db = SessionLocal()  # fcg-rewrite
    
    try:
        # Run sync operations
        official_count = sync_official_scanner_templates(db)  # fcg-rewrite
        custom_count = sync_custom_scanner_templates(db)  # fcg-rewrite
        marketplace_count = sync_marketplace_scanner_templates(db)  # fcg-rewrite
        blacklist_count = sync_blacklist_templates(db)  # fcg-rewrite
        
        # Summary
        total_count = official_count + custom_count + marketplace_count + blacklist_count  # fcg-rewrite
        
        print("\n" + "=" * 80)  # fcg-rewrite
        print("SUMMARY")  # fcg-rewrite
        print("=" * 80)  # fcg-rewrite
        print(f"Official Scanner Templates:   {official_count}")  # fcg-rewrite
        print(f"Custom Scanner Templates:     {custom_count}")  # fcg-rewrite
        print(f"Marketplace Scanner Templates: {marketplace_count}")  # fcg-rewrite
        print(f"Blacklist Templates:          {blacklist_count}")  # fcg-rewrite
        print("-" * 80)  # fcg-rewrite
        print(f"Total Templates Created:      {total_count}")  # fcg-rewrite
        print("=" * 80)  # fcg-rewrite
        
        if total_count > 0:  # fcg-rewrite
            print("\n✅ Response template sync completed successfully!")  # fcg-rewrite
        else:
            print("\n✓ All templates already exist - no action needed")  # fcg-rewrite
    
    except Exception as e:  # fcg-rewrite
        print(f"\n❌ Error during sync: {e}")  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        raise
    
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite


if __name__ == "__main__":  # fcg-rewrite
    main()

