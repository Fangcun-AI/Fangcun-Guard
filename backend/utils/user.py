from datetime import datetime, timedelta
import secrets
import string
import uuid
from typing import Optional, Union

from sqlalchemy.orm import Session

from database.models import ApiKey, Application, EmailVerification, Tenant
from utils.auth import get_password_hash
from utils.logger import setup_logger

logger = setup_logger()

API_KEY_PREFIX = "sk-xxai-"
API_KEY_LENGTH = 64


def _tenant_uuid(value: Union[str, uuid.UUID]) -> Optional[uuid.UUID]:
    """Coerce tenant ids into UUID instances."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        return None


def new_api_key() -> str:
    """Create a tenant or application API key."""
    alphabet = string.ascii_letters + string.digits
    token_len = API_KEY_LENGTH - len(API_KEY_PREFIX)
    token = ''.join(secrets.choice(alphabet) for _ in range(token_len))
    return f"{API_KEY_PREFIX}{token}"


def find_user_by_email(db: Session, email: str) -> Optional[Tenant]:
    """Return a tenant by email."""
    return db.query(Tenant).filter(Tenant.email == email).first()


def find_tenant_by_key(db: Session, api_key: str) -> Optional[Tenant]:
    """
    Return a verified tenant for a legacy tenant API key.

    This only checks ``tenants.api_key`` and is kept for backward compatibility.
    """
    return db.query(Tenant).filter(
        Tenant.api_key == api_key,
        Tenant.is_verified == True,
        Tenant.is_active == True
    ).first()


def find_app_by_key(db: Session, api_key: str) -> Optional[dict]:
    """Return application and tenant details for an application API key."""
    row = db.query(ApiKey, Application, Tenant).join(
        Application, ApiKey.application_id == Application.id
    ).join(
        Tenant, ApiKey.tenant_id == Tenant.id
    ).filter(
        ApiKey.key == api_key,
        ApiKey.is_active == True,
        Application.is_active == True,
        Tenant.is_verified == True,
        Tenant.is_active == True
    ).first()

    if not row:
        return None

    key_row, app, tenant = row

    try:
        key_row.last_used_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        logger.warning(f"Failed to update API key last_used_at: {exc}")
        db.rollback()

    return {
        "tenant_id": str(tenant.id),
        "tenant_email": tenant.email,
        "application_id": str(app.id),
        "application_name": app.name,
        "api_key_id": str(key_row.id),
        "api_key": api_key,
    }


def add_user(db: Session, email: str, password: str) -> Tenant:
    """Create a new tenant."""
    from utils.validators import validate_password_strength

    password_check = validate_password_strength(password)
    if not password_check["is_valid"]:
        issues = ", ".join(password_check["errors"])
        raise ValueError(f"Password does not meet security requirements: {issues}")

    password_hash = get_password_hash(password)
    api_key = new_api_key()

    while db.query(Tenant).filter(Tenant.api_key == api_key).first():
        api_key = new_api_key()

    tenant = Tenant(
        email=email,
        password_hash=password_hash,
        api_key=api_key,
        is_active=False,
        is_verified=False,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def add_default_app_key(
    db: Session,
    tenant_id: Union[str, uuid.UUID],
    tenant_email: str,
) -> Optional[dict]:
    """Create the default application and application key for a tenant."""
    tenant_uuid = _tenant_uuid(tenant_id)
    if tenant_uuid is None:
        logger.error(f"Failed to create default application for tenant {tenant_email}: invalid tenant id")
        return None

    try:
        app = Application(
            tenant_id=tenant_uuid,
            name="Default Application",
            description="Default application created automatically",
            is_active=True,
            source='manual',
        )
        db.add(app)
        db.flush()

        api_key = new_api_key()
        while db.query(ApiKey).filter(ApiKey.key == api_key).first():
            api_key = new_api_key()

        app_key = ApiKey(
            tenant_id=tenant_uuid,
            application_id=app.id,
            key=api_key,
            name="Default API Key",
            is_active=True,
        )
        db.add(app_key)
        db.flush()

        try:
            from routers.applications import initialize_application_configs

            initialize_application_configs(db, str(app.id), str(tenant_uuid))
            logger.info(f"Created default application '{app.name}' with API key for tenant {tenant_email}")
        except Exception as exc:
            logger.error(f"Failed to initialize configs for default application: {exc}")

        db.commit()
        return {
            "application_id": str(app.id),
            "application_name": app.name,
            "api_key": api_key,
        }
    except Exception as exc:
        logger.error(f"Failed to create default application for tenant {tenant_email}: {exc}")
        db.rollback()
        return None


def _bootstrap_verified_user(db: Session, tenant: Tenant) -> None:
    """Create the default resources for a newly verified tenant."""
    try:
        app_data = add_default_app_key(db, tenant.id, tenant.email)
        if app_data:
            logger.info(f"Created default application for tenant {tenant.email}: app_id={app_data['application_id']}")
        else:
            logger.warning(f"Failed to create default application for tenant {tenant.email}")
    except Exception as exc:
        logger.error(f"Error creating default application for tenant {tenant.email}: {exc}")

    try:
        from services.template_service import create_user_default_templates

        template_count = create_user_default_templates(db, tenant.id)
        print(f"Created {template_count} default reply templates for tenant {tenant.email}")
    except Exception as exc:
        print(f"Failed to create default reply templates for tenant {tenant.email}: {exc}")

    try:
        from services.data_security_service import create_user_default_entity_types

        entity_count = create_user_default_entity_types(db, str(tenant.id))
        print(f"Created {entity_count} default entity type configurations for tenant {tenant.email}")
    except Exception as exc:
        print(f"Failed to create default entity type configurations for tenant {tenant.email}: {exc}")

    try:
        from services.billing_service import billing_service

        billing_service.create_subscription(str(tenant.id), 'free', db)
        print(f"Created free subscription for tenant {tenant.email}")
    except Exception as exc:
        print(f"Failed to create subscription for tenant {tenant.email}: {exc}")

    try:
        from config import settings
        from services.rate_limiter import RateLimitService

        rate_limit_service = RateLimitService(db)
        default_rps = settings.default_rate_limit_rps
        rate_limit_service.set_user_rate_limit(str(tenant.id), default_rps)
        print(f"Created rate limit ({default_rps} RPS) for tenant {tenant.email}")
    except Exception as exc:
        print(f"Failed to create rate limit for tenant {tenant.email}: {exc}")


def confirm_user_email(db: Session, email: str, verification_code: str) -> bool:
    """Verify a tenant email and bootstrap the tenant defaults."""
    verification = db.query(EmailVerification).filter(
        EmailVerification.email == email,
        EmailVerification.verification_code == verification_code,
        EmailVerification.is_used == False,
        EmailVerification.expires_at > datetime.utcnow()
    ).first()

    if not verification:
        return False

    verification.is_used = True
    tenant = db.query(Tenant).filter(Tenant.email == email).first()
    if tenant:
        tenant.is_active = True
        tenant.is_verified = True

    db.commit()

    if tenant:
        _bootstrap_verified_user(db, tenant)

    return True


def rotate_api_key(db: Session, tenant_id: Union[str, uuid.UUID]) -> Optional[str]:
    """Regenerate the legacy tenant API key."""
    tenant_uuid = _tenant_uuid(tenant_id)
    if tenant_uuid is None:
        return None

    tenant = db.query(Tenant).filter(Tenant.id == tenant_uuid).first()
    if not tenant:
        return None

    api_key = new_api_key()
    while db.query(Tenant).filter(Tenant.api_key == api_key).first():
        api_key = new_api_key()

    tenant.api_key = api_key
    db.commit()
    db.refresh(tenant)
    return api_key


def save_login_attempt(
    db: Session,
    email: str,
    ip_address: str,
    user_agent: str,
    success: bool,
) -> None:
    """Persist a login attempt."""
    from database.models import LoginAttempt

    attempt = LoginAttempt(
        email=email,
        ip_address=ip_address,
        user_agent=user_agent or "",
        success=success,
    )
    db.add(attempt)
    db.commit()


def login_rate_ok(
    db: Session,
    email: str,
    ip_address: str,
    time_window_minutes: int = 15,
    max_attempts: int = 5,
) -> bool:
    """Return whether the login failure count is below the configured limit."""
    from database.models import LoginAttempt

    cutoff = datetime.utcnow() - timedelta(minutes=time_window_minutes)
    email_failures = db.query(LoginAttempt).filter(
        LoginAttempt.email == email,
        LoginAttempt.success == False,
        LoginAttempt.attempted_at >= cutoff
    ).count()
    return email_failures < max_attempts


def prune_login_attempts(db: Session, days_to_keep: int = 30) -> int:
    """Delete old login-attempt records."""
    from database.models import LoginAttempt

    cutoff = datetime.utcnow() - timedelta(days=days_to_keep)

    try:
        removed = db.query(LoginAttempt).filter(
            LoginAttempt.attempted_at < cutoff
        ).delete()
        db.commit()
        if removed > 0:
            logger.info(f"Cleaned up {removed} old login attempts older than {days_to_keep} days")
        return removed
    except Exception as exc:
        logger.error(f"Failed to cleanup old login attempts: {exc}")
        db.rollback()
        return 0


def clear_login_window(
    db: Session,
    email: str = None,
    ip_address: str = None,
    time_window_minutes: int = 15,
) -> int:
    """Clear recent failed login attempts for emergency unblocking."""
    from database.models import LoginAttempt

    cutoff = datetime.utcnow() - timedelta(minutes=time_window_minutes)

    try:
        query = db.query(LoginAttempt).filter(
            LoginAttempt.attempted_at >= cutoff,
            LoginAttempt.success == False
        )
        if email:
            query = query.filter(LoginAttempt.email == email)
        if ip_address:
            query = query.filter(LoginAttempt.ip_address == ip_address)

        removed = query.delete()
        db.commit()
        logger.info(f"Emergency cleared {removed} failed login attempts for email={email}, ip={ip_address}")
        return removed
    except Exception as exc:
        logger.error(f"Failed to emergency clear rate limit: {exc}")
        db.rollback()
        return 0


def ensure_app_for_external_id(
    db: Session,
    tenant_id: Union[str, uuid.UUID],
    external_id: str,
) -> Optional[dict]:
    """Find or create an auto-discovered application for an external gateway id."""
    tenant_uuid = _tenant_uuid(tenant_id)
    if tenant_uuid is None:
        logger.error(f"Invalid tenant_id format: {tenant_id}")
        return None

    app = db.query(Application).filter(
        Application.tenant_id == tenant_uuid,
        Application.external_id == external_id,
        Application.is_active == True
    ).first()
    if app:
        logger.debug(f"Found existing application for external_id '{external_id}': app_id={app.id}")
        return {
            "application_id": str(app.id),
            "application_name": app.name,
            "is_new": False,
        }

    try:
        app = Application(
            tenant_id=tenant_uuid,
            name=external_id,
            description=f"Auto-discovered from gateway: {external_id}",
            external_id=external_id,
            source='auto_discovery',
            is_active=True,
        )
        db.add(app)
        db.flush()

        try:
            from routers.applications import initialize_application_configs

            initialize_application_configs(db, str(app.id), str(tenant_uuid))
            logger.info(f"Initialized configs for auto-discovered application '{external_id}'")
        except Exception as exc:
            logger.warning(f"Failed to initialize configs for auto-discovered app '{external_id}': {exc}")

        db.commit()
        logger.info(f"Auto-created application '{external_id}' for tenant {tenant_uuid}: app_id={app.id}")
        return {
            "application_id": str(app.id),
            "application_name": app.name,
            "is_new": True,
        }
    except Exception as exc:
        logger.error(f"Failed to auto-create application for external_id '{external_id}': {exc}")
        db.rollback()
        return None
