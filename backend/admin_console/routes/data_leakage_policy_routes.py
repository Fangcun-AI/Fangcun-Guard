"""Tenant defaults and application overrides for data leakage handling."""

from datetime import datetime  # fcg-rewrite
from typing import Annotated, List, Optional  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status  # fcg-rewrite
from pydantic import BaseModel, Field  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from config import settings  # fcg-rewrite
from database.connection import get_admin_db  # fcg-rewrite
from database.models import (  # fcg-rewrite
    Application,  # fcg-rewrite
    ApplicationDataLeakagePolicy,  # fcg-rewrite
    TenantDataLeakagePolicy,  # fcg-rewrite
    UpstreamApiConfig,  # fcg-rewrite
)
from services.data_leakage_disposal_service import LeakageMitigator  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite
from utils.subscription_check import SubscriptionFeature, require_subscription_for_feature  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(prefix="/api/v1/config", tags=["Data Leakage Policy"])  # fcg-rewrite

Action = Annotated[  # fcg-rewrite
    str,
    Field(pattern="^(block|switch_private_model|anonymize|anonymize_restore|pass)$"),  # fcg-rewrite
]


def get_current_user(request: Request) -> dict:  # fcg-rewrite
    context = getattr(request.state, "auth_context", None)  # fcg-rewrite
    if isinstance(context, dict):  # fcg-rewrite
        return context.get("data", context)  # fcg-rewrite
    raise HTTPException(status_code=401, detail="Not authenticated" if not context else "Invalid auth context")  # fcg-rewrite


def get_application_id(request: Request, x_application_id: Optional[str] = Header(None)) -> UUID:  # fcg-rewrite
    raw_id = x_application_id or get_current_user(request).get("application_id")  # fcg-rewrite
    if not raw_id:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
            detail="No application context. Please provide X-Application-ID header.",  # fcg-rewrite
        )
    try:
        return UUID(str(raw_id))  # fcg-rewrite
    except ValueError as exc:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
            detail="Invalid X-Application-ID format",  # fcg-rewrite
        ) from exc  # fcg-rewrite


class UpstreamApiConfigBrief(BaseModel):  # fcg-rewrite
    id: str
    config_name: str  # fcg-rewrite
    provider: Optional[str] = None  # fcg-rewrite
    api_base_url: str  # fcg-rewrite
    is_private_model: bool  # fcg-rewrite
    is_default_private_model: bool  # fcg-rewrite

    @classmethod  # fcg-rewrite
    def from_orm(cls, model):  # fcg-rewrite
        return cls(  # fcg-rewrite
            id=str(model.id),  # fcg-rewrite
            config_name=model.config_name,  # fcg-rewrite
            provider=model.provider,  # fcg-rewrite
            api_base_url=model.api_base_url,  # fcg-rewrite
            is_private_model=model.is_private_model,  # fcg-rewrite
            is_default_private_model=model.is_default_private_model,  # fcg-rewrite
        )


class TenantPolicyUpdate(BaseModel):  # fcg-rewrite
    default_input_high_risk_action: Action  # fcg-rewrite
    default_input_medium_risk_action: Action  # fcg-rewrite
    default_input_low_risk_action: Action  # fcg-rewrite
    default_output_high_risk_anonymize: bool  # fcg-rewrite
    default_output_medium_risk_anonymize: bool  # fcg-rewrite
    default_output_low_risk_anonymize: bool  # fcg-rewrite
    default_enable_format_detection: bool = True  # fcg-rewrite
    default_enable_smart_segmentation: bool = True  # fcg-rewrite


class TenantPolicyResponse(TenantPolicyUpdate):  # fcg-rewrite
    id: str
    tenant_id: str  # fcg-rewrite
    default_private_model: Optional[UpstreamApiConfigBrief] = None  # fcg-rewrite
    available_private_models: List[UpstreamApiConfigBrief] = Field(default_factory=list)  # fcg-rewrite
    created_at: datetime  # fcg-rewrite
    updated_at: datetime  # fcg-rewrite


