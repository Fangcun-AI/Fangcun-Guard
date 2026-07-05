#!/usr/bin/env python3
"""
Security check and repair script
Check common security configuration issues and provide repair suggestions
"""

import os  # fcg-rewrite
import sys  # fcg-rewrite
import secrets  # fcg-rewrite
import hashlib  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))  # fcg-rewrite

from config import settings  # fcg-rewrite

def generate_secure_jwt_key():  # fcg-rewrite
    """Generate secure JWT key"""
    return secrets.token_urlsafe(64)  # fcg-rewrite

def generate_secure_password(length=16):  # fcg-rewrite
    """Generate secure random password"""
    import string  # fcg-rewrite
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"  # fcg-rewrite
    return ''.join(secrets.choice(alphabet) for _ in range(length))  # fcg-rewrite

def check_jwt_security():  # fcg-rewrite
    """Check JWT configuration security"""
    issues = []  # fcg-rewrite

    # Check JWT key length and complexity
    if len(settings.jwt_secret_key) < 32:  # fcg-rewrite
        issues.append({  # fcg-rewrite
            'level': 'HIGH',  # fcg-rewrite
            'category': 'JWT',  # fcg-rewrite
            'issue': 'JWT key length is too short',  # fcg-rewrite
            'description': f'The current JWT key length is {len(settings.jwt_secret_key)} characters, it is recommended to be at least 64 characters',  # fcg-rewrite
            'fix': f'Suggested key: {generate_secure_jwt_key()}'  # fcg-rewrite
        })

    # Check if using default key
    weak_keys = [  # fcg-rewrite
        'fangcunguard-jwt-secret-key-2024',  # fcg-rewrite
        'your-secret-key',  # fcg-rewrite
        'secret',  # fcg-rewrite
        'jwt-secret'  # fcg-rewrite
    ]

    if settings.jwt_secret_key in weak_keys:  # fcg-rewrite
        issues.append({  # fcg-rewrite
            'level': 'CRITICAL',  # fcg-rewrite
            'category': 'JWT',  # fcg-rewrite
            'issue': 'Using default or weak JWT key',  # fcg-rewrite
            'description': 'The current key is default or known weak key',  # fcg-rewrite
            'fix': f'Please replace with secure key: {generate_secure_jwt_key()}'  # fcg-rewrite
        })

    return issues  # fcg-rewrite

def check_admin_security():  # fcg-rewrite
    """Check admin account security"""
    issues = []  # fcg-rewrite

    # Check default admin password
    weak_passwords = [  # fcg-rewrite
        'admin',  # fcg-rewrite
        'password',  # fcg-rewrite
        '123456',  # fcg-rewrite
        'fangcunguard@2024',  # fcg-rewrite
        'admin123'  # fcg-rewrite
    ]

    if settings.super_admin_password in weak_passwords:  # fcg-rewrite
        issues.append({  # fcg-rewrite
            'level': 'CRITICAL',  # fcg-rewrite
            'category': 'Admin',  # fcg-rewrite
            'issue': 'Using default or weak admin password',  # fcg-rewrite
            'description': 'The current admin password is too simple and can be easily cracked',  # fcg-rewrite
            'fix': f'Suggest replacing with strong password: {generate_secure_password()}'  # fcg-rewrite
        })

    # Check admin username
    if settings.super_admin_username == 'admin':  # fcg-rewrite
        issues.append({  # fcg-rewrite
            'level': 'MEDIUM',  # fcg-rewrite
            'category': 'Admin',  # fcg-rewrite
            'issue': 'Using default admin username',  # fcg-rewrite
            'description': 'Using default username increases the risk of attack',  # fcg-rewrite
            'fix': 'Suggest replacing with custom email address'  # fcg-rewrite
        })

    return issues  # fcg-rewrite

def check_database_security():  # fcg-rewrite
    """Check database security"""
    issues = []  # fcg-rewrite

    # Check database URL if it contains weak password
    db_url = settings.database_url  # fcg-rewrite
    if 'password' in db_url.lower() or '123456' in db_url:  # fcg-rewrite
        issues.append({  # fcg-rewrite
            'level': 'HIGH',  # fcg-rewrite
            'category': 'Database',  # fcg-rewrite
            'issue': 'Database password may be too simple',  # fcg-rewrite
            'description': 'Database connection string may contain weak password',  # fcg-rewrite
            'fix': 'Use strong password and consider using environment variables'  # fcg-rewrite
        })

    return issues  # fcg-rewrite

def check_cors_security():  # fcg-rewrite
    """Check CORS configuration security"""
    issues = []  # fcg-rewrite

    if settings.cors_origins == "*":  # fcg-rewrite
        issues.append({  # fcg-rewrite
            'level': 'MEDIUM',  # fcg-rewrite
            'category': 'CORS',  # fcg-rewrite
            'issue': 'CORS configuration is too permissive',  # fcg-rewrite
            'description': 'Allowing all origins may introduce security risks',  # fcg-rewrite
            'fix': 'Suggest configuring specific domains, such as: https://yourdomain.com'  # fcg-rewrite
        })

    return issues  # fcg-rewrite

