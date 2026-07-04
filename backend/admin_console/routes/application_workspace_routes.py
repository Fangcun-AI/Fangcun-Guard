"""Tenant application workspaces and application-scoped API keys."""

from datetime import datetime  # fcg-rewrite
from typing import Any, Dict, List, Optional  # fcg-rewrite
import secrets  # fcg-rewrite
import string  # fcg-rewrite
import uuid  # fcg-rewrite

from fastapi import APIRouter, Depends, HTTPException, Request  # fcg-rewrite
from pydantic import BaseModel  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.connection import get_admin_db  # fcg-rewrite
from database.models import (  # fcg-rewrite
    ApiKey,
    Application,  # fcg-rewrite
    ApplicationScannerConfig,  # fcg-rewrite
    BanPolicy,  # fcg-rewrite
    Blacklist,  # fcg-rewrite
    DataSecurityEntityType,  # fcg-rewrite
    KnowledgeBase,  # fcg-rewrite
    RiskTypeConfig,  # fcg-rewrite
    Whitelist,  # fcg-rewrite
)
from services.scanner_config_service import ScannerConfigService  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Applications"])  # fcg-rewrite


def get_current_tenant_id(request: Request) -> str:  # fcg-rewrite
    context = getattr(request.state, "auth_context", None)  # fcg-rewrite
    tenant_id = context.get("data", {}).get("tenant_id") if isinstance(context, dict) else None  # fcg-rewrite
    if not tenant_id:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Not authenticated" if not context else "Tenant ID not found in auth context")  # fcg-rewrite
    return str(tenant_id)  # fcg-rewrite


class ApplicationCreate(BaseModel):  # fcg-rewrite
    name: str  # fcg-rewrite
    description: Optional[str] = None  # fcg-rewrite


class ApplicationUpdate(BaseModel):  # fcg-rewrite
    name: Optional[str] = None  # fcg-rewrite
    description: Optional[str] = None  # fcg-rewrite
    is_active: Optional[bool] = None  # fcg-rewrite


class ApplicationResponse(BaseModel):  # fcg-rewrite
    id: str
    tenant_id: str  # fcg-rewrite
    name: str  # fcg-rewrite
    description: Optional[str]  # fcg-rewrite
    is_active: bool  # fcg-rewrite
    source: str = "manual"  # fcg-rewrite
    external_id: Optional[str] = None  # fcg-rewrite
    created_at: datetime  # fcg-rewrite
    updated_at: datetime  # fcg-rewrite
    api_keys_count: int = 0  # fcg-rewrite
    protection_summary: Optional[Dict[str, Any]] = None  # fcg-rewrite


class ApiKeyCreate(BaseModel):  # fcg-rewrite
    application_id: str  # fcg-rewrite
    name: Optional[str] = None  # fcg-rewrite


class ApiKeyResponse(BaseModel):  # fcg-rewrite
    id: str
    application_id: str  # fcg-rewrite
    key: str  # fcg-rewrite
    name: Optional[str]  # fcg-rewrite
    is_active: bool  # fcg-rewrite
    last_used_at: Optional[datetime]  # fcg-rewrite
    created_at: datetime  # fcg-rewrite


def generate_api_key() -> str:  # fcg-rewrite
    alphabet = string.ascii_letters + string.digits  # fcg-rewrite
    return "sk-xxai-" + "".join(secrets.choice(alphabet) for _ in range(56))  # fcg-rewrite


def _application(db: Session, app_id: str, tenant_id: str) -> Application:  # fcg-rewrite
    app = db.query(Application).filter(Application.id == app_id, Application.tenant_id == tenant_id).first()  # fcg-rewrite
    if not app:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Application not found")  # fcg-rewrite
    return app  # fcg-rewrite


def _api_key(db: Session, app_id: str, key_id: str, tenant_id: str) -> ApiKey:  # fcg-rewrite
    key = db.query(ApiKey).join(Application).filter(  # fcg-rewrite
        ApiKey.id == key_id, ApiKey.application_id == app_id, Application.tenant_id == tenant_id  # fcg-rewrite
    ).first()  # fcg-rewrite
    if not key:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="API key not found")  # fcg-rewrite
    return key  # fcg-rewrite


def _key_response(key: ApiKey) -> ApiKeyResponse:  # fcg-rewrite
    return ApiKeyResponse(  # fcg-rewrite
        id=str(key.id),  # fcg-rewrite
        application_id=str(key.application_id),  # fcg-rewrite
        key=key.key,  # fcg-rewrite
        name=key.name,  # fcg-rewrite
        is_active=key.is_active,  # fcg-rewrite
        last_used_at=key.last_used_at,  # fcg-rewrite
        created_at=key.created_at,  # fcg-rewrite
    )


def _summary(db: Session, app: Application) -> dict:  # fcg-rewrite
    def active_count(model):  # fcg-rewrite
        return db.query(model).filter(model.application_id == app.id, model.is_active == True).count()  # fcg-rewrite

    scanner_query = db.query(ApplicationScannerConfig).filter(ApplicationScannerConfig.application_id == app.id)  # fcg-rewrite
    risk = db.query(RiskTypeConfig).filter(RiskTypeConfig.application_id == app.id).first()  # fcg-rewrite
    ban = db.query(BanPolicy).filter(BanPolicy.application_id == app.id).first()  # fcg-rewrite
    return {  # fcg-rewrite
        "risk_types_enabled": scanner_query.filter(ApplicationScannerConfig.is_enabled == True).count(),  # fcg-rewrite
        "total_risk_types": scanner_query.count(),  # fcg-rewrite
        "ban_policy_enabled": ban.enabled if ban else False,  # fcg-rewrite
        "sensitivity_level": risk.sensitivity_trigger_level if risk else "medium",  # fcg-rewrite
        "data_security_entities": active_count(DataSecurityEntityType),  # fcg-rewrite
        "blacklist_count": active_count(Blacklist),  # fcg-rewrite
        "whitelist_count": active_count(Whitelist),  # fcg-rewrite
        "knowledge_base_count": active_count(KnowledgeBase),  # fcg-rewrite
    }


def _application_response(db: Session, app: Application, include_summary: bool = False) -> ApplicationResponse:  # fcg-rewrite
    return ApplicationResponse(  # fcg-rewrite
        id=str(app.id),  # fcg-rewrite
        tenant_id=str(app.tenant_id),  # fcg-rewrite
        name=app.name,  # fcg-rewrite
        description=app.description,  # fcg-rewrite
        is_active=app.is_active,  # fcg-rewrite
        source=getattr(app, "source", "manual") or "manual",  # fcg-rewrite
        external_id=getattr(app, "external_id", None),  # fcg-rewrite
        created_at=app.created_at,  # fcg-rewrite
        updated_at=app.updated_at,  # fcg-rewrite
        api_keys_count=db.query(ApiKey).filter(ApiKey.application_id == app.id).count(),  # fcg-rewrite
        protection_summary=_summary(db, app) if include_summary else None,  # fcg-rewrite
    )


def initialize_application_configs(db: Session, application_id: str, tenant_id: str):  # fcg-rewrite
    """Seed defaults for a newly created application."""
    try:
        if not db.query(RiskTypeConfig).filter(RiskTypeConfig.application_id == application_id).first():  # fcg-rewrite
            db.add(RiskTypeConfig(  # fcg-rewrite
                application_id=application_id,  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                **{f"s{number}_enabled": True for number in range(1, 22)},  # fcg-rewrite
                low_sensitivity_threshold=0.95,  # fcg-rewrite
                medium_sensitivity_threshold=0.60,  # fcg-rewrite
                high_sensitivity_threshold=0.40,  # fcg-rewrite
                sensitivity_trigger_level="medium",  # fcg-rewrite
            ))
        if not db.query(BanPolicy).filter(BanPolicy.application_id == application_id).first():  # fcg-rewrite
            db.add(BanPolicy(  # fcg-rewrite
                application_id=application_id,  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                enabled=False,  # fcg-rewrite
                risk_level="high_risk",  # fcg-rewrite
                trigger_count=3,  # fcg-rewrite
                time_window_minutes=10,  # fcg-rewrite
                ban_duration_minutes=1440,  # fcg-rewrite
            ))
        if not db.query(DataSecurityEntityType).filter(DataSecurityEntityType.application_id == application_id).count():  # fcg-rewrite
            templates = db.query(DataSecurityEntityType).filter(  # fcg-rewrite
                DataSecurityEntityType.source_type == "system_template",  # fcg-rewrite
                DataSecurityEntityType.application_id.is_(None),  # fcg-rewrite
            ).all()
            for template in templates:  # fcg-rewrite
                db.add(DataSecurityEntityType(  # fcg-rewrite
                    tenant_id=tenant_id,  # fcg-rewrite
                    application_id=application_id,  # fcg-rewrite
                    entity_type=template.entity_type,  # fcg-rewrite
                    entity_type_name=template.entity_type_name,  # fcg-rewrite
                    category=template.category,  # fcg-rewrite
                    recognition_method=template.recognition_method,  # fcg-rewrite
                    recognition_config=dict(template.recognition_config or {}),  # fcg-rewrite
                    anonymization_method=template.anonymization_method,  # fcg-rewrite
                    anonymization_config=dict(template.anonymization_config or {}),  # fcg-rewrite
                    is_active=True,  # fcg-rewrite
                    is_global=False,  # fcg-rewrite
                    source_type="system_copy",  # fcg-rewrite
                    template_id=template.id,  # fcg-rewrite
                ))
        try:
            ScannerConfigService(db).initialize_default_configs(  # fcg-rewrite
                application_id=uuid.UUID(application_id), tenant_id=uuid.UUID(tenant_id)  # fcg-rewrite
            )
        except Exception as exc:  # fcg-rewrite
            logger.error("Scanner config initialization failed for %s: %s", application_id, exc)  # fcg-rewrite
        db.commit()  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        if "ix_risk_type_config_user_id" in str(exc) or "tenant_id" in str(exc).lower():  # fcg-rewrite
            raise ValueError(  # fcg-rewrite
                "Database constraint error: A unique constraint on tenant_id is preventing multiple applications. "  # fcg-rewrite
                "This indicates a migration issue. Please run migration 014 to fix this: "  # fcg-rewrite
                "'014_force_remove_tenant_id_unique_constraints.sql'"  # fcg-rewrite
            ) from exc  # fcg-rewrite
        raise


@router.get("", response_model=List[ApplicationResponse])  # fcg-rewrite
async def list_applications(  # fcg-rewrite
    request: Request, db: Session = Depends(get_admin_db), include_summary: bool = True  # fcg-rewrite
):
    tenant_id = get_current_tenant_id(request)  # fcg-rewrite
    apps = db.query(Application).filter(Application.tenant_id == tenant_id).all()  # fcg-rewrite
    return [_application_response(db, app, include_summary) for app in apps]  # fcg-rewrite


@router.post("", response_model=ApplicationResponse)  # fcg-rewrite
async def create_application(  # fcg-rewrite
    data: ApplicationCreate, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    tenant_id = get_current_tenant_id(request)  # fcg-rewrite
    if db.query(Application).filter(Application.tenant_id == tenant_id, Application.name == data.name).first():  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Application name already exists")  # fcg-rewrite
    app = Application(tenant_id=tenant_id, name=data.name, description=data.description, is_active=True, source="manual")  # fcg-rewrite
    db.add(app)  # fcg-rewrite
    db.commit()  # fcg-rewrite
    db.refresh(app)  # fcg-rewrite
    try:
        initialize_application_configs(db, str(app.id), tenant_id)  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        db.delete(app)  # fcg-rewrite
        db.commit()  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Failed to initialize application configurations: {exc}") from exc  # fcg-rewrite
    return _application_response(db, app)  # fcg-rewrite


@router.put("/{app_id}", response_model=ApplicationResponse)  # fcg-rewrite
async def update_application(  # fcg-rewrite
    app_id: str, data: ApplicationUpdate, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    app = _application(db, app_id, get_current_tenant_id(request))  # fcg-rewrite
    for field, value in data.model_dump(exclude_unset=True).items():  # fcg-rewrite
        setattr(app, field, value)  # fcg-rewrite
    db.commit()  # fcg-rewrite
    db.refresh(app)  # fcg-rewrite
    return _application_response(db, app)  # fcg-rewrite


@router.delete("/{app_id}")  # fcg-rewrite
async def delete_application(app_id: str, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant_id = get_current_tenant_id(request)  # fcg-rewrite
    app = _application(db, app_id, tenant_id)  # fcg-rewrite
    if db.query(Application).filter(Application.tenant_id == tenant_id).count() <= 1:  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Cannot delete the last application")  # fcg-rewrite
    db.delete(app)  # fcg-rewrite
    db.commit()  # fcg-rewrite
    return {"message": "Application deleted successfully"}  # fcg-rewrite


@router.get("/{app_id}/keys", response_model=List[ApiKeyResponse])  # fcg-rewrite
async def list_api_keys(app_id: str, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    _application(db, app_id, get_current_tenant_id(request))  # fcg-rewrite
    return [_key_response(key) for key in db.query(ApiKey).filter(ApiKey.application_id == app_id).all()]  # fcg-rewrite


@router.post("/{app_id}/keys", response_model=ApiKeyResponse)  # fcg-rewrite
async def create_api_key(  # fcg-rewrite
    app_id: str, data: ApiKeyCreate, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    tenant_id = get_current_tenant_id(request)  # fcg-rewrite
    _application(db, app_id, tenant_id)  # fcg-rewrite
    value = generate_api_key()  # fcg-rewrite
    while db.query(ApiKey).filter(ApiKey.key == value).first():  # fcg-rewrite
        value = generate_api_key()  # fcg-rewrite
    key = ApiKey(tenant_id=tenant_id, application_id=app_id, key=value, name=data.name, is_active=True)  # fcg-rewrite
    db.add(key)  # fcg-rewrite
    db.commit()  # fcg-rewrite
    db.refresh(key)  # fcg-rewrite
    return _key_response(key)  # fcg-rewrite


@router.delete("/{app_id}/keys/{key_id}")  # fcg-rewrite
async def delete_api_key(app_id: str, key_id: str, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    key = _api_key(db, app_id, key_id, get_current_tenant_id(request))  # fcg-rewrite
    db.delete(key)  # fcg-rewrite
    db.commit()  # fcg-rewrite
    return {"message": "API key deleted successfully"}  # fcg-rewrite


@router.put("/{app_id}/keys/{key_id}/toggle")  # fcg-rewrite
async def toggle_api_key(app_id: str, key_id: str, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    key = _api_key(db, app_id, key_id, get_current_tenant_id(request))  # fcg-rewrite
    key.is_active = not key.is_active  # fcg-rewrite
    db.commit()  # fcg-rewrite
    return {"is_active": key.is_active}  # fcg-rewrite
