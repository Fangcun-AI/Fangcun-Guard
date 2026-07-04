"""Unified gateway policy endpoints for tenant defaults and application overrides."""

from datetime import datetime  # fcg-rewrite
from typing import Annotated, List, Optional  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status  # fcg-rewrite
from pydantic import BaseModel, Field  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.connection import get_admin_db  # fcg-rewrite
from database.models import Application, ApplicationDataLeakagePolicy, TenantDataLeakagePolicy, UpstreamApiConfig  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(prefix="/api/v1/config", tags=["Gateway Policy"])  # fcg-rewrite

GeneralAction = Annotated[str, Field(pattern="^(block|replace|pass)$")]  # fcg-rewrite
InputAction = Annotated[str, Field(pattern="^(block|switch_private_model|anonymize|anonymize_restore|pass)$")]  # fcg-rewrite
OutputAction = Annotated[str, Field(pattern="^(block|switch_private_model|anonymize|pass)$")]  # fcg-rewrite


def get_current_user(request: Request) -> dict:  # fcg-rewrite
    context = getattr(request.state, "auth_context", None)  # fcg-rewrite
    if isinstance(context, dict):  # fcg-rewrite
        return context.get("data", context)  # fcg-rewrite
    raise HTTPException(status_code=401, detail="Not authenticated" if not context else "Invalid auth context")  # fcg-rewrite


def get_application_id(request: Request, x_application_id: Optional[str] = Header(None)) -> UUID:  # fcg-rewrite
    value = x_application_id or get_current_user(request).get("application_id")  # fcg-rewrite
    if not value:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
            detail="No application context. Please provide X-Application-ID header.",  # fcg-rewrite
        )
    try:
        return UUID(str(value))  # fcg-rewrite
    except ValueError as exc:  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Invalid X-Application-ID format") from exc  # fcg-rewrite


class PrivateModelBrief(BaseModel):  # fcg-rewrite
    id: str
    config_name: str  # fcg-rewrite
    provider: Optional[str] = None  # fcg-rewrite
    is_default_private_model: bool  # fcg-rewrite
    private_model_names: List[str] = Field(default_factory=list)  # fcg-rewrite

    @classmethod  # fcg-rewrite
    def from_orm(cls, model):  # fcg-rewrite
        return cls(  # fcg-rewrite
            id=str(model.id),  # fcg-rewrite
            config_name=model.config_name,  # fcg-rewrite
            provider=model.provider,  # fcg-rewrite
            is_default_private_model=bool(model.is_default_private_model),  # fcg-rewrite
            private_model_names=model.private_model_names or [],  # fcg-rewrite
        )


class GatewayPolicyUpdate(BaseModel):  # fcg-rewrite
    general_input_high_risk_action: Optional[GeneralAction] = None  # fcg-rewrite
    general_input_medium_risk_action: Optional[GeneralAction] = None  # fcg-rewrite
    general_input_low_risk_action: Optional[GeneralAction] = None  # fcg-rewrite
    general_output_high_risk_action: Optional[GeneralAction] = None  # fcg-rewrite
    general_output_medium_risk_action: Optional[GeneralAction] = None  # fcg-rewrite
    general_output_low_risk_action: Optional[GeneralAction] = None  # fcg-rewrite
    input_high_risk_action: Optional[InputAction] = None  # fcg-rewrite
    input_medium_risk_action: Optional[InputAction] = None  # fcg-rewrite
    input_low_risk_action: Optional[InputAction] = None  # fcg-rewrite
    output_high_risk_action: Optional[OutputAction] = None  # fcg-rewrite
    output_medium_risk_action: Optional[OutputAction] = None  # fcg-rewrite
    output_low_risk_action: Optional[OutputAction] = None  # fcg-rewrite
    private_model_id: Optional[str] = None  # fcg-rewrite


class TenantGatewayPolicyUpdate(BaseModel):  # fcg-rewrite
    default_general_input_high_risk_action: GeneralAction  # fcg-rewrite
    default_general_input_medium_risk_action: GeneralAction  # fcg-rewrite
    default_general_input_low_risk_action: GeneralAction  # fcg-rewrite
    default_general_output_high_risk_action: GeneralAction  # fcg-rewrite
    default_general_output_medium_risk_action: GeneralAction  # fcg-rewrite
    default_general_output_low_risk_action: GeneralAction  # fcg-rewrite
    default_input_high_risk_action: InputAction  # fcg-rewrite
    default_input_medium_risk_action: InputAction  # fcg-rewrite
    default_input_low_risk_action: InputAction  # fcg-rewrite
    default_output_high_risk_action: OutputAction  # fcg-rewrite
    default_output_medium_risk_action: OutputAction  # fcg-rewrite
    default_output_low_risk_action: OutputAction  # fcg-rewrite


