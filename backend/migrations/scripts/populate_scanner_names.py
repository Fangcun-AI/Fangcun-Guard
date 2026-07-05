#!/usr/bin/env python3
"""
Populate Scanner Names - Data Maintenance Script
This script populates missing scanner_name fields in knowledge_bases and response_templates tables.

Use this script when:
1. After running migration 026 on an existing database with data
2. If scanner_name fields are missing or null for existing records
3. As part of database maintenance to ensure data consistency

This is a safe operation that only updates NULL scanner_name fields.
"""

import sys  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent  # fcg-rewrite
sys.path.insert(0, str(backend_dir))  # fcg-rewrite

from sqlalchemy import create_engine, text  # fcg-rewrite
from sqlalchemy.orm import sessionmaker  # fcg-rewrite
from config import settings  # fcg-rewrite
from database.models import KnowledgeBase, ResponseTemplate, Scanner, Blacklist, Whitelist  # fcg-rewrite

def populate_knowledge_base_scanner_names(db):  # fcg-rewrite
    """Populate scanner_name for knowledge bases"""
    print("\n=== Populating Knowledge Base Scanner Names ===")  # fcg-rewrite

    # Get all knowledge bases with null scanner_name
    kb_records = db.query(KnowledgeBase).filter(  # fcg-rewrite
        KnowledgeBase.scanner_name.is_(None),  # fcg-rewrite
        KnowledgeBase.scanner_type.isnot(None),  # fcg-rewrite
        KnowledgeBase.scanner_identifier.isnot(None)  # fcg-rewrite
    ).all()

    if not kb_records:  # fcg-rewrite
        print("✓ All knowledge bases already have scanner_name populated")  # fcg-rewrite
        return 0  # fcg-rewrite

    print(f"Found {len(kb_records)} knowledge base(s) with missing scanner_name\n")  # fcg-rewrite

    updated_count = 0  # fcg-rewrite
    for kb in kb_records:  # fcg-rewrite
        scanner_name = None  # fcg-rewrite

        try:
            if kb.scanner_type == 'blacklist':  # fcg-rewrite
                # Get name from blacklist table
                blacklist = db.query(Blacklist).filter(  # fcg-rewrite
                    Blacklist.application_id == kb.application_id,  # fcg-rewrite
                    Blacklist.name == kb.scanner_identifier  # fcg-rewrite
                ).first()  # fcg-rewrite
                if blacklist:  # fcg-rewrite
                    scanner_name = blacklist.name  # fcg-rewrite

            elif kb.scanner_type == 'whitelist':  # fcg-rewrite
                # Get name from whitelist table
                whitelist = db.query(Whitelist).filter(  # fcg-rewrite
                    Whitelist.application_id == kb.application_id,  # fcg-rewrite
                    Whitelist.name == kb.scanner_identifier  # fcg-rewrite
                ).first()  # fcg-rewrite
                if whitelist:  # fcg-rewrite
                    scanner_name = whitelist.name  # fcg-rewrite

            elif kb.scanner_type in ['official_scanner', 'marketplace_scanner', 'custom_scanner']:  # fcg-rewrite
                # Get name from scanners table
                scanner = db.query(Scanner).filter(  # fcg-rewrite
                    Scanner.tag == kb.scanner_identifier  # fcg-rewrite
                ).first()  # fcg-rewrite
                if scanner:  # fcg-rewrite
                    scanner_name = scanner.name  # fcg-rewrite

            if scanner_name:  # fcg-rewrite
                kb.scanner_name = scanner_name  # fcg-rewrite
                updated_count += 1  # fcg-rewrite
                print(f"  ✓ KB #{kb.id}: {kb.scanner_type}/{kb.scanner_identifier} → {scanner_name}")  # fcg-rewrite
            else:
                print(f"  ⚠ KB #{kb.id}: Could not find scanner for {kb.scanner_type}/{kb.scanner_identifier}")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            print(f"  ✗ KB #{kb.id}: Error - {e}")  # fcg-rewrite

    if updated_count > 0:  # fcg-rewrite
        db.commit()  # fcg-rewrite
        print(f"\n✅ Updated {updated_count} knowledge base(s)")  # fcg-rewrite

    return updated_count  # fcg-rewrite