def check_debug_mode():  # fcg-rewrite
    """Check debug mode"""
    issues = []  # fcg-rewrite

    if settings.debug:  # fcg-rewrite
        issues.append({  # fcg-rewrite
            'level': 'MEDIUM',  # fcg-rewrite
            'category': 'Debug',  # fcg-rewrite
            'issue': 'Debug mode is enabled in production environment',  # fcg-rewrite
            'description': 'Debug mode may leak sensitive information',  # fcg-rewrite
            'fix': 'Set DEBUG=false in production environment'  # fcg-rewrite
        })

    return issues  # fcg-rewrite

def check_smtp_security():  # fcg-rewrite
    """Check SMTP configuration security"""
    issues = []  # fcg-rewrite

    if settings.smtp_password and settings.smtp_password in ['your-email-password', 'password']:  # fcg-rewrite
        issues.append({  # fcg-rewrite
            'level': 'HIGH',  # fcg-rewrite
            'category': 'SMTP',  # fcg-rewrite
            'issue': 'Using default SMTP password',  # fcg-rewrite
            'description': 'SMTP password is not correctly configured',  # fcg-rewrite
            'fix': 'Configure correct email password'  # fcg-rewrite
        })

    return issues  # fcg-rewrite

def check_file_permissions():  # fcg-rewrite
    """Check critical file permissions"""
    issues = []  # fcg-rewrite

    # Check .env file permissions
    env_file = Path(__file__).parent.parent / '.env'  # fcg-rewrite
    if env_file.exists():  # fcg-rewrite
        stat_info = env_file.stat()  # fcg-rewrite
        # Check if it is readable by other users
        if stat_info.st_mode & 0o044:  # Other users or groups can read  # fcg-rewrite
            issues.append({  # fcg-rewrite
                'level': 'HIGH',  # fcg-rewrite
                'category': 'File Permissions',  # fcg-rewrite
                'issue': '.env file permissions are too permissive',  # fcg-rewrite
                'description': '.env file contains sensitive information, it should not be readable by other users',  # fcg-rewrite
                'fix': f'Run: chmod 600 {env_file}'  # fcg-rewrite
            })

    return issues  # fcg-rewrite

def check_api_key_security():  # fcg-rewrite
    """Check API key security"""
    issues = []  # fcg-rewrite

    if settings.guardrails_model_api_key == 'your-model-api-key':  # fcg-rewrite
        issues.append({  # fcg-rewrite
            'level': 'MEDIUM',  # fcg-rewrite
            'category': 'API Key',  # fcg-rewrite
            'issue': 'Model API key is not configured',  # fcg-rewrite
            'description': 'Using default placeholder may cause service to not work properly',  # fcg-rewrite
            'fix': 'Configure correct model API key'  # fcg-rewrite
        })

    return issues  # fcg-rewrite

def generate_security_report():  # fcg-rewrite
    """Generate security check report"""
    print("=" * 60)  # fcg-rewrite
    print("FangcunGuard Platform - Security check report")  # fcg-rewrite
    print("=" * 60)  # fcg-rewrite

    all_issues = []  # fcg-rewrite

    # Run all checks
    checks = [  # fcg-rewrite
        ('JWT security', check_jwt_security),  # fcg-rewrite
        ('Admin account security', check_admin_security),  # fcg-rewrite
        ('Database security', check_database_security),  # fcg-rewrite
        ('CORS configuration', check_cors_security),  # fcg-rewrite
        ('Debug mode', check_debug_mode),  # fcg-rewrite
        ('SMTP configuration', check_smtp_security),  # fcg-rewrite
        ('File permissions', check_file_permissions),  # fcg-rewrite
        ('API key security', check_api_key_security),  # fcg-rewrite
    ]

    for check_name, check_func in checks:  # fcg-rewrite
        print(f"\n📋 Check: {check_name}")  # fcg-rewrite
        issues = check_func()  # fcg-rewrite

        if not issues:  # fcg-rewrite
            print("✅ No security issues found")  # fcg-rewrite
        else:
            for issue in issues:  # fcg-rewrite
                all_issues.append(issue)  # fcg-rewrite
                level_emoji = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}  # fcg-rewrite
                print(f"{level_emoji.get(issue['level'], '⚪')} {issue['level']}: {issue['issue']}")  # fcg-rewrite
                print(f"   Description: {issue['description']}")  # fcg-rewrite
                print(f"   Fix suggestion: {issue['fix']}")  # fcg-rewrite
                print()

    # Generate report
    print("\n" + "=" * 60)  # fcg-rewrite
    print("Security check summary")  # fcg-rewrite
    print("=" * 60)  # fcg-rewrite

    if not all_issues:  # fcg-rewrite
        print("🎉 Congratulations! No security issues found.")  # fcg-rewrite
        return True  # fcg-rewrite

    critical_count = len([i for i in all_issues if i['level'] == 'CRITICAL'])  # fcg-rewrite
    high_count = len([i for i in all_issues if i['level'] == 'HIGH'])  # fcg-rewrite
    medium_count = len([i for i in all_issues if i['level'] == 'MEDIUM'])  # fcg-rewrite
    low_count = len([i for i in all_issues if i['level'] == 'LOW'])  # fcg-rewrite

    print(f"🔴 Critical issues: {critical_count}")  # fcg-rewrite
    print(f"🟠 High risk issues: {high_count}")  # fcg-rewrite
    print(f"🟡 Medium risk issues: {medium_count}")  # fcg-rewrite
    print(f"🟢 Low risk issues: {low_count}")  # fcg-rewrite
    print(f"📊 Total: {len(all_issues)} issues")  # fcg-rewrite

    if critical_count > 0:  # fcg-rewrite
        print("\n⚠️  Warning: Critical security issues found, please fix immediately!")  # fcg-rewrite
        return False  # fcg-rewrite
    elif high_count > 0:  # fcg-rewrite
        print("\n⚠️  Warning: High risk security issues found, please fix as soon as possible.")  # fcg-rewrite
        return False  # fcg-rewrite
    else:
        print("\n✅ No critical security issues found, but it is recommended to fix medium and low risk issues to improve security.")  # fcg-rewrite
        return True  # fcg-rewrite

