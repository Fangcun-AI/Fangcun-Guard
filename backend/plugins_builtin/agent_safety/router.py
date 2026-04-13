"""
Agent safety policy API routes (moved from routers/agent_safety_api.py — agent-safety portion)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from database.connection import get_admin_db
from database.models import AgentSafetyPolicy, Application
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import logging

from plugins_builtin.agent_safety.models import AgentSafetyPolicyUpdate, AgentSafetyPolicyResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["agent-safety"])


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


@router.get("/agent-safety-policy")
async def get_agent_safety_policy(
    request: Request,
    application_id: str = Depends(get_current_application_id),
    db: Session = Depends(get_admin_db),
):
    """Get agent safety policy for current application"""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application ID")

    policy = db.query(AgentSafetyPolicy).filter(
        AgentSafetyPolicy.application_id == app_uuid
    ).first()

    if not policy:
        tenant_id = get_tenant_id(request)
        policy = AgentSafetyPolicy(
            tenant_id=uuid.UUID(tenant_id),
            application_id=app_uuid,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)

    return AgentSafetyPolicyResponse(
        id=str(policy.id),
        application_id=str(policy.application_id),
        enabled=policy.enabled,
        tool_whitelist=policy.tool_whitelist,
        tool_blacklist=policy.tool_blacklist or [],
        max_tool_calls_per_request=policy.max_tool_calls_per_request,
        enable_argument_inspection=policy.enable_argument_inspection,
        argument_patterns=policy.argument_patterns or [],
        enable_reasoning_safety=policy.enable_reasoning_safety,
        enable_tool_definition_scan=getattr(policy, 'enable_tool_definition_scan', True),
        tool_violation_action=policy.tool_violation_action,
        reasoning_violation_action=policy.reasoning_violation_action,
        tool_definition_scan_action=getattr(policy, 'tool_definition_scan_action', 'warn'),
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.put("/agent-safety-policy")
async def update_agent_safety_policy(
    request: Request,
    policy_data: AgentSafetyPolicyUpdate,
    application_id: str = Depends(get_current_application_id),
    db: Session = Depends(get_admin_db),
):
    """Update agent safety policy for current application"""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application ID")

    policy = db.query(AgentSafetyPolicy).filter(
        AgentSafetyPolicy.application_id == app_uuid
    ).first()

    if not policy:
        tenant_id = get_tenant_id(request)
        policy = AgentSafetyPolicy(
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
        from plugins_builtin.agent_safety.cache import agent_safety_cache
        await agent_safety_cache.invalidate(application_id)
    except Exception as e:
        logger.warning(f"Failed to invalidate agent safety cache: {e}")

    return {
        "success": True,
        "message": "Agent safety policy updated",
        "policy": AgentSafetyPolicyResponse(
            id=str(policy.id),
            application_id=str(policy.application_id),
            enabled=policy.enabled,
            tool_whitelist=policy.tool_whitelist,
            tool_blacklist=policy.tool_blacklist or [],
            max_tool_calls_per_request=policy.max_tool_calls_per_request,
            enable_argument_inspection=policy.enable_argument_inspection,
            argument_patterns=policy.argument_patterns or [],
            enable_reasoning_safety=policy.enable_reasoning_safety,
            enable_tool_definition_scan=getattr(policy, 'enable_tool_definition_scan', True),
            tool_violation_action=policy.tool_violation_action,
            reasoning_violation_action=policy.reasoning_violation_action,
            tool_definition_scan_action=getattr(policy, 'tool_definition_scan_action', 'warn'),
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        ),
    }