class TenantGatewayPolicyResponse(TenantGatewayPolicyUpdate):  # fcg-rewrite
    id: str
    tenant_id: str  # fcg-rewrite
    default_private_model: Optional[PrivateModelBrief] = None  # fcg-rewrite
    available_private_models: List[PrivateModelBrief] = Field(default_factory=list)  # fcg-rewrite
    created_at: datetime  # fcg-rewrite
    updated_at: datetime  # fcg-rewrite


class GatewayPolicyResponse(BaseModel):  # fcg-rewrite
    id: str
    application_id: str  # fcg-rewrite
    general_input_high_risk_action: str  # fcg-rewrite
    general_input_medium_risk_action: str  # fcg-rewrite
    general_input_low_risk_action: str  # fcg-rewrite
    general_input_high_risk_action_override: Optional[str]  # fcg-rewrite
    general_input_medium_risk_action_override: Optional[str]  # fcg-rewrite
    general_input_low_risk_action_override: Optional[str]  # fcg-rewrite
    general_output_high_risk_action: str  # fcg-rewrite
    general_output_medium_risk_action: str  # fcg-rewrite
    general_output_low_risk_action: str  # fcg-rewrite
    general_output_high_risk_action_override: Optional[str]  # fcg-rewrite
    general_output_medium_risk_action_override: Optional[str]  # fcg-rewrite
    general_output_low_risk_action_override: Optional[str]  # fcg-rewrite
    input_high_risk_action: str  # fcg-rewrite
    input_medium_risk_action: str  # fcg-rewrite
    input_low_risk_action: str  # fcg-rewrite
    input_high_risk_action_override: Optional[str]  # fcg-rewrite
    input_medium_risk_action_override: Optional[str]  # fcg-rewrite
    input_low_risk_action_override: Optional[str]  # fcg-rewrite
    output_high_risk_action: str  # fcg-rewrite
    output_medium_risk_action: str  # fcg-rewrite
    output_low_risk_action: str  # fcg-rewrite
    output_high_risk_action_override: Optional[str]  # fcg-rewrite
    output_medium_risk_action_override: Optional[str]  # fcg-rewrite
    output_low_risk_action_override: Optional[str]  # fcg-rewrite
    private_model: Optional[PrivateModelBrief] = None  # fcg-rewrite
    private_model_override: Optional[str] = None  # fcg-rewrite
    available_private_models: List[PrivateModelBrief] = Field(default_factory=list)  # fcg-rewrite
    created_at: datetime  # fcg-rewrite
    updated_at: datetime  # fcg-rewrite


_POLICY_DEFAULTS = {  # fcg-rewrite
    "general_input_high_risk_action": ("default_general_input_high_risk_action", "default_general_high_risk_action", "block"),  # fcg-rewrite
    "general_input_medium_risk_action": ("default_general_input_medium_risk_action", "default_general_medium_risk_action", "replace"),  # fcg-rewrite
    "general_input_low_risk_action": ("default_general_input_low_risk_action", "default_general_low_risk_action", "pass"),  # fcg-rewrite
    "general_output_high_risk_action": ("default_general_output_high_risk_action", "default_general_high_risk_action", "block"),  # fcg-rewrite
    "general_output_medium_risk_action": ("default_general_output_medium_risk_action", "default_general_medium_risk_action", "replace"),  # fcg-rewrite
    "general_output_low_risk_action": ("default_general_output_low_risk_action", "default_general_low_risk_action", "pass"),  # fcg-rewrite
    "input_high_risk_action": ("default_input_high_risk_action", None, "block"),  # fcg-rewrite
    "input_medium_risk_action": ("default_input_medium_risk_action", None, "anonymize"),  # fcg-rewrite
    "input_low_risk_action": ("default_input_low_risk_action", None, "pass"),  # fcg-rewrite
    "output_high_risk_action": ("default_output_high_risk_action", None, "block"),  # fcg-rewrite
    "output_medium_risk_action": ("default_output_medium_risk_action", None, "anonymize"),  # fcg-rewrite
    "output_low_risk_action": ("default_output_low_risk_action", None, "pass"),  # fcg-rewrite
}


