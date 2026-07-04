"""Shared request-to-tenant/application resolution helpers."""

from dataclasses import dataclass  # fcg-rewrite
import uuid  # fcg-rewrite

from fastapi import HTTPException, Request  # fcg-rewrite

from database.models import Application, Tenant  # fcg-rewrite
from services.admin_service import admin_service  # fcg-rewrite
from utils.auth import verify_token  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite


logger = setup_logger()  # fcg-rewrite


@dataclass(frozen=True)  # fcg-rewrite
class ApplicationRequestContext:  # fcg-rewrite
    """Resolved tenant/application scope for a request."""

    tenant: Tenant  # fcg-rewrite
    application_id: uuid.UUID  # fcg-rewrite


def resolve_admin_application_context(request: Request, db) -> ApplicationRequestContext:  # fcg-rewrite
    """Resolve tenant/application scope for management-style routes."""
    header_context = _resolve_header_application_context(request, db)  # fcg-rewrite
    if header_context is not None:  # fcg-rewrite
        return header_context  # fcg-rewrite

    switch_context = _resolve_switched_application_context(request, db)  # fcg-rewrite
    if switch_context is not None:  # fcg-rewrite
        return switch_context  # fcg-rewrite

    auth_context = getattr(request.state, "auth_context", None)  # fcg-rewrite
    if not auth_context or "data" not in auth_context:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite

    data = auth_context["data"]  # fcg-rewrite
    app_context = _resolve_application_from_auth_data(data, db)  # fcg-rewrite
    if app_context is not None:  # fcg-rewrite
        return app_context  # fcg-rewrite

    tenant = _resolve_tenant_from_management_request(request, db, data)  # fcg-rewrite
    default_app = _load_default_application(db, tenant.id)  # fcg-rewrite
    if default_app is None:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="No active application found for user")  # fcg-rewrite

    return ApplicationRequestContext(tenant=tenant, application_id=default_app.id)  # fcg-rewrite


def resolve_tenant_application_context(request: Request, db) -> ApplicationRequestContext:  # fcg-rewrite
    """Resolve tenant/application scope constrained to the authenticated tenant."""
    auth_context = getattr(request.state, "auth_context", None)  # fcg-rewrite
    if not auth_context or "data" not in auth_context:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite

    data = auth_context["data"]  # fcg-rewrite
    tenant_id = data.get("tenant_id")  # fcg-rewrite
    if not tenant_id:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Tenant ID not found in auth context")  # fcg-rewrite

    try:
        tenant_uuid = uuid.UUID(str(tenant_id))  # fcg-rewrite
    except ValueError:  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")  # fcg-rewrite

    tenant = db.query(Tenant).filter(Tenant.id == tenant_uuid).first()  # fcg-rewrite
    if not tenant:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Tenant not found")  # fcg-rewrite

    header_app_id = request.headers.get("x-application-id") or request.headers.get("X-Application-ID")  # fcg-rewrite
    if header_app_id:  # fcg-rewrite
        try:
            application_uuid = uuid.UUID(str(header_app_id))  # fcg-rewrite
        except (ValueError, AttributeError):  # fcg-rewrite
            application_uuid = None  # fcg-rewrite
        if application_uuid is not None:  # fcg-rewrite
            app = _load_application_for_tenant(db, application_uuid, tenant.id)  # fcg-rewrite
            if app is not None:  # fcg-rewrite
                return ApplicationRequestContext(tenant=tenant, application_id=application_uuid)  # fcg-rewrite

    application_id_value = data.get("application_id")  # fcg-rewrite
    if application_id_value:  # fcg-rewrite
        try:
            application_uuid = uuid.UUID(str(application_id_value))  # fcg-rewrite
        except (ValueError, AttributeError):  # fcg-rewrite
            application_uuid = None  # fcg-rewrite
        if application_uuid is not None:  # fcg-rewrite
            app = _load_application_for_tenant(db, application_uuid, tenant.id)  # fcg-rewrite
            if app is not None:  # fcg-rewrite
                return ApplicationRequestContext(tenant=tenant, application_id=application_uuid)  # fcg-rewrite

    default_app = _load_default_application(db, tenant.id)  # fcg-rewrite
    if default_app is None:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="No active application found for user")  # fcg-rewrite

    return ApplicationRequestContext(tenant=tenant, application_id=default_app.id)  # fcg-rewrite


def _resolve_header_application_context(request: Request, db):  # fcg-rewrite
    header_app_id = request.headers.get("x-application-id") or request.headers.get("X-Application-ID")  # fcg-rewrite
    if not header_app_id:  # fcg-rewrite
        return None  # fcg-rewrite

    try:
        header_app_uuid = uuid.UUID(str(header_app_id))  # fcg-rewrite
    except (ValueError, AttributeError):  # fcg-rewrite
        return None  # fcg-rewrite

    app = (
        db.query(Application)  # fcg-rewrite
        .filter(Application.id == header_app_uuid, Application.is_active == True)  # fcg-rewrite
        .first()  # fcg-rewrite
    )
    if app is None:  # fcg-rewrite
        return None  # fcg-rewrite

    tenant = db.query(Tenant).filter(Tenant.id == app.tenant_id).first()  # fcg-rewrite
    if tenant is None:  # fcg-rewrite
        return None  # fcg-rewrite

    return ApplicationRequestContext(tenant=tenant, application_id=header_app_uuid)  # fcg-rewrite


