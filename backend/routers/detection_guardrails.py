from fastapi import APIRouter, Depends, Request, HTTPException
from config import settings
from services.detection_guardrail_service import DetectionGuardrailService
from services.ban_policy_service import BanPolicyService
from utils.i18n import get_language_from_request
from models.requests import GuardrailRequest, InputGuardrailRequest, OutputGuardrailRequest, Message, SkillAuditRequest
from models.responses import GuardrailResponse, SkillAuditResponse
from utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(tags=["Detection Guardrails"])

async def check_user_ban_status(tenant_id: str, user_id: str):
    """Check if the user is banned"""
    ban_record = await BanPolicyService.check_user_banned(tenant_id, user_id)
    if ban_record:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "User is banned",
                "ban_until": ban_record['ban_until'].isoformat() if hasattr(ban_record['ban_until'], 'isoformat') else str(ban_record['ban_until']),
                "reason": ban_record['reason']
            }
        )

@router.post("/guardrails", response_model=GuardrailResponse)
async def check_guardrails(
    request_data: GuardrailRequest,
    request: Request
):
    """
    Guardrail detection API - detection service专用版本（只写日志，不写数据库）
    """
    try:
        # Get client information
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Get user context
        auth_context = getattr(request.state, 'auth_context', None)
        tenant_id = None
        application_id = None
        if auth_context:
            tenant_id = str(auth_context['data'].get('tenant_id'))
            application_id = auth_context['data'].get('application_id')  # Extract application_id from auth

        # Also check for X-Application-ID header (for frontend/online test)
        header_app_id = request.headers.get('x-application-id') or request.headers.get('X-Application-ID')
        if header_app_id:
            application_id = header_app_id
            logger.info(f"Using application_id from header: {application_id}")

        if not tenant_id:
            raise HTTPException(status_code=401, detail="User ID not found in auth context")

        # Get user ID, reasoning_content, tools, tool_calls from extra_body
        user_id = None
        reasoning_content = None
        tools = None
        tool_calls = None
        if request_data.extra_body:
            user_id = request_data.extra_body.get('xxai_app_user_id')
            reasoning_content = request_data.extra_body.get('reasoning_content')
            tools = request_data.extra_body.get('tools')
            tool_calls = request_data.extra_body.get('tool_calls')

        # If there is no user_id, use tenant_id as fallback
        if not user_id:
            user_id = tenant_id

        # Check if the user is banned
        await check_user_ban_status(tenant_id, user_id)

        # Check monthly scan limit (before processing)
        from database.connection import get_admin_db
        db = next(get_admin_db())
        try:
            from services.rate_limiter import RateLimitService
            rate_limit_service = RateLimitService(db)
            is_allowed, current_usage, monthly_limit = rate_limit_service.check_and_increment_monthly_usage(tenant_id)

            if not is_allowed:
                logger.warning(f"Monthly scan limit exceeded for tenant {tenant_id}: {current_usage}/{monthly_limit}")
                raise HTTPException(
                    status_code=429,
                    detail=f"Monthly scan limit exceeded. Used {current_usage}/{monthly_limit} scans this month."
                )

            if current_usage and monthly_limit:
                logger.info(f"Monthly usage for tenant {tenant_id}: {current_usage}/{monthly_limit}")
        finally:
            db.close()

        # Create detection service (no database connection)
        guardrail_service = DetectionGuardrailService()

        # Execute detection (only write log file)
        result = await guardrail_service.check_guardrails(
            request_data,
            ip_address=ip_address,
            user_agent=user_agent,
            tenant_id=tenant_id,
            application_id=application_id  # Pass application_id to service
        )

        # Run Agent Safety reasoning audit if reasoning_content is provided
        if reasoning_content and application_id:
            try:
                from plugins_builtin.agent_safety.cache import agent_safety_cache
                policy = await agent_safety_cache.get_policy(str(application_id))
                if policy and policy.enabled and policy.enable_reasoning_safety:
                    from plugins_builtin.agent_safety.service import agent_safety_service
                    # Extract user message for context
                    user_message = ""
                    for msg in request_data.messages:
                        if msg.role == "user" and msg.content:
                            content = msg.content if isinstance(msg.content, str) else str(msg.content)
                            user_message = content[:500]
                            break

                    reasoning_result = await agent_safety_service.check_reasoning_safety(
                        reasoning_content=reasoning_content,
                        original_user_message=user_message,
                        tenant_id=tenant_id,
                        application_id=str(application_id),
                    )

                    if reasoning_result.risk_level != 'no_risk':
                        # Merge reasoning safety result into response
                        result.result.agent_safety = {
                            "risk_level": reasoning_result.risk_level,
                            "categories": reasoning_result.categories,
                        }
                        # Escalate overall risk if reasoning is unsafe
                        risk_priority = {"no_risk": 0, "low_risk": 1, "medium_risk": 2, "high_risk": 3}
                        if risk_priority.get(reasoning_result.risk_level, 0) > risk_priority.get(result.overall_risk_level, 0):
                            result.overall_risk_level = reasoning_result.risk_level
                            result.suggest_action = "reject"
                        logger.warning(f"Reasoning safety violation detected: {reasoning_result.categories}")
            except Exception as e:
                logger.error(f"Reasoning safety check failed in detection API: {e}", exc_info=True)

        # Run Agent Safety tool checks if tools or tool_calls are provided
        if (tools or tool_calls) and application_id:
            try:
                from plugins_builtin.agent_safety.cache import agent_safety_cache
                from plugins_builtin.agent_safety.service import agent_safety_service

                policy = await agent_safety_cache.get_policy(str(application_id))
                if policy and policy.enabled:
                    risk_priority = {"no_risk": 0, "low_risk": 1, "medium_risk": 2, "high_risk": 3}
                    agent_safety_data = result.result.agent_safety or {}
                    if isinstance(agent_safety_data, dict):
                        current_agent_risk = agent_safety_data.get("risk_level", "no_risk")
                        current_agent_categories = list(agent_safety_data.get("categories", []))
                    else:
                        current_agent_risk = "no_risk"
                        current_agent_categories = []

                    # Tool definition audit
                    if tools and isinstance(tools, list) and policy.enable_tool_definition_scan:
                        tool_def_result = await agent_safety_service.check_tool_definition_security(tools, policy)
                        if tool_def_result.risk_level != 'no_risk':
                            current_agent_categories.extend(tool_def_result.categories)
                            if risk_priority.get(tool_def_result.risk_level, 0) > risk_priority.get(current_agent_risk, 0):
                                current_agent_risk = tool_def_result.risk_level
                            logger.warning(f"Tool definition security issues: {tool_def_result.categories}")

                        # Also check tool names against whitelist/blacklist
                        tool_names_result = await agent_safety_service.check_tool_definitions(tools, policy)
                        if tool_names_result.risk_level != 'no_risk':
                            current_agent_categories.extend(tool_names_result.categories)
                            if risk_priority.get(tool_names_result.risk_level, 0) > risk_priority.get(current_agent_risk, 0):
                                current_agent_risk = tool_names_result.risk_level
                            logger.warning(f"Tool definition violations: {tool_names_result.blocked_tools}")

                    # Tool call monitoring (argument inspection, frequency tracking)
                    if tool_calls and isinstance(tool_calls, list):
                        tool_call_result = await agent_safety_service.check_tool_calls(
                            tool_calls, policy,
                            current_call_count=0,
                            application_id=str(application_id),
                        )
                        if tool_call_result.risk_level != 'no_risk':
                            current_agent_categories.extend(tool_call_result.categories)
                            if risk_priority.get(tool_call_result.risk_level, 0) > risk_priority.get(current_agent_risk, 0):
                                current_agent_risk = tool_call_result.risk_level
                            logger.warning(f"Tool call violations: categories={tool_call_result.categories}, "
                                         f"blocked={tool_call_result.blocked_tools}, "
                                         f"suspicious_args={tool_call_result.suspicious_arguments}")

                    # Update agent_safety in result if any issues found
                    if current_agent_risk != 'no_risk':
                        result.result.agent_safety = {
                            "risk_level": current_agent_risk,
                            "categories": list(set(current_agent_categories)),
                        }
                        # Escalate overall risk if needed
                        if risk_priority.get(current_agent_risk, 0) > risk_priority.get(result.overall_risk_level, 0):
                            result.overall_risk_level = current_agent_risk
                            result.suggest_action = "reject"

            except Exception as e:
                logger.error(f"Agent safety tool check failed in detection API: {e}", exc_info=True)

        # Check and apply ban policy
        logger.info(f"Checking ban policy: overall_risk_level={result.overall_risk_level}, user_id={user_id}, tenant_id={tenant_id}")
        if result.overall_risk_level in ['中风险', '高风险']:
            logger.info(f"Ban policy check triggered for user_id={user_id}, risk_level={result.overall_risk_level}")
            try:
                # Get language setting
                language = get_language_from_request(request, tenant_id)
                await BanPolicyService.check_and_apply_ban_policy(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    risk_level=result.overall_risk_level,
                    detection_result_id=result.id,
                    language=language,
                    application_id=application_id
                )
                logger.info(f"Ban policy check completed for user_id={user_id}")
            except Exception as e:
                logger.error(f"Ban policy check failed for user_id={user_id}: {e}", exc_info=True)
        else:
            logger.info(f"Ban policy check skipped: risk_level={result.overall_risk_level}")

        logger.info(f"Detection completed: {result.id}, action: {result.suggest_action}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Detection API error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Detection service error")