def generate_secure_env_template():  # fcg-rewrite
    """Generate secure .env template"""
    print("\n" + "=" * 60)  # fcg-rewrite
    print("Generate secure configuration template")  # fcg-rewrite
    print("=" * 60)  # fcg-rewrite

    template = f"""# Application configuration  # fcg-rewrite
APP_NAME=FangcunGuard
APP_VERSION=1.0.0
DEBUG=false

# Super admin configuration
# ⚠️ Please make sure to change the default admin username and password!
SUPER_ADMIN_USERNAME=admin@yourdomain.com
SUPER_ADMIN_PASSWORD={generate_secure_password(20)}

# Data directory configuration
DATA_DIR=~/fangcunguard-data

# Database configuration
# ⚠️ Please use a strong password
DATABASE_URL=postgresql://fangcunguard:YOUR_SECURE_DB_PASSWORD@localhost:54321/fangcunguard

# Model configuration
GUARDRAILS_MODEL_API_URL=http://localhost:58002/v1
GUARDRAILS_MODEL_API_KEY=your-actual-model-api-key
GUARDRAILS_MODEL_NAME=Qwen3Guard-Gen-8B

# API configuration
# ⚠️ In production environment, please configure specific domains
CORS_ORIGINS=https://yourdomain.com

# Logging configuration
LOG_LEVEL=INFO

# JWT configuration
# ⚠️ Use a secure random key
JWT_SECRET_KEY={generate_secure_jwt_key()}
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Email configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-secure-email-password
SMTP_USE_TLS=true
SMTP_USE_SSL=false

# Server configuration
UVICORN_WORKERS=4
MAX_CONCURRENT_REQUESTS=100
"""

    print("🔐 Secure .env configuration template:")  # fcg-rewrite
    print(template)  # fcg-rewrite

    # Save to file
    template_file = Path(__file__).parent.parent / '.env.secure.template'  # fcg-rewrite
    with open(template_file, 'w') as f:  # fcg-rewrite
        f.write(template)  # fcg-rewrite

    print(f"✅ Template saved to: {template_file}")  # fcg-rewrite
    print("📋 Please update your .env file according to the template")  # fcg-rewrite

def main():  # fcg-rewrite
    print("🛡️  FangcunGuard Platform - Security check tool")  # fcg-rewrite
    print("This tool will check common security configuration issues and provide repair suggestions\n")  # fcg-rewrite

    # Generate security check report
    is_secure = generate_security_report()  # fcg-rewrite

    # Generate secure configuration template
    generate_secure_env_template()  # fcg-rewrite

    print("\n" + "=" * 60)  # fcg-rewrite
    print("Security recommendations")  # fcg-rewrite
    print("=" * 60)  # fcg-rewrite
    print("1. 🔐 Update JWT key and admin password regularly")  # fcg-rewrite
    print("2. 🔒 Deploy production environment using HTTPS")  # fcg-rewrite
    print("3. 🌐 Configure firewall to limit unnecessary port access")  # fcg-rewrite
    print("4. 📊 Enable access log monitoring")  # fcg-rewrite
    print("5. 🔄 Backup database regularly")  # fcg-rewrite
    print("6. 📱 Consider enabling two-factor authentication (2FA)")  # fcg-rewrite
    print("7. 🛡️  Run this security check tool regularly")  # fcg-rewrite

    if not is_secure:  # fcg-rewrite
        print("\n❌ Security check failed, please fix the issues and run again.")  # fcg-rewrite
        sys.exit(1)  # fcg-rewrite
    else:
        print("\n✅ Security check passed!")  # fcg-rewrite
        sys.exit(0)  # fcg-rewrite

if __name__ == "__main__":  # fcg-rewrite
    main()