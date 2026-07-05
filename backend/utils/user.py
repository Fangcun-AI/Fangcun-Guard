from datetime import datetime, timedelta  # fcg-rewrite
import secrets  # fcg-rewrite
import string  # fcg-rewrite
import uuid  # fcg-rewrite
from typing import Optional, Union  # fcg-rewrite

from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import ApiKey, Application, EmailVerification, Tenant  # fcg-rewrite
from utils.auth import get_password_hash  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

API_KEY_PREFIX = "sk-xxai-"  # fcg-rewrite
API_KEY_LENGTH = 64  # fcg-rewrite


def _resolve_tenant_uuid(value: Union[str, uuid.UUID]) -> Optional[uuid.UUID]:  # fcg-rewrite
    """Coerce tenant ids into UUID instances."""
    if isinstance(value, uuid.UUID):  # fcg-rewrite
        return value  # fcg-rewrite
    try:
        return uuid.UUID(value)  # fcg-rewrite
    except (TypeError, ValueError):  # fcg-rewrite
        return None  # fcg-rewrite


def new_api_key() -> str:  # fcg-rewrite
    """Create a tenant or application API key."""
    alphabet = string.ascii_letters + string.digits  # fcg-rewrite
    token_len = API_KEY_LENGTH - len(API_KEY_PREFIX)  # fcg-rewrite
    token = ''.join(secrets.choice(alphabet) for _ in range(token_len))  # fcg-rewrite
    return f"{API_KEY_PREFIX}{token}"  # fcg-rewrite


def find_user_by_email(db: Session, email: str) -> Optional[Tenant]:  # fcg-rewrite
    """Return a tenant by email."""
    return db.query(Tenant).filter(Tenant.email == email).first()  # fcg-rewrite


def find_tenant_by_key(db: Session, api_key: str) -> Optional[Tenant]:  # fcg-rewrite
    """
    Return a verified tenant for a legacy tenant API key.

    This only checks ``tenants.api_key`` and is kept for backward compatibility.
    """
    return db.query(Tenant).filter(  # fcg-rewrite
        Tenant.api_key == api_key,  # fcg-rewrite
        Tenant.is_verified == True,  # fcg-rewrite
        Tenant.is_active == True  # fcg-rewrite
    ).first()  # fcg-rewrite


def find_app_by_key(db: Session, api_key: str) -> Optional[dict]:  # fcg-rewrite
    """Return application and tenant details for an application API key."""
    row = db.query(ApiKey, Application, Tenant).join(  # fcg-rewrite
        Application, ApiKey.application_id == Application.id  # fcg-rewrite
    ).join(
        Tenant, ApiKey.tenant_id == Tenant.id  # fcg-rewrite
    ).filter(  # fcg-rewrite
        ApiKey.key == api_key,  # fcg-rewrite
        ApiKey.is_active == True,  # fcg-rewrite
        Application.is_active == True,  # fcg-rewrite
        Tenant.is_verified == True,  # fcg-rewrite
        Tenant.is_active == True  # fcg-rewrite
    ).first()  # fcg-rewrite

    if not row:  # fcg-rewrite
        return None  # fcg-rewrite

    key_row, app, tenant = row  # fcg-rewrite

    try:
        key_row.last_used_at = datetime.utcnow()  # fcg-rewrite
        db.commit()  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.warning(f"Failed to update API key last_used_at: {exc}")  # fcg-rewrite
        db.rollback()  # fcg-rewrite

    return {  # fcg-rewrite
        "tenant_id": str(tenant.id),  # fcg-rewrite
        "tenant_email": tenant.email,  # fcg-rewrite
        "application_id": str(app.id),  # fcg-rewrite
        "application_name": app.name,  # fcg-rewrite
        "api_key_id": str(key_row.id),  # fcg-rewrite
        "api_key": api_key,  # fcg-rewrite
    }


def add_user(db: Session, email: str, password: str) -> Tenant:  # fcg-rewrite
    """Create a new tenant."""
    from utils.validators import validate_password_strength  # fcg-rewrite

    password_check = validate_password_strength(password)  # fcg-rewrite
    if not password_check["is_valid"]:  # fcg-rewrite
        issues = ", ".join(password_check["errors"])  # fcg-rewrite
        raise ValueError(f"Password does not meet security requirements: {issues}")  # fcg-rewrite

    password_hash = get_password_hash(password)  # fcg-rewrite
    api_key = new_api_key()  # fcg-rewrite

    while db.query(Tenant).filter(Tenant.api_key == api_key).first():  # fcg-rewrite
        api_key = new_api_key()  # fcg-rewrite

    tenant = Tenant(  # fcg-rewrite
        email=email,  # fcg-rewrite
        password_hash=password_hash,  # fcg-rewrite
        api_key=api_key,  # fcg-rewrite
        is_active=False,  # fcg-rewrite
        is_verified=False,  # fcg-rewrite
    )
    db.add(tenant)  # fcg-rewrite
    db.commit()  # fcg-rewrite
    db.refresh(tenant)  # fcg-rewrite
    return tenant  # fcg-rewrite


