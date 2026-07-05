"""
Basic guard policy API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from database.connection import get_admin_db
from database.models import BasicGuardPolicy, Application
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import logging

from plugins_builtin.basic_guard.models import (
    BasicGuardPolicyUpdate,
    BasicGuardPolicyResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["basic-guard"])


def get_current_application_id(request: Request, db: Session = Depends(get_admin_db)) -> str:
    """Get current application ID from request context"""
    header_app_id = request.headers.get('x-application-id') or request.headers.get('X-Application-ID')
    if header_app_id:
        try:
            header_app_uuid = uuid.UUID(str(header_app_id))
            app = db.query(Application).filter(
                Application.id == header_app_uuid,
                Application.is_active == True
            ).first()
            if app:
                return str(app.id)
        except (ValueError, AttributeError):
            pass

    auth_context = getattr(request.state, 'auth_context', None)
    if not auth_context:
        raise HTTPException(status_code=401, detail="Not authenticated")

    application_id = auth_context['data'].get('application_id')
    if application_id:
        return str(application_id)

    tenant_id = auth_context['data'].get('tenant_id')
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant ID not found in auth context")

    try:
        tenant_uuid = uuid.UUID(str(tenant_id))
        default_app = db.query(Application).filter(
            Application.tenant_id == tenant_uuid,
            Application.is_active == True
        ).first()
        if not default_app:
            raise HTTPException(status_code=404, detail="No active application found for user")
        return str(default_app.id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")


def get_tenant_id(request: Request) -> str:
    """Get tenant ID from request auth context"""
    auth_context = getattr(request.state, 'auth_context', None)
    if not auth_context:
        raise HTTPException(status_code=401, detail="Not authenticated")
    tenant_id = auth_context['data'].get('tenant_id')
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant ID not found")
    return str(tenant_id)


def _to_policy_response(policy) -> BasicGuardPolicyResponse:
    """Convert DB policy to API response."""
    return BasicGuardPolicyResponse(
        id=str(policy.id),
        application_id=str(policy.application_id),
        enabled=policy.enabled,
        enable_content_pattern_check=policy.enable_content_pattern_check,
        enable_reasoning_divergence_check=policy.enable_reasoning_divergence_check,
        enable_output_anomaly_check=policy.enable_output_anomaly_check,
        max_repetition_ratio=policy.max_repetition_ratio,
        min_content_length=policy.min_content_length,
        violation_action=policy.violation_action,
        enable_prompt_injection_check=getattr(policy, 'enable_prompt_injection_check', True),
        prompt_injection_threshold=getattr(policy, 'prompt_injection_threshold', 0.5),
        prompt_injection_action=getattr(policy, 'prompt_injection_action', 'block'),
        scan_user_messages=getattr(policy, 'scan_user_messages', True),
        scan_system_messages=getattr(policy, 'scan_system_messages', True),
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


# ── Policy Configuration Endpoints ─────────────────────────────────────────────

@router.get("/basic-guard-policy")
async def get_basic_guard_policy(
    request: Request,
    application_id: str = Depends(get_current_application_id),
    db: Session = Depends(get_admin_db),
):
    """Get basic guard policy for current application"""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application ID")

    policy = db.query(BasicGuardPolicy).filter(
        BasicGuardPolicy.application_id == app_uuid
    ).first()

    if not policy:
        tenant_id = get_tenant_id(request)
        policy = BasicGuardPolicy(
            tenant_id=uuid.UUID(tenant_id),
            application_id=app_uuid,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)

    return _to_policy_response(policy)


@router.put("/basic-guard-policy")
async def update_basic_guard_policy(
    request: Request,
    policy_data: BasicGuardPolicyUpdate,
    application_id: str = Depends(get_current_application_id),
    db: Session = Depends(get_admin_db),
):
    """Update basic guard policy for current application"""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application ID")

    policy = db.query(BasicGuardPolicy).filter(
        BasicGuardPolicy.application_id == app_uuid
    ).first()

    if not policy:
        tenant_id = get_tenant_id(request)
        policy = BasicGuardPolicy(
            tenant_id=uuid.UUID(tenant_id),
            application_id=app_uuid,
        )
        db.add(policy)

    for field, value in policy_data.model_dump().items():
        setattr(policy, field, value)

    db.commit()
    db.refresh(policy)

    # Invalidate cache
    try:
        from plugins_builtin.basic_guard.cache import basic_guard_cache
        await basic_guard_cache.invalidate(application_id)
    except Exception as e:
        logger.warning(f"Failed to invalidate basic guard cache: {e}")

    return {
        "success": True,
        "message": "Basic guard policy updated",
        "policy": _to_policy_response(policy),
    }