def _first_or_create(db: Session, model, **identity):  # fcg-rewrite
    query = db.query(model)  # fcg-rewrite
    for field, value in identity.items():  # fcg-rewrite
        query = query.filter(getattr(model, field) == value)  # fcg-rewrite
    record = query.first()  # fcg-rewrite
    if record:  # fcg-rewrite
        return record  # fcg-rewrite
    record = model(**identity)  # fcg-rewrite
    db.add(record)  # fcg-rewrite
    db.commit()  # fcg-rewrite
    db.refresh(record)  # fcg-rewrite
    return record  # fcg-rewrite


def _private_models(db: Session, tenant_id: UUID) -> list:  # fcg-rewrite
    return db.query(UpstreamApiConfig).filter(  # fcg-rewrite
        UpstreamApiConfig.tenant_id == tenant_id,  # fcg-rewrite
        UpstreamApiConfig.is_private_model == True,  # fcg-rewrite
        UpstreamApiConfig.is_active == True,  # fcg-rewrite
    ).all()


def _private_model(db: Session, tenant_id: UUID, model_id=None):  # fcg-rewrite
    query = db.query(UpstreamApiConfig).filter(  # fcg-rewrite
        UpstreamApiConfig.tenant_id == tenant_id,  # fcg-rewrite
        UpstreamApiConfig.is_private_model == True,  # fcg-rewrite
        UpstreamApiConfig.is_active == True,  # fcg-rewrite
    )
    return query.filter(UpstreamApiConfig.id == model_id).first() if model_id else query.filter(  # fcg-rewrite
        UpstreamApiConfig.is_default_private_model == True  # fcg-rewrite
    ).first()  # fcg-rewrite


def _default(policy, field: str):  # fcg-rewrite
    preferred, legacy, fallback = _POLICY_DEFAULTS[field]  # fcg-rewrite
    return getattr(policy, preferred, None) or (getattr(policy, legacy, None) if legacy else None) or fallback  # fcg-rewrite


def _tenant_payload(db: Session, policy) -> TenantGatewayPolicyResponse:  # fcg-rewrite
    models = _private_models(db, policy.tenant_id)  # fcg-rewrite
    values = {f"default_{field}": _default(policy, field) for field in _POLICY_DEFAULTS}  # fcg-rewrite
    return TenantGatewayPolicyResponse(  # fcg-rewrite
        id=str(policy.id),  # fcg-rewrite
        tenant_id=str(policy.tenant_id),  # fcg-rewrite
        default_private_model=PrivateModelBrief.from_orm(model) if (model := _private_model(db, policy.tenant_id)) else None,  # fcg-rewrite
        available_private_models=[PrivateModelBrief.from_orm(model) for model in models],  # fcg-rewrite
        created_at=policy.created_at,  # fcg-rewrite
        updated_at=policy.updated_at,  # fcg-rewrite
        **values,  # fcg-rewrite
    )


def _app_payload(db: Session, app_policy, tenant_policy) -> GatewayPolicyResponse:  # fcg-rewrite
    values = {}  # fcg-rewrite
    for field in _POLICY_DEFAULTS:  # fcg-rewrite
        override = getattr(app_policy, field, None)  # fcg-rewrite
        values[field] = override if override is not None else _default(tenant_policy, field)  # fcg-rewrite
        values[f"{field}_override"] = override  # fcg-rewrite
    model = _private_model(db, tenant_policy.tenant_id, app_policy.private_model_id) if app_policy.private_model_id else None  # fcg-rewrite
    return GatewayPolicyResponse(  # fcg-rewrite
        id=str(app_policy.id),  # fcg-rewrite
        application_id=str(app_policy.application_id),  # fcg-rewrite
        private_model=PrivateModelBrief.from_orm(model) if model else None,  # fcg-rewrite
        private_model_override=str(app_policy.private_model_id) if app_policy.private_model_id else None,  # fcg-rewrite
        available_private_models=[PrivateModelBrief.from_orm(item) for item in _private_models(db, tenant_policy.tenant_id)],  # fcg-rewrite
        created_at=app_policy.created_at,  # fcg-rewrite
        updated_at=app_policy.updated_at,  # fcg-rewrite
        **values,  # fcg-rewrite
    )