def add_default_app_key(  # fcg-rewrite
    db: Session,  # fcg-rewrite
    tenant_id: Union[str, uuid.UUID],  # fcg-rewrite
    tenant_email: str,  # fcg-rewrite
) -> Optional[dict]:  # fcg-rewrite
    """Create the default application and application key for a tenant."""
    tenant_uuid = _resolve_tenant_uuid(tenant_id)  # fcg-rewrite
    if tenant_uuid is None:  # fcg-rewrite
        logger.error(f"Failed to create default application for tenant {tenant_email}: invalid tenant id")  # fcg-rewrite
        return None  # fcg-rewrite

    try:
        app = Application(  # fcg-rewrite
            tenant_id=tenant_uuid,  # fcg-rewrite
            name="Default Application",  # fcg-rewrite
            description="Default application created automatically",  # fcg-rewrite
            is_active=True,  # fcg-rewrite
            source='manual',  # fcg-rewrite
        )
        db.add(app)  # fcg-rewrite
        db.flush()  # fcg-rewrite

        api_key = new_api_key()  # fcg-rewrite
        while db.query(ApiKey).filter(ApiKey.key == api_key).first():  # fcg-rewrite
            api_key = new_api_key()  # fcg-rewrite

        app_key = ApiKey(  # fcg-rewrite
            tenant_id=tenant_uuid,  # fcg-rewrite
            application_id=app.id,  # fcg-rewrite
            key=api_key,  # fcg-rewrite
            name="Default API Key",  # fcg-rewrite
            is_active=True,  # fcg-rewrite
        )
        db.add(app_key)  # fcg-rewrite
        db.flush()  # fcg-rewrite

        try:
            from admin_console.routes.application_workspace_routes import initialize_application_configs  # fcg-rewrite

            initialize_application_configs(db, str(app.id), str(tenant_uuid))  # fcg-rewrite
            logger.info(f"Created default application '{app.name}' with API key for tenant {tenant_email}")  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to initialize configs for default application: {exc}")  # fcg-rewrite

        db.commit()  # fcg-rewrite
        return {  # fcg-rewrite
            "application_id": str(app.id),  # fcg-rewrite
            "application_name": app.name,  # fcg-rewrite
            "api_key": api_key,  # fcg-rewrite
        }
    except Exception as exc:  # fcg-rewrite
        logger.error(f"Failed to create default application for tenant {tenant_email}: {exc}")  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        return None  # fcg-rewrite


def _seed_verified_user(db: Session, tenant: Tenant) -> None:  # fcg-rewrite
    """Create the default resources for a newly verified tenant."""
    try:
        app_data = add_default_app_key(db, tenant.id, tenant.email)  # fcg-rewrite
        if app_data:  # fcg-rewrite
            logger.info(f"Created default application for tenant {tenant.email}: app_id={app_data['application_id']}")  # fcg-rewrite
        else:
            logger.warning(f"Failed to create default application for tenant {tenant.email}")  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.error(f"Error creating default application for tenant {tenant.email}: {exc}")  # fcg-rewrite

    try:
        from services.template_service import create_user_default_templates  # fcg-rewrite

        template_count = create_user_default_templates(db, tenant.id)  # fcg-rewrite
        print(f"Created {template_count} default reply templates for tenant {tenant.email}")  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        print(f"Failed to create default reply templates for tenant {tenant.email}: {exc}")  # fcg-rewrite

    try:
        from services.data_security_service import create_user_default_entity_types  # fcg-rewrite

        entity_count = create_user_default_entity_types(db, str(tenant.id))  # fcg-rewrite
        print(f"Created {entity_count} default entity type configurations for tenant {tenant.email}")  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        print(f"Failed to create default entity type configurations for tenant {tenant.email}: {exc}")  # fcg-rewrite

    try:
        from services.billing_service import billing_service  # fcg-rewrite

        billing_service.create_subscription(str(tenant.id), 'free', db)  # fcg-rewrite
        print(f"Created free subscription for tenant {tenant.email}")  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        print(f"Failed to create subscription for tenant {tenant.email}: {exc}")  # fcg-rewrite

    try:
        from config import settings  # fcg-rewrite
        from services.rate_limiter import RateLimitService  # fcg-rewrite

        rate_limit_service = RateLimitService(db)  # fcg-rewrite
        default_rps = settings.default_rate_limit_rps  # fcg-rewrite
        rate_limit_service.set_user_rate_limit(str(tenant.id), default_rps)  # fcg-rewrite
        print(f"Created rate limit ({default_rps} RPS) for tenant {tenant.email}")  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        print(f"Failed to create rate limit for tenant {tenant.email}: {exc}")  # fcg-rewrite


def confirm_user_email(db: Session, email: str, verification_code: str) -> bool:  # fcg-rewrite
    """Verify a tenant email and bootstrap the tenant defaults."""
    verification = db.query(EmailVerification).filter(  # fcg-rewrite
        EmailVerification.email == email,  # fcg-rewrite
        EmailVerification.verification_code == verification_code,  # fcg-rewrite
        EmailVerification.is_used == False,  # fcg-rewrite
        EmailVerification.expires_at > datetime.utcnow()  # fcg-rewrite
    ).first()  # fcg-rewrite

    if not verification:  # fcg-rewrite
        return False  # fcg-rewrite

    verification.is_used = True  # fcg-rewrite
    tenant = db.query(Tenant).filter(Tenant.email == email).first()  # fcg-rewrite
    if tenant:  # fcg-rewrite
        tenant.is_active = True  # fcg-rewrite
        tenant.is_verified = True  # fcg-rewrite

    db.commit()  # fcg-rewrite

    if tenant:  # fcg-rewrite
        _seed_verified_user(db, tenant)  # fcg-rewrite

    return True  # fcg-rewrite


def rotate_api_key(db: Session, tenant_id: Union[str, uuid.UUID]) -> Optional[str]:  # fcg-rewrite
    """Regenerate the legacy tenant API key."""
    tenant_uuid = _resolve_tenant_uuid(tenant_id)  # fcg-rewrite
    if tenant_uuid is None:  # fcg-rewrite
        return None  # fcg-rewrite

    tenant = db.query(Tenant).filter(Tenant.id == tenant_uuid).first()  # fcg-rewrite
    if not tenant:  # fcg-rewrite
        return None  # fcg-rewrite

    api_key = new_api_key()  # fcg-rewrite
    while db.query(Tenant).filter(Tenant.api_key == api_key).first():  # fcg-rewrite
        api_key = new_api_key()  # fcg-rewrite

    tenant.api_key = api_key  # fcg-rewrite
    db.commit()  # fcg-rewrite
    db.refresh(tenant)  # fcg-rewrite
    return api_key  # fcg-rewrite


def save_login_attempt(  # fcg-rewrite
    db: Session,  # fcg-rewrite
    email: str,  # fcg-rewrite
    ip_address: str,  # fcg-rewrite
    user_agent: str,  # fcg-rewrite
    success: bool,  # fcg-rewrite
) -> None:  # fcg-rewrite
    """Persist a login attempt."""
    from database.models import LoginAttempt  # fcg-rewrite

    attempt = LoginAttempt(  # fcg-rewrite
        email=email,  # fcg-rewrite
        ip_address=ip_address,  # fcg-rewrite
        user_agent=user_agent or "",  # fcg-rewrite
        success=success,  # fcg-rewrite
    )
    db.add(attempt)  # fcg-rewrite
    db.commit()  # fcg-rewrite


def login_rate_ok(  # fcg-rewrite
    db: Session,  # fcg-rewrite
    email: str,  # fcg-rewrite
    ip_address: str,  # fcg-rewrite
    time_window_minutes: int = 15,  # fcg-rewrite
    max_attempts: int = 5,  # fcg-rewrite
) -> bool:  # fcg-rewrite
    """Return whether the login failure count is below the configured limit."""
    from database.models import LoginAttempt  # fcg-rewrite

    cutoff = datetime.utcnow() - timedelta(minutes=time_window_minutes)  # fcg-rewrite
    email_failures = db.query(LoginAttempt).filter(  # fcg-rewrite
        LoginAttempt.email == email,  # fcg-rewrite
        LoginAttempt.success == False,  # fcg-rewrite
        LoginAttempt.attempted_at >= cutoff  # fcg-rewrite
    ).count()  # fcg-rewrite
    return email_failures < max_attempts  # fcg-rewrite