def _resolve_switched_application_context(request: Request, db):  # fcg-rewrite
    switch_token = request.headers.get("x-switch-session")  # fcg-rewrite
    if not switch_token:  # fcg-rewrite
        return None  # fcg-rewrite

    switched_tenant = admin_service.resolve_assumed_user(db, switch_token)  # fcg-rewrite
    if switched_tenant is None:  # fcg-rewrite
        return None  # fcg-rewrite

    default_app = _load_default_application(db, switched_tenant.id)  # fcg-rewrite
    if default_app is None:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="No active application found for switched user")  # fcg-rewrite

    return ApplicationRequestContext(tenant=switched_tenant, application_id=default_app.id)  # fcg-rewrite


def _resolve_application_from_auth_data(data, db):  # fcg-rewrite
    application_id_value = data.get("application_id")  # fcg-rewrite
    if not application_id_value:  # fcg-rewrite
        return None  # fcg-rewrite

    try:
        application_uuid = uuid.UUID(str(application_id_value))  # fcg-rewrite
    except (ValueError, AttributeError):  # fcg-rewrite
        return None  # fcg-rewrite

    app = (
        db.query(Application)  # fcg-rewrite
        .filter(Application.id == application_uuid, Application.is_active == True)  # fcg-rewrite
        .first()  # fcg-rewrite
    )
    if app is None:  # fcg-rewrite
        return None  # fcg-rewrite

    tenant = db.query(Tenant).filter(Tenant.id == app.tenant_id).first()  # fcg-rewrite
    if tenant is None:  # fcg-rewrite
        return None  # fcg-rewrite

    return ApplicationRequestContext(tenant=tenant, application_id=application_uuid)  # fcg-rewrite


def _resolve_tenant_from_management_request(request: Request, db, data):  # fcg-rewrite
    tenant = _load_tenant_from_auth_data(db, data)  # fcg-rewrite
    if tenant is not None:  # fcg-rewrite
        return tenant  # fcg-rewrite

    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")  # fcg-rewrite
    if auth_header and auth_header.startswith("Bearer "):  # fcg-rewrite
        token = auth_header.split(" ", 1)[1]  # fcg-rewrite
        tenant = _load_tenant_from_jwt(db, token)  # fcg-rewrite
        if tenant is not None:  # fcg-rewrite
            return tenant  # fcg-rewrite

    raise HTTPException(status_code=401, detail="User not found or invalid context")  # fcg-rewrite


def _load_tenant_from_auth_data(db, data):  # fcg-rewrite
    tenant_id_value = data.get("tenant_id")  # fcg-rewrite
    tenant_email_value = data.get("email")  # fcg-rewrite

    tenant = None  # fcg-rewrite
    if tenant_id_value:  # fcg-rewrite
        try:
            tenant_uuid = uuid.UUID(str(tenant_id_value))  # fcg-rewrite
            tenant = db.query(Tenant).filter(Tenant.id == tenant_uuid).first()  # fcg-rewrite
        except ValueError:  # fcg-rewrite
            tenant = None  # fcg-rewrite

    if tenant is None and tenant_email_value:  # fcg-rewrite
        tenant = db.query(Tenant).filter(Tenant.email == tenant_email_value).first()  # fcg-rewrite

    return tenant  # fcg-rewrite


def _load_tenant_from_jwt(db, token: str):  # fcg-rewrite
    try:
        payload = verify_token(token)  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.debug("JWT tenant fallback failed: %s", exc)  # fcg-rewrite
        return None  # fcg-rewrite

    raw_tenant_id = payload.get("tenant_id") or payload.get("sub")  # fcg-rewrite
    if raw_tenant_id:  # fcg-rewrite
        try:
            tenant_uuid = uuid.UUID(str(raw_tenant_id))  # fcg-rewrite
            tenant = db.query(Tenant).filter(Tenant.id == tenant_uuid).first()  # fcg-rewrite
            if tenant is not None:  # fcg-rewrite
                return tenant  # fcg-rewrite
        except ValueError:  # fcg-rewrite
            pass

    email_claim = payload.get("email") or payload.get("username")  # fcg-rewrite
    if email_claim:  # fcg-rewrite
        return db.query(Tenant).filter(Tenant.email == email_claim).first()  # fcg-rewrite
    return None  # fcg-rewrite


def _load_default_application(db, tenant_id):  # fcg-rewrite
    return (  # fcg-rewrite
        db.query(Application)  # fcg-rewrite
        .filter(Application.tenant_id == tenant_id, Application.is_active == True)  # fcg-rewrite
        .order_by(Application.created_at.asc())  # fcg-rewrite
        .first()  # fcg-rewrite
    )


def _load_application_for_tenant(db, application_id, tenant_id):  # fcg-rewrite
    return (  # fcg-rewrite
        db.query(Application)  # fcg-rewrite
        .filter(  # fcg-rewrite
            Application.id == application_id,  # fcg-rewrite
            Application.tenant_id == tenant_id,  # fcg-rewrite
            Application.is_active == True,  # fcg-rewrite
        )
        .first()  # fcg-rewrite
    )