def _tenant_id(request: Request) -> UUID:  # fcg-rewrite
    return UUID(str(get_current_user(request)["tenant_id"]))  # fcg-rewrite


def _require_application(db: Session, application_id: UUID, tenant_id: UUID):  # fcg-rewrite
    if not db.query(Application).filter(Application.id == application_id, Application.tenant_id == tenant_id).first():  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Application not found or access denied")  # fcg-rewrite


def _failure(label: str, exc: Exception):  # fcg-rewrite
    logger.error("%s: %s", label, exc, exc_info=True)  # fcg-rewrite
    raise HTTPException(status_code=500, detail=f"{label}: {exc}") from exc  # fcg-rewrite


@router.get("/gateway-policy/tenant-defaults", response_model=TenantGatewayPolicyResponse)  # fcg-rewrite
async def get_tenant_gateway_policy(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    try:
        return _tenant_payload(db, _first_or_create(db, TenantDataLeakagePolicy, tenant_id=_tenant_id(request)))  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _failure("Error getting tenant gateway policy", exc)  # fcg-rewrite


@router.put("/gateway-policy/tenant-defaults", response_model=TenantGatewayPolicyResponse)  # fcg-rewrite
async def update_tenant_gateway_policy(  # fcg-rewrite
    request: Request, policy_update: TenantGatewayPolicyUpdate, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    try:
        policy = _first_or_create(db, TenantDataLeakagePolicy, tenant_id=_tenant_id(request))  # fcg-rewrite
        for field, value in policy_update.model_dump().items():  # fcg-rewrite
            setattr(policy, field, value)  # fcg-rewrite
        db.commit()  # fcg-rewrite
        db.refresh(policy)  # fcg-rewrite
        return _tenant_payload(db, policy)  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _failure("Error updating tenant gateway policy", exc)  # fcg-rewrite


@router.get("/gateway-policy", response_model=GatewayPolicyResponse)  # fcg-rewrite
async def get_gateway_policy(  # fcg-rewrite
    request: Request, db: Session = Depends(get_admin_db), application_id: UUID = Depends(get_application_id)  # fcg-rewrite
):
    try:
        tenant_id = _tenant_id(request)  # fcg-rewrite
        _require_application(db, application_id, tenant_id)  # fcg-rewrite
        tenant_policy = _first_or_create(db, TenantDataLeakagePolicy, tenant_id=tenant_id)  # fcg-rewrite
        app_policy = _first_or_create(  # fcg-rewrite
            db, ApplicationDataLeakagePolicy, tenant_id=tenant_id, application_id=application_id  # fcg-rewrite
        )
        return _app_payload(db, app_policy, tenant_policy)  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _failure("Error getting gateway policy", exc)  # fcg-rewrite


@router.put("/gateway-policy", response_model=GatewayPolicyResponse)  # fcg-rewrite
async def update_gateway_policy(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    policy_update: GatewayPolicyUpdate,  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
    application_id: UUID = Depends(get_application_id),  # fcg-rewrite
):
    try:
        tenant_id = _tenant_id(request)  # fcg-rewrite
        _require_application(db, application_id, tenant_id)  # fcg-rewrite
        app_policy = _first_or_create(  # fcg-rewrite
            db, ApplicationDataLeakagePolicy, tenant_id=tenant_id, application_id=application_id  # fcg-rewrite
        )
        values = policy_update.model_dump()  # fcg-rewrite
        private_model_id = values.pop("private_model_id")  # fcg-rewrite
        if private_model_id and not _private_model(db, tenant_id, UUID(private_model_id)):  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Private model not found or access denied")  # fcg-rewrite
        for field, value in values.items():  # fcg-rewrite
            if hasattr(app_policy, field):  # fcg-rewrite
                setattr(app_policy, field, value)  # fcg-rewrite
        app_policy.private_model_id = UUID(private_model_id) if private_model_id else None  # fcg-rewrite
        db.commit()  # fcg-rewrite
        db.refresh(app_policy)  # fcg-rewrite
        tenant_policy = _first_or_create(db, TenantDataLeakagePolicy, tenant_id=tenant_id)  # fcg-rewrite
        return _app_payload(db, app_policy, tenant_policy)  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except ValueError as exc:  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Invalid private_model_id format") from exc  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        _failure("Error updating gateway policy", exc)  # fcg-rewrite