def prune_login_attempts(db: Session, days_to_keep: int = 30) -> int:  # fcg-rewrite
    """Delete old login-attempt records."""
    from database.models import LoginAttempt  # fcg-rewrite

    cutoff = datetime.utcnow() - timedelta(days=days_to_keep)  # fcg-rewrite

    try:
        removed = db.query(LoginAttempt).filter(  # fcg-rewrite
            LoginAttempt.attempted_at < cutoff  # fcg-rewrite
        ).delete()  # fcg-rewrite
        db.commit()  # fcg-rewrite
        if removed > 0:  # fcg-rewrite
            logger.info(f"Cleaned up {removed} old login attempts older than {days_to_keep} days")  # fcg-rewrite
        return removed  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.error(f"Failed to cleanup old login attempts: {exc}")  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        return 0  # fcg-rewrite


def clear_login_window(  # fcg-rewrite
    db: Session,  # fcg-rewrite
    email: str = None,  # fcg-rewrite
    ip_address: str = None,  # fcg-rewrite
    time_window_minutes: int = 15,  # fcg-rewrite
) -> int:  # fcg-rewrite
    """Clear recent failed login attempts for emergency unblocking."""
    from database.models import LoginAttempt  # fcg-rewrite

    cutoff = datetime.utcnow() - timedelta(minutes=time_window_minutes)  # fcg-rewrite

    try:
        query = db.query(LoginAttempt).filter(  # fcg-rewrite
            LoginAttempt.attempted_at >= cutoff,  # fcg-rewrite
            LoginAttempt.success == False  # fcg-rewrite
        )
        if email:  # fcg-rewrite
            query = query.filter(LoginAttempt.email == email)  # fcg-rewrite
        if ip_address:  # fcg-rewrite
            query = query.filter(LoginAttempt.ip_address == ip_address)  # fcg-rewrite

        removed = query.delete()  # fcg-rewrite
        db.commit()  # fcg-rewrite
        logger.info(f"Emergency cleared {removed} failed login attempts for email={email}, ip={ip_address}")  # fcg-rewrite
        return removed  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.error(f"Failed to emergency clear rate limit: {exc}")  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        return 0  # fcg-rewrite


def ensure_app_for_external_id(  # fcg-rewrite
    db: Session,  # fcg-rewrite
    tenant_id: Union[str, uuid.UUID],  # fcg-rewrite
    external_id: str,  # fcg-rewrite
) -> Optional[dict]:  # fcg-rewrite
    """Find or create an auto-discovered application for an external gateway id."""
    tenant_uuid = _resolve_tenant_uuid(tenant_id)  # fcg-rewrite
    if tenant_uuid is None:  # fcg-rewrite
        logger.error(f"Invalid tenant_id format: {tenant_id}")  # fcg-rewrite
        return None  # fcg-rewrite

    app = db.query(Application).filter(  # fcg-rewrite
        Application.tenant_id == tenant_uuid,  # fcg-rewrite
        Application.external_id == external_id,  # fcg-rewrite
        Application.is_active == True  # fcg-rewrite
    ).first()  # fcg-rewrite
    if app:
        logger.debug(f"Found existing application for external_id '{external_id}': app_id={app.id}")  # fcg-rewrite
        return {  # fcg-rewrite
            "application_id": str(app.id),  # fcg-rewrite
            "application_name": app.name,  # fcg-rewrite
            "is_new": False,  # fcg-rewrite
        }

    try:
        app = Application(  # fcg-rewrite
            tenant_id=tenant_uuid,  # fcg-rewrite
            name=external_id,  # fcg-rewrite
            description=f"Auto-discovered from gateway: {external_id}",  # fcg-rewrite
            external_id=external_id,  # fcg-rewrite
            source='auto_discovery',  # fcg-rewrite
            is_active=True,  # fcg-rewrite
        )
        db.add(app)  # fcg-rewrite
        db.flush()  # fcg-rewrite

        try:
            from admin_console.routes.application_workspace_routes import initialize_application_configs  # fcg-rewrite

            initialize_application_configs(db, str(app.id), str(tenant_uuid))  # fcg-rewrite
            logger.info(f"Initialized configs for auto-discovered application '{external_id}'")  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.warning(f"Failed to initialize configs for auto-discovered app '{external_id}': {exc}")  # fcg-rewrite

        db.commit()  # fcg-rewrite
        logger.info(f"Auto-created application '{external_id}' for tenant {tenant_uuid}: app_id={app.id}")  # fcg-rewrite
        return {  # fcg-rewrite
            "application_id": str(app.id),  # fcg-rewrite
            "application_name": app.name,  # fcg-rewrite
            "is_new": True,  # fcg-rewrite
        }
    except Exception as exc:  # fcg-rewrite
        logger.error(f"Failed to auto-create application for external_id '{external_id}': {exc}")  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        return None  # fcg-rewrite