class ApplicationPolicyUpdate(BaseModel):  # fcg-rewrite
    input_high_risk_action: Optional[Action] = None  # fcg-rewrite
    input_medium_risk_action: Optional[Action] = None  # fcg-rewrite
    input_low_risk_action: Optional[Action] = None  # fcg-rewrite
    output_high_risk_anonymize: Optional[bool] = None  # fcg-rewrite
    output_medium_risk_anonymize: Optional[bool] = None  # fcg-rewrite
    output_low_risk_anonymize: Optional[bool] = None  # fcg-rewrite
    private_model_id: Optional[str] = None  # fcg-rewrite
    enable_format_detection: Optional[bool] = None  # fcg-rewrite
    enable_smart_segmentation: Optional[bool] = None  # fcg-rewrite


class ApplicationPolicyResponse(BaseModel):  # fcg-rewrite
    id: str
    application_id: str  # fcg-rewrite
    input_high_risk_action: str  # fcg-rewrite
    input_medium_risk_action: str  # fcg-rewrite
    input_low_risk_action: str  # fcg-rewrite
    input_high_risk_action_override: Optional[str]  # fcg-rewrite
    input_medium_risk_action_override: Optional[str]  # fcg-rewrite
    input_low_risk_action_override: Optional[str]  # fcg-rewrite
    output_high_risk_anonymize: bool  # fcg-rewrite
    output_medium_risk_anonymize: bool  # fcg-rewrite
    output_low_risk_anonymize: bool  # fcg-rewrite
    output_high_risk_anonymize_override: Optional[bool]  # fcg-rewrite
    output_medium_risk_anonymize_override: Optional[bool]  # fcg-rewrite
    output_low_risk_anonymize_override: Optional[bool]  # fcg-rewrite
    private_model: Optional[UpstreamApiConfigBrief] = None  # fcg-rewrite
    private_model_override: Optional[str] = None  # fcg-rewrite
    available_private_models: List[UpstreamApiConfigBrief] = Field(default_factory=list)  # fcg-rewrite
    enable_format_detection: bool  # fcg-rewrite
    enable_smart_segmentation: bool  # fcg-rewrite
    enable_format_detection_override: Optional[bool]  # fcg-rewrite
    enable_smart_segmentation_override: Optional[bool]  # fcg-rewrite
    created_at: datetime  # fcg-rewrite
    updated_at: datetime  # fcg-rewrite


def _tenant_id(request: Request) -> UUID:  # fcg-rewrite
    return UUID(str(get_current_user(request)["tenant_id"]))  # fcg-rewrite


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


def _available_models(db: Session, tenant_id: UUID) -> list:  # fcg-rewrite
    return LeakageMitigator(db).list_available_private_models(str(tenant_id))  # fcg-rewrite


def _default_model(db: Session, tenant_id: UUID):  # fcg-rewrite
    return db.query(UpstreamApiConfig).filter(  # fcg-rewrite
        UpstreamApiConfig.tenant_id == tenant_id,  # fcg-rewrite
        UpstreamApiConfig.is_private_model == True,  # fcg-rewrite
        UpstreamApiConfig.is_default_private_model == True,  # fcg-rewrite
        UpstreamApiConfig.is_active == True,  # fcg-rewrite
    ).first()  # fcg-rewrite


def _brief(model) -> Optional[UpstreamApiConfigBrief]:  # fcg-rewrite
    return UpstreamApiConfigBrief.from_orm(model) if model else None  # fcg-rewrite


def _tenant_response(db: Session, policy) -> TenantPolicyResponse:  # fcg-rewrite
    models = _available_models(db, policy.tenant_id)  # fcg-rewrite
    return TenantPolicyResponse(  # fcg-rewrite
        id=str(policy.id),  # fcg-rewrite
        tenant_id=str(policy.tenant_id),  # fcg-rewrite
        default_private_model=_brief(_default_model(db, policy.tenant_id)),  # fcg-rewrite
        available_private_models=[_brief(model) for model in models],  # fcg-rewrite
        **{
            field: getattr(policy, field)  # fcg-rewrite
            for field in TenantPolicyUpdate.model_fields  # fcg-rewrite
        },
        created_at=policy.created_at,  # fcg-rewrite
        updated_at=policy.updated_at,  # fcg-rewrite
    )


def _require_application(db: Session, application_id: UUID, tenant_id: UUID) -> Application:  # fcg-rewrite
    application = db.query(Application).filter(  # fcg-rewrite
        Application.id == application_id, Application.tenant_id == tenant_id  # fcg-rewrite
    ).first()  # fcg-rewrite
    if not application:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Application not found or access denied")  # fcg-rewrite
    return application  # fcg-rewrite


def _resolved(override, fallback):  # fcg-rewrite
    return fallback if override is None else override  # fcg-rewrite


def _application_response(db: Session, policy, tenant_policy) -> ApplicationPolicyResponse:  # fcg-rewrite
    actions = {  # fcg-rewrite
        "high": policy.input_high_risk_action or tenant_policy.default_input_high_risk_action or "block",  # fcg-rewrite
        "medium": policy.input_medium_risk_action or tenant_policy.default_input_medium_risk_action or "anonymize",  # fcg-rewrite
        "low": policy.input_low_risk_action or tenant_policy.default_input_low_risk_action or "pass",  # fcg-rewrite
    }
    output = {  # fcg-rewrite
        risk: _resolved(  # fcg-rewrite
            getattr(policy, f"output_{risk}_risk_anonymize"),  # fcg-rewrite
            getattr(tenant_policy, f"default_output_{risk}_risk_anonymize"),  # fcg-rewrite
        )
        for risk in ("high", "medium", "low")  # fcg-rewrite
    }
    private_model = (  # fcg-rewrite
        db.query(UpstreamApiConfig).filter(UpstreamApiConfig.id == policy.private_model_id).first()  # fcg-rewrite
        if policy.private_model_id else _default_model(db, tenant_policy.tenant_id)  # fcg-rewrite
    )
    return ApplicationPolicyResponse(  # fcg-rewrite
        id=str(policy.id),  # fcg-rewrite
        application_id=str(policy.application_id),  # fcg-rewrite
        input_high_risk_action=actions["high"],  # fcg-rewrite
        input_medium_risk_action=actions["medium"],  # fcg-rewrite
        input_low_risk_action=actions["low"],  # fcg-rewrite
        input_high_risk_action_override=policy.input_high_risk_action,  # fcg-rewrite
        input_medium_risk_action_override=policy.input_medium_risk_action,  # fcg-rewrite
        input_low_risk_action_override=policy.input_low_risk_action,  # fcg-rewrite
        output_high_risk_anonymize=output["high"],  # fcg-rewrite
        output_medium_risk_anonymize=output["medium"],  # fcg-rewrite
        output_low_risk_anonymize=output["low"],  # fcg-rewrite
        output_high_risk_anonymize_override=policy.output_high_risk_anonymize,  # fcg-rewrite
        output_medium_risk_anonymize_override=policy.output_medium_risk_anonymize,  # fcg-rewrite
        output_low_risk_anonymize_override=policy.output_low_risk_anonymize,  # fcg-rewrite
        private_model=_brief(private_model),  # fcg-rewrite
        private_model_override=str(policy.private_model_id) if policy.private_model_id else None,  # fcg-rewrite
        available_private_models=[_brief(model) for model in _available_models(db, tenant_policy.tenant_id)],  # fcg-rewrite
        enable_format_detection=_resolved(  # fcg-rewrite
            policy.enable_format_detection, tenant_policy.default_enable_format_detection  # fcg-rewrite
        ),
        enable_smart_segmentation=_resolved(  # fcg-rewrite
            policy.enable_smart_segmentation, tenant_policy.default_enable_smart_segmentation  # fcg-rewrite
        ),
        enable_format_detection_override=policy.enable_format_detection,  # fcg-rewrite
        enable_smart_segmentation_override=policy.enable_smart_segmentation,  # fcg-rewrite
        created_at=policy.created_at,  # fcg-rewrite
        updated_at=policy.updated_at,  # fcg-rewrite
    )


def _require_paid_features(db: Session, tenant_id: str, format_detection, smart_segmentation):  # fcg-rewrite
    checks = (  # fcg-rewrite
        (format_detection, SubscriptionFeature.FORMAT_DETECTION),  # fcg-rewrite
        (smart_segmentation, SubscriptionFeature.SMART_SEGMENTATION),  # fcg-rewrite
    )
    for enabled, feature in checks:  # fcg-rewrite
        if enabled is True:  # fcg-rewrite
            require_subscription_for_feature(  # fcg-rewrite
                tenant_id=tenant_id, db=db, feature=feature, language=settings.default_language  # fcg-rewrite
            )


def _failure(label: str, exc: Exception):  # fcg-rewrite
    logger.error("%s: %s", label, exc, exc_info=True)  # fcg-rewrite
    raise HTTPException(status_code=500, detail=f"{label}: {exc}") from exc  # fcg-rewrite