@router.get("/guardrails/health")
async def health_check():
    """Detection service health check"""
    return {
        "status": "healthy",
        "service": "detection_guardrails",
        "timestamp": "2025-01-01T00:00:00Z"
    }

@router.get("/guardrails/models")
async def list_models():
    """List available models"""
    return {
        "object": "list",
        "data": [
            {
                "id": settings.guardrails_model_name,
                "object": "model",
                "created": 1640995200,
                "owned_by": "fangcunguard",
                "permission": [],
                "root": settings.guardrails_model_name,
                "parent": None,
            }
        ]
    }

@router.post("/guardrails/input", response_model=GuardrailResponse)
async def check_input_guardrails(
    request_data: InputGuardrailRequest,
    request: Request
):
    """
    Input detection API - detection service special version (for dify/coze etc. agent platform plugins)
    """
    try:
        # Convert input to messages format
        messages = [Message(role="user", content=request_data.input)]
        
        # Construct standard GuardrailRequest
        guardrail_request = GuardrailRequest(
            model=settings.guardrails_model_name,
            messages=messages
        )
        
        # Get client information
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        # Get user context
        auth_context = getattr(request.state, 'auth_context', None)
        tenant_id = None
        application_id = None
        if auth_context:
            tenant_id = str(auth_context['data'].get('tenant_id'))
            application_id = auth_context['data'].get('application_id')

        # Also check for X-Application-ID header (for frontend/online test)
        header_app_id = request.headers.get('x-application-id') or request.headers.get('X-Application-ID')
        if header_app_id:
            application_id = header_app_id
            logger.info(f"Using application_id from header: {application_id}")

        if not tenant_id:
            raise HTTPException(status_code=401, detail="User ID not found in auth context")

        # Check monthly scan limit (before processing)
        from database.connection import get_admin_db
        db = next(get_admin_db())
        try:
            from services.rate_limiter import RateLimitService
            rate_limit_service = RateLimitService(db)
            is_allowed, current_usage, monthly_limit = rate_limit_service.check_and_increment_monthly_usage(tenant_id)

            if not is_allowed:
                logger.warning(f"Monthly scan limit exceeded for tenant {tenant_id}: {current_usage}/{monthly_limit}")
                raise HTTPException(
                    status_code=429,
                    detail=f"Monthly scan limit exceeded. Used {current_usage}/{monthly_limit} scans this month."
                )

            if current_usage and monthly_limit:
                logger.info(f"Monthly usage for tenant {tenant_id}: {current_usage}/{monthly_limit}")
        finally:
            db.close()

        # Create detection service (no database connection)
        guardrail_service = DetectionGuardrailService()

        # Execute detection (only write log file)
        result = await guardrail_service.check_guardrails(
            guardrail_request,
            ip_address=ip_address,
            user_agent=user_agent,
            tenant_id=tenant_id,
            application_id=application_id
        )

        logger.info(f"Input detection completed: {result.id}, action: {result.suggest_action}")

        return result

    except Exception as e:
        logger.error(f"Input detection API error: {e}")
        raise HTTPException(status_code=500, detail="Detection service error")

