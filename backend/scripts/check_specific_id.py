#!/usr/bin/env python3
"""
Check if a specific upstream API config ID exists in both old and new tables
"""

import sys  # fcg-rewrite
import os  # fcg-rewrite
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # fcg-rewrite

from database.connection import admin_engine  # fcg-rewrite
from sqlalchemy import text  # fcg-rewrite
import uuid  # fcg-rewrite

def check_specific_id(config_id_str: str):  # fcg-rewrite
    """Check if a specific ID exists"""
    try:
        config_id = uuid.UUID(config_id_str)  # fcg-rewrite
    except ValueError:  # fcg-rewrite
        print(f"❌ Invalid UUID: {config_id_str}")  # fcg-rewrite
        return
    
    print(f"Searching for ID: {config_id}\n")  # fcg-rewrite
    
    with admin_engine.connect() as conn:  # fcg-rewrite
        # Check in upstream_api_configs
        print("=== upstream_api_configs ===")  # fcg-rewrite
        result = conn.execute(text("""
            SELECT id, tenant_id, config_name, api_base_url, is_active, created_at
            FROM upstream_api_configs
            WHERE id = :config_id
        """), {"config_id": config_id})
        
        row = result.fetchone()  # fcg-rewrite
        if row:
            print(f"✅ Found in upstream_api_configs:")  # fcg-rewrite
            print(f"   ID: {row[0]}")  # fcg-rewrite
            print(f"   Tenant ID: {row[1]}")  # fcg-rewrite
            print(f"   Config Name: {row[2]}")  # fcg-rewrite
            print(f"   API Base URL: {row[3]}")  # fcg-rewrite
            print(f"   Is Active: {row[4]}")  # fcg-rewrite
            print(f"   Created At: {row[5]}")  # fcg-rewrite
        else:
            print(f"❌ Not found in upstream_api_configs")  # fcg-rewrite
        
        print("\n=== proxy_model_configs_deprecated ===")  # fcg-rewrite
        result = conn.execute(text("""
            SELECT id, tenant_id, config_name, api_base_url, enabled, created_at
            FROM proxy_model_configs_deprecated
            WHERE id = :config_id
        """), {"config_id": config_id})
        
        row = result.fetchone()  # fcg-rewrite
        if row:
            print(f"✅ Found in proxy_model_configs_deprecated:")  # fcg-rewrite
            print(f"   ID: {row[0]}")  # fcg-rewrite
            print(f"   Tenant ID: {row[1]}")  # fcg-rewrite
            print(f"   Config Name: {row[2]}")  # fcg-rewrite
            print(f"   API Base URL: {row[3]}")  # fcg-rewrite
            print(f"   Enabled: {row[4]}")  # fcg-rewrite
            print(f"   Created At: {row[5]}")  # fcg-rewrite
        else:
            print(f"❌ Not found in proxy_model_configs_deprecated")  # fcg-rewrite
        
        # Check if there are any configs for the user with this API base URL
        if row:
            tenant_id = row[1]  # fcg-rewrite
            api_base_url = row[3]  # fcg-rewrite
            print(f"\n=== Looking for migrated configs ===")  # fcg-rewrite
            print(f"   Tenant: {tenant_id}")  # fcg-rewrite
            print(f"   API Base URL: {api_base_url}")  # fcg-rewrite
            
            result = conn.execute(text("""
                SELECT id, config_name, api_base_url, is_active
                FROM upstream_api_configs
                WHERE tenant_id = :tenant_id 
                AND api_base_url = :api_base_url
            """), {"tenant_id": tenant_id, "api_base_url": api_base_url})
            
            for row in result:  # fcg-rewrite
                print(f"\n✅ Found migrated config:")  # fcg-rewrite
                print(f"   NEW ID: {row[0]}")  # fcg-rewrite
                print(f"   Config Name: {row[1]}")  # fcg-rewrite
                print(f"   API Base URL: {row[2]}")  # fcg-rewrite
                print(f"   Is Active: {row[3]}")  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    if len(sys.argv) != 2:  # fcg-rewrite
        print("Usage: python backend/scripts/check_specific_id.py <upstream_api_id>")  # fcg-rewrite
        sys.exit(1)  # fcg-rewrite
    
    config_id = sys.argv[1]  # fcg-rewrite
    check_specific_id(config_id)  # fcg-rewrite