def populate_response_template_scanner_names(db):  # fcg-rewrite
    """Populate scanner_name for response templates"""
    print("\n=== Populating Response Template Scanner Names ===")  # fcg-rewrite

    # Get all response templates with null scanner_name
    rt_records = db.query(ResponseTemplate).filter(  # fcg-rewrite
        ResponseTemplate.scanner_name.is_(None),  # fcg-rewrite
        ResponseTemplate.scanner_type.isnot(None),  # fcg-rewrite
        ResponseTemplate.scanner_identifier.isnot(None)  # fcg-rewrite
    ).all()

    if not rt_records:  # fcg-rewrite
        print("✓ All response templates already have scanner_name populated")  # fcg-rewrite
        return 0  # fcg-rewrite

    print(f"Found {len(rt_records)} response template(s) with missing scanner_name\n")  # fcg-rewrite

    updated_count = 0  # fcg-rewrite
    for rt in rt_records:  # fcg-rewrite
        scanner_name = None  # fcg-rewrite

        try:
            if rt.scanner_type == 'blacklist':  # fcg-rewrite
                # Get name from blacklist table
                blacklist = db.query(Blacklist).filter(  # fcg-rewrite
                    Blacklist.application_id == rt.application_id,  # fcg-rewrite
                    Blacklist.name == rt.scanner_identifier  # fcg-rewrite
                ).first()  # fcg-rewrite
                if blacklist:  # fcg-rewrite
                    scanner_name = blacklist.name  # fcg-rewrite

            elif rt.scanner_type == 'whitelist':  # fcg-rewrite
                # Get name from whitelist table
                whitelist = db.query(Whitelist).filter(  # fcg-rewrite
                    Whitelist.application_id == rt.application_id,  # fcg-rewrite
                    Whitelist.name == rt.scanner_identifier  # fcg-rewrite
                ).first()  # fcg-rewrite
                if whitelist:  # fcg-rewrite
                    scanner_name = whitelist.name  # fcg-rewrite

            elif rt.scanner_type in ['official_scanner', 'marketplace_scanner', 'custom_scanner']:  # fcg-rewrite
                # Get name from scanners table
                scanner = db.query(Scanner).filter(  # fcg-rewrite
                    Scanner.tag == rt.scanner_identifier  # fcg-rewrite
                ).first()  # fcg-rewrite
                if scanner:  # fcg-rewrite
                    scanner_name = scanner.name  # fcg-rewrite

            if scanner_name:  # fcg-rewrite
                rt.scanner_name = scanner_name  # fcg-rewrite
                updated_count += 1  # fcg-rewrite
                print(f"  ✓ Template #{rt.id}: {rt.scanner_type}/{rt.scanner_identifier} → {scanner_name}")  # fcg-rewrite
            else:
                print(f"  ⚠ Template #{rt.id}: Could not find scanner for {rt.scanner_type}/{rt.scanner_identifier}")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            print(f"  ✗ Template #{rt.id}: Error - {e}")  # fcg-rewrite

    if updated_count > 0:  # fcg-rewrite
        db.commit()  # fcg-rewrite
        print(f"\n✅ Updated {updated_count} response template(s)")  # fcg-rewrite

    return updated_count  # fcg-rewrite

def main():  # fcg-rewrite
    print("=== Scanner Name Population Tool ===")  # fcg-rewrite
    print("This script populates missing scanner_name fields for knowledge bases and response templates.\n")  # fcg-rewrite

    # Create database session
    engine = create_engine(settings.database_url)  # fcg-rewrite
    SessionLocal = sessionmaker(bind=engine)  # fcg-rewrite
    db = SessionLocal()  # fcg-rewrite

    try:
        # Populate knowledge base scanner names
        kb_count = populate_knowledge_base_scanner_names(db)  # fcg-rewrite

        # Populate response template scanner names
        rt_count = populate_response_template_scanner_names(db)  # fcg-rewrite

        # Summary
        print("\n=== Summary ===")  # fcg-rewrite
        print(f"Knowledge Bases Updated: {kb_count}")  # fcg-rewrite
        print(f"Response Templates Updated: {rt_count}")  # fcg-rewrite
        print(f"Total Records Updated: {kb_count + rt_count}")  # fcg-rewrite

        if kb_count + rt_count > 0:  # fcg-rewrite
            print("\n✅ All missing scanner_name fields have been populated!")  # fcg-rewrite
        else:
            print("\n✓ No updates needed - all records are already up to date")  # fcg-rewrite

    except Exception as e:  # fcg-rewrite
        print(f"\n❌ Error: {e}")  # fcg-rewrite
        import traceback  # fcg-rewrite
        traceback.print_exc()  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        return 1  # fcg-rewrite
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite

    return 0  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    sys.exit(main())  # fcg-rewrite

