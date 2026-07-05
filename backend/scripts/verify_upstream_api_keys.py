#!/usr/bin/env python3
"""
Verify Upstream API Key configuration script
Help diagnose whether the xxai API key is used as an Upstream API Key incorrectly
"""

import sys  # fcg-rewrite
import os  # fcg-rewrite

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # fcg-rewrite

from database.connection import get_admin_db_session  # fcg-rewrite
from database.models import UpstreamApiConfig  # fcg-rewrite
from cryptography.fernet import Fernet  # fcg-rewrite
from config import settings  # fcg-rewrite

def get_encryption_key() -> bytes:  # fcg-rewrite
    """Get encryption key"""
    key_file = f"{settings.data_dir}/proxy_encryption.key"  # fcg-rewrite
    if os.path.exists(key_file):  # fcg-rewrite
        with open(key_file, 'rb') as f:  # fcg-rewrite
            return f.read()  # fcg-rewrite
    else:
        raise FileNotFoundError(f"Encryption key file not found: {key_file}")  # fcg-rewrite

def decrypt_api_key(encrypted_api_key: str, cipher_suite) -> str:  # fcg-rewrite
    """Decrypt API key"""
    return cipher_suite.decrypt(encrypted_api_key.encode()).decode()  # fcg-rewrite

def main():  # fcg-rewrite
    print("=" * 80)  # fcg-rewrite
    print("Verify Upstream API Key configuration")  # fcg-rewrite
    print("=" * 80)  # fcg-rewrite
    print()
    
    # Get encryption key
    try:
        encryption_key = get_encryption_key()  # fcg-rewrite
        cipher_suite = Fernet(encryption_key)  # fcg-rewrite
    except Exception as e:  # fcg-rewrite
        print(f"❌ Failed to get encryption key: {e}")  # fcg-rewrite
        return 1  # fcg-rewrite
    
    # Query all upstream API configurations
    db = get_admin_db_session()  # fcg-rewrite
    try:
        configs = db.query(UpstreamApiConfig).all()  # fcg-rewrite
        
        if not configs:  # fcg-rewrite
            print("📝 No Upstream API configurations found")  # fcg-rewrite
            return 0  # fcg-rewrite
        
        print(f"Found {len(configs)} Upstream API configurations:\n")  # fcg-rewrite
        
        issues_found = False  # fcg-rewrite
        
        for config in configs:  # fcg-rewrite
            print(f"Configuration name: {config.config_name}")  # fcg-rewrite
            print(f"  UUID: {config.id}")  # fcg-rewrite
            print(f"  Upstream API URL: {config.api_base_url}")  # fcg-rewrite
            print(f"  Tenant ID: {config.tenant_id}")  # fcg-rewrite
            
            # Decrypt and check API key
            try:
                decrypted_key = decrypt_api_key(config.api_key_encrypted, cipher_suite)  # fcg-rewrite
                
                # Mask the key for display
                if len(decrypted_key) > 12:  # fcg-rewrite
                    masked_key = f"{decrypted_key[:8]}...{decrypted_key[-4:]}"  # fcg-rewrite
                else:
                    masked_key = "***"  # fcg-rewrite
                
                print(f"  Decrypted API Key: {masked_key}")  # fcg-rewrite
                
                # Check if the key looks like an xxai key (potential misconfiguration)
                if decrypted_key.startswith('sk-xxai-'):  # fcg-rewrite
                    print(f"  ⚠️  Warning: This API Key looks like an FangcunGuard platform API Key (sk-xxai-)")  # fcg-rewrite
                    print(f"      Upstream API Key should be the API Key for the upstream service (e.g. OpenAI)")  # fcg-rewrite
                    print(f"      Not the API Key for accessing the FangcunGuard platform")  # fcg-rewrite
                    issues_found = True  # fcg-rewrite
                elif decrypted_key.startswith('sk-'):  # fcg-rewrite
                    print(f"  ✓ API Key format is normal (starts with sk-)")  # fcg-rewrite
                else:
                    print(f"  ℹ️  API Key format: other format")  # fcg-rewrite
                
            except Exception as e:  # fcg-rewrite
                print(f"  ❌  Decryption failed: {e}")  # fcg-rewrite
                issues_found = True  # fcg-rewrite
            
            print()
        
        if issues_found:  # fcg-rewrite
            print("=" * 80)  # fcg-rewrite
            print("⚠️  Found potential configuration issues!")  # fcg-rewrite
            print()
            print("Explanation:")  # fcg-rewrite
            print("  • FangcunGuard API Key (sk-xxai-xxx): Used for client access to the FangcunGuard platform")  # fcg-rewrite
            print("  • Upstream API Key (e.g. sk-xxx): Stored in the configuration, used for FangcunGuard to call the upstream service")  # fcg-rewrite
            print()
            print("If you incorrectly configured the key in the sk-xxai- format as an Upstream API Key,")  # fcg-rewrite
            print("please edit the configuration in the management interface to fill in the correct upstream service API Key.")  # fcg-rewrite
            print("=" * 80)  # fcg-rewrite
        else:
            print("=" * 80)  # fcg-rewrite
            print("✓ All configurations look normal")  # fcg-rewrite
            print("=" * 80)  # fcg-rewrite
        
        return 1 if issues_found else 0  # fcg-rewrite
        
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    sys.exit(main())  # fcg-rewrite