@router.post("/guardrails/output", response_model=GuardrailResponse)
async def check_output_guardrails(
    request_data: OutputGuardrailRequest,
    request: Request
):
    """
    Output detection API - detection service special version (for dify/coze etc. agent platform plugins)
    """
    try:
        # Convert input output to messages format
        messages = [
            Message(role="user", content=request_data.input),
            Message(role="assistant", content=request_data.output)
        ]

        # Construct standard GuardrailRequest
        guardrail_request = GuardrailRequest(
            model=settings.guardrails_model_name,
            messages=messages
        )

        # Get client information
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Get user context
        auth_context = getattr(request.state, 'auth_context', None)
        tenant_id = None
        application_id = None
        if auth_context:
            tenant_id = str(auth_context['data'].get('tenant_id'))
            application_id = auth_context['data'].get('application_id')

        # Also check for X-Application-ID header (for frontend/online test)
        header_app_id = request.headers.get('x-application-id') or request.headers.get('X-Application-ID')
        if header_app_id:
            application_id = header_app_id
            logger.info(f"Using application_id from header: {application_id}")

        if not tenant_id:
            raise HTTPException(status_code=401, detail="User ID not found in auth context")

        # Check monthly scan limit (before processing)
        from database.connection import get_admin_db
        db = next(get_admin_db())
        try:
            from services.rate_limiter import RateLimitService
            rate_limit_service = RateLimitService(db)
            is_allowed, current_usage, monthly_limit = rate_limit_service.check_and_increment_monthly_usage(tenant_id)

            if not is_allowed:
                logger.warning(f"Monthly scan limit exceeded for tenant {tenant_id}: {current_usage}/{monthly_limit}")
                raise HTTPException(
                    status_code=429,
                    detail=f"Monthly scan limit exceeded. Used {current_usage}/{monthly_limit} scans this month."
                )

            if current_usage and monthly_limit:
                logger.info(f"Monthly usage for tenant {tenant_id}: {current_usage}/{monthly_limit}")
        finally:
            db.close()

        # Create detection service (no database connection)
        guardrail_service = DetectionGuardrailService()

        # Execute detection (only write log file)
        result = await guardrail_service.check_guardrails(
            guardrail_request,
            ip_address=ip_address,
            user_agent=user_agent,
            tenant_id=tenant_id,
            application_id=application_id
        )

        logger.info(f"Output detection completed: {result.id}, action: {result.suggest_action}")
        
        return result
        
    except Exception as e:
        logger.error(f"Output detection API error: {e}")
        raise HTTPException(status_code=500, detail="Detection service error")


@router.post("/guardrails/skill-audit", response_model=SkillAuditResponse)
async def skill_audit(
    request_data: SkillAuditRequest,
    request: Request
):
    """
    Skill operation audit API - Two-layer safety analysis for Agent skill operations.

    Layer 1: Qwen3Guard classification (content safety)
    Layer 2: Qwen3-8B LLM review (operation context analysis)

    Returns risk level 0-3 with analysis reasoning.
    """
    try:
        # Verify authentication
        auth_context = getattr(request.state, 'auth_context', None)
        if not auth_context:
            raise HTTPException(status_code=401, detail="Not authenticated")

        tenant_id = str(auth_context['data'].get('tenant_id'))
        if not tenant_id:
            raise HTTPException(status_code=401, detail="User ID not found in auth context")

        logger.info(f"Skill audit request: skill={request_data.skill_name}, "
                     f"current_op={request_data.current_operation}, tenant={tenant_id}")

        from services.skill_audit_service import audit_skill_operation
        result = await audit_skill_operation(request_data)

        logger.info(f"Skill audit completed: {result.id}, risk_level={result.risk_level}, action={result.suggest_action}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Skill audit API error: {e}")
        raise HTTPException(status_code=500, detail="Skill audit service error")