@router.get("/data-leakage-policy/tenant-defaults", response_model=TenantPolicyResponse)  # fcg-rewrite
async def get_tenant_default_policy(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    try:
        policy = _first_or_create(db, TenantDataLeakagePolicy, tenant_id=_tenant_id(request))  # fcg-rewrite
        return _tenant_response(db, policy)  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _failure("Error getting tenant default policy", exc)  # fcg-rewrite


@router.put("/data-leakage-policy/tenant-defaults", response_model=TenantPolicyResponse)  # fcg-rewrite
async def update_tenant_default_policy(  # fcg-rewrite
    request: Request, policy_update: TenantPolicyUpdate, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    try:
        tenant_id = _tenant_id(request)  # fcg-rewrite
        _require_paid_features(  # fcg-rewrite
            db,
            str(tenant_id),  # fcg-rewrite
            policy_update.default_enable_format_detection,  # fcg-rewrite
            policy_update.default_enable_smart_segmentation,  # fcg-rewrite
        )
        policy = _first_or_create(db, TenantDataLeakagePolicy, tenant_id=tenant_id)  # fcg-rewrite
        for field, value in policy_update.model_dump().items():  # fcg-rewrite
            setattr(policy, field, value)  # fcg-rewrite
        db.commit()  # fcg-rewrite
        db.refresh(policy)  # fcg-rewrite
        return _tenant_response(db, policy)  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _failure("Error updating tenant default policy", exc)  # fcg-rewrite


@router.get("/data-leakage-policy", response_model=ApplicationPolicyResponse)  # fcg-rewrite
async def get_application_policy(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    application_id: UUID = Depends(get_application_id),  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    try:
        tenant_id = _tenant_id(request)  # fcg-rewrite
        _require_application(db, application_id, tenant_id)  # fcg-rewrite
        tenant_policy = _first_or_create(db, TenantDataLeakagePolicy, tenant_id=tenant_id)  # fcg-rewrite
        policy = _first_or_create(  # fcg-rewrite
            db, ApplicationDataLeakagePolicy, tenant_id=tenant_id, application_id=application_id  # fcg-rewrite
        )
        return _application_response(db, policy, tenant_policy)  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _failure("Error getting policy", exc)  # fcg-rewrite


@router.put("/data-leakage-policy", response_model=ApplicationPolicyResponse)  # fcg-rewrite
async def update_application_policy(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    policy_update: ApplicationPolicyUpdate,  # fcg-rewrite
    application_id: UUID = Depends(get_application_id),  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    try:
        tenant_id = _tenant_id(request)  # fcg-rewrite
        _require_paid_features(  # fcg-rewrite
            db, str(tenant_id), policy_update.enable_format_detection, policy_update.enable_smart_segmentation  # fcg-rewrite
        )
        _require_application(db, application_id, tenant_id)  # fcg-rewrite
        if policy_update.private_model_id:  # fcg-rewrite
            private_model = db.query(UpstreamApiConfig).filter(  # fcg-rewrite
                UpstreamApiConfig.id == policy_update.private_model_id,  # fcg-rewrite
                UpstreamApiConfig.tenant_id == tenant_id,  # fcg-rewrite
                UpstreamApiConfig.is_private_model == True,  # fcg-rewrite
                UpstreamApiConfig.is_active == True,  # fcg-rewrite
            ).first()  # fcg-rewrite
            if not private_model:  # fcg-rewrite
                raise HTTPException(status_code=400, detail="Private model not found or not configured as data-safe")  # fcg-rewrite
        policy = _first_or_create(  # fcg-rewrite
            db, ApplicationDataLeakagePolicy, tenant_id=tenant_id, application_id=application_id  # fcg-rewrite
        )
        for field, value in policy_update.model_dump().items():  # fcg-rewrite
            setattr(policy, field, UUID(value) if field == "private_model_id" and value else value)  # fcg-rewrite
        db.commit()  # fcg-rewrite
        db.refresh(policy)  # fcg-rewrite
        tenant_policy = _first_or_create(db, TenantDataLeakagePolicy, tenant_id=tenant_id)  # fcg-rewrite
        return _application_response(db, policy, tenant_policy)  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _failure("Error updating policy", exc)  # fcg-rewrite


@router.get("/private-models", response_model=List[UpstreamApiConfigBrief])  # fcg-rewrite
async def list_private_models(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    try:
        return [_brief(model) for model in _available_models(db, _tenant_id(request))]  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        _failure("Error listing private models", exc)  # fcg-rewrite
