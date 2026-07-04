from fastapi import APIRouter, Depends, Request, HTTPException  # fcg-rewrite
from config import settings  # fcg-rewrite
from services.detection_guardrail_service import DetectionPipeline  # fcg-rewrite
from services.ban_policy_service import BanPolicyManager  # fcg-rewrite
from utils.i18n import get_language_from_request  # fcg-rewrite
from models.requests import GuardrailRequest, InputGuardrailRequest, OutputGuardrailRequest, Message, SkillAuditRequest  # fcg-rewrite
from models.responses import GuardrailResponse, SkillAuditResponse  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Fangcun Detection Runtime"])  # fcg-rewrite

@router.post("/guardrails", response_model=GuardrailResponse)  # fcg-rewrite
async def submit_detection_guardrails(  # fcg-rewrite
    payload: GuardrailRequest,  # fcg-rewrite
    request: Request  # fcg-rewrite
):
    """
    Guardrail detection API - detection service专用版本（只写日志，不写数据库）
    """
    try:
        # Get client information
        ip_address = request.client.host if request.client else None  # fcg-rewrite
        user_agent = request.headers.get("user-agent")  # fcg-rewrite

        # Get user context
        request_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        tenant_id = None  # fcg-rewrite
        application_id = None  # fcg-rewrite
        if request_context:  # fcg-rewrite
            tenant_id = str(request_context['data'].get('tenant_id'))  # fcg-rewrite
            application_id = request_context['data'].get('application_id')  # Extract application_id from auth  # fcg-rewrite

        # Also check for X-Application-ID header (for frontend/online test)
        header_app_id = request.headers.get('x-application-id') or request.headers.get('X-Application-ID')  # fcg-rewrite
        if header_app_id:  # fcg-rewrite
            application_id = header_app_id  # fcg-rewrite
            logger.info(f"Using application_id from header: {application_id}")  # fcg-rewrite

        if not tenant_id:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="User ID not found in auth context")  # fcg-rewrite

        # Get user ID, reasoning_content, tools, tool_calls from extra_body
        user_id = None  # fcg-rewrite
        reasoning_content = None  # fcg-rewrite
        tools = None  # fcg-rewrite
        tool_calls = None  # fcg-rewrite
        if payload.extra_body:  # fcg-rewrite
            user_id = payload.extra_body.get('xxai_app_user_id')  # fcg-rewrite
            reasoning_content = payload.extra_body.get('reasoning_content')  # fcg-rewrite
            tools = payload.extra_body.get('tools')  # fcg-rewrite
            tool_calls = payload.extra_body.get('tool_calls')  # fcg-rewrite

        # If there is no user_id, use tenant_id as fallback
        if not user_id:  # fcg-rewrite
            user_id = tenant_id  # fcg-rewrite

        # Check if the user is banned
        await apply_ban_check(tenant_id, user_id)  # fcg-rewrite

        # Check monthly scan limit (before processing)
        from database.connection import get_admin_db  # fcg-rewrite
        db = next(get_admin_db())  # fcg-rewrite
        try:
            from services.rate_limiter import RateLimitService  # fcg-rewrite
            usage_service = RateLimitService(db)  # fcg-rewrite
            is_allowed, current_usage, monthly_limit = usage_service.check_and_increment_monthly_usage(tenant_id)  # fcg-rewrite

            if not is_allowed:  # fcg-rewrite
                logger.warning(f"Monthly scan limit exceeded for tenant {tenant_id}: {current_usage}/{monthly_limit}")  # fcg-rewrite
                raise HTTPException(  # fcg-rewrite
                    status_code=429,  # fcg-rewrite
                    detail=f"Monthly scan limit exceeded. Used {current_usage}/{monthly_limit} scans this month."  # fcg-rewrite
                )

            if current_usage and monthly_limit:  # fcg-rewrite
                logger.info(f"Monthly usage for tenant {tenant_id}: {current_usage}/{monthly_limit}")  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

        # Create detection service (no database connection)
        detection_service = DetectionPipeline()  # fcg-rewrite

        # Execute detection (only write log file)
        result = await detection_service.run_guardrail_check(  # fcg-rewrite
            payload,  # fcg-rewrite
            ip_address=ip_address,  # fcg-rewrite
            user_agent=user_agent,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id  # Pass application_id to service  # fcg-rewrite
        )

        # Run Agent Safety reasoning audit if reasoning_content is provided
        if reasoning_content and application_id:  # fcg-rewrite
            try:
                from plugins_builtin.agent_safety.cache import agent_safety_cache  # fcg-rewrite
                policy = await agent_safety_cache.get_policy(str(application_id))  # fcg-rewrite
                if policy and policy.enabled and policy.enable_reasoning_safety:  # fcg-rewrite
                    from plugins_builtin.agent_safety.service import agent_safety_service  # fcg-rewrite
                    # Extract user message for context
                    user_message = ""  # fcg-rewrite
                    for msg in payload.messages:  # fcg-rewrite
                        if msg.role == "user" and msg.content:  # fcg-rewrite
                            content = msg.content if isinstance(msg.content, str) else str(msg.content)  # fcg-rewrite
                            user_message = content[:500]  # fcg-rewrite
                            break

                    reasoning_result = await agent_safety_service.check_reasoning_safety(  # fcg-rewrite
                        reasoning_content=reasoning_content,  # fcg-rewrite
                        original_user_message=user_message,  # fcg-rewrite
                        tenant_id=tenant_id,  # fcg-rewrite
                        application_id=str(application_id),  # fcg-rewrite
                    )

                    if reasoning_result.risk_level != 'no_risk':  # fcg-rewrite
                        # Merge reasoning safety result into response
                        result.result.agent_safety = {  # fcg-rewrite
                            "risk_level": reasoning_result.risk_level,  # fcg-rewrite
                            "categories": reasoning_result.categories,  # fcg-rewrite
                        }
                        # Escalate overall risk if reasoning is unsafe
                        risk_priority = {"no_risk": 0, "low_risk": 1, "medium_risk": 2, "high_risk": 3}  # fcg-rewrite
                        if risk_priority.get(reasoning_result.risk_level, 0) > risk_priority.get(result.overall_risk_level, 0):  # fcg-rewrite
                            result.overall_risk_level = reasoning_result.risk_level  # fcg-rewrite
                            result.suggest_action = "reject"  # fcg-rewrite
                        logger.warning(f"Reasoning safety violation detected: {reasoning_result.categories}")  # fcg-rewrite
            except Exception as e:  # fcg-rewrite
                logger.error(f"Reasoning safety check failed in detection API: {e}", exc_info=True)  # fcg-rewrite

        # Run Agent Safety tool checks if tools or tool_calls are provided
        if (tools or tool_calls) and application_id:  # fcg-rewrite
            try:
                from plugins_builtin.agent_safety.cache import agent_safety_cache  # fcg-rewrite
                from plugins_builtin.agent_safety.service import agent_safety_service  # fcg-rewrite

                policy = await agent_safety_cache.get_policy(str(application_id))  # fcg-rewrite
                if policy and policy.enabled:  # fcg-rewrite
                    risk_priority = {"no_risk": 0, "low_risk": 1, "medium_risk": 2, "high_risk": 3}  # fcg-rewrite
                    agent_safety_data = result.result.agent_safety or {}  # fcg-rewrite
                    if isinstance(agent_safety_data, dict):  # fcg-rewrite
                        current_agent_risk = agent_safety_data.get("risk_level", "no_risk")  # fcg-rewrite
                        current_agent_categories = list(agent_safety_data.get("categories", []))  # fcg-rewrite
                    else:
                        current_agent_risk = "no_risk"  # fcg-rewrite
                        current_agent_categories = []  # fcg-rewrite

                    # Tool definition audit
                    if tools and isinstance(tools, list) and policy.enable_tool_definition_scan:  # fcg-rewrite
                        tool_def_result = await agent_safety_service.check_tool_definition_security(tools, policy)  # fcg-rewrite
                        if tool_def_result.risk_level != 'no_risk':  # fcg-rewrite
                            current_agent_categories.extend(tool_def_result.categories)  # fcg-rewrite
                            if risk_priority.get(tool_def_result.risk_level, 0) > risk_priority.get(current_agent_risk, 0):  # fcg-rewrite
                                current_agent_risk = tool_def_result.risk_level  # fcg-rewrite
                            logger.warning(f"Tool definition security issues: {tool_def_result.categories}")  # fcg-rewrite

                        # Also check tool names against whitelist/blacklist
                        tool_names_result = await agent_safety_service.check_tool_definitions(tools, policy)  # fcg-rewrite
                        if tool_names_result.risk_level != 'no_risk':  # fcg-rewrite
                            current_agent_categories.extend(tool_names_result.categories)  # fcg-rewrite
                            if risk_priority.get(tool_names_result.risk_level, 0) > risk_priority.get(current_agent_risk, 0):  # fcg-rewrite
                                current_agent_risk = tool_names_result.risk_level  # fcg-rewrite
                            logger.warning(f"Tool definition violations: {tool_names_result.blocked_tools}")  # fcg-rewrite

                    # Tool call monitoring (argument inspection, frequency tracking)
                    if tool_calls and isinstance(tool_calls, list):  # fcg-rewrite
                        tool_call_result = await agent_safety_service.check_tool_calls(  # fcg-rewrite
                            tool_calls, policy,  # fcg-rewrite
                            current_call_count=0,  # fcg-rewrite
                            application_id=str(application_id),  # fcg-rewrite
                        )
                        if tool_call_result.risk_level != 'no_risk':  # fcg-rewrite
                            current_agent_categories.extend(tool_call_result.categories)  # fcg-rewrite
                            if risk_priority.get(tool_call_result.risk_level, 0) > risk_priority.get(current_agent_risk, 0):  # fcg-rewrite
                                current_agent_risk = tool_call_result.risk_level  # fcg-rewrite
                            logger.warning(f"Tool call violations: categories={tool_call_result.categories}, "  # fcg-rewrite
                                         f"blocked={tool_call_result.blocked_tools}, "  # fcg-rewrite
                                         f"suspicious_args={tool_call_result.suspicious_arguments}")  # fcg-rewrite

                    # Update agent_safety in result if any issues found
                    if current_agent_risk != 'no_risk':  # fcg-rewrite
                        result.result.agent_safety = {  # fcg-rewrite
                            "risk_level": current_agent_risk,  # fcg-rewrite
                            "categories": list(set(current_agent_categories)),  # fcg-rewrite
                        }
                        # Escalate overall risk if needed
                        if risk_priority.get(current_agent_risk, 0) > risk_priority.get(result.overall_risk_level, 0):  # fcg-rewrite
                            result.overall_risk_level = current_agent_risk  # fcg-rewrite
                            result.suggest_action = "reject"  # fcg-rewrite

            except Exception as e:  # fcg-rewrite
                logger.error(f"Agent safety tool check failed in detection API: {e}", exc_info=True)  # fcg-rewrite

        # Check and apply ban policy
        logger.info(f"Checking ban policy: overall_risk_level={result.overall_risk_level}, user_id={user_id}, tenant_id={tenant_id}")  # fcg-rewrite
        if result.overall_risk_level in ['中风险', '高风险']:  # fcg-rewrite
            logger.info(f"Ban policy check triggered for user_id={user_id}, risk_level={result.overall_risk_level}")  # fcg-rewrite
            try:
                # Get language setting
                language = get_language_from_request(request, tenant_id)  # fcg-rewrite
                await BanPolicyManager.check_and_apply_ban_policy(  # fcg-rewrite
                    tenant_id=tenant_id,  # fcg-rewrite
                    user_id=user_id,  # fcg-rewrite
                    risk_level=result.overall_risk_level,  # fcg-rewrite
                    detection_result_id=result.id,  # fcg-rewrite
                    language=language,  # fcg-rewrite
                    application_id=application_id  # fcg-rewrite
                )
                logger.info(f"Ban policy check completed for user_id={user_id}")  # fcg-rewrite
            except Exception as e:  # fcg-rewrite
                logger.error(f"Ban policy check failed for user_id={user_id}: {e}", exc_info=True)  # fcg-rewrite
        else:
            logger.info(f"Ban policy check skipped: risk_level={result.overall_risk_level}")  # fcg-rewrite

        logger.info(f"Detection completed: {result.id}, action: {result.suggest_action}")  # fcg-rewrite

        return result  # fcg-rewrite

    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Detection API error: {e}", exc_info=True)  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Detection service error")  # fcg-rewrite

@router.get("/guardrails/health")  # fcg-rewrite
async def detection_guardrail_health_probe():  # fcg-rewrite
    """Detection service health check"""
    return {  # fcg-rewrite
        "status": "healthy",  # fcg-rewrite
        "service": "detection_guardrails",  # fcg-rewrite
        "timestamp": "2025-01-01T00:00:00Z"  # fcg-rewrite
    }

@router.get("/guardrails/models")  # fcg-rewrite
async def list_detection_models():  # fcg-rewrite
    """List available models"""
    return {  # fcg-rewrite
        "object": "list",  # fcg-rewrite
        "data": [  # fcg-rewrite
            {
                "id": settings.guardrails_model_name,  # fcg-rewrite
                "object": "model",  # fcg-rewrite
                "created": 1640995200,  # fcg-rewrite
                "owned_by": "fangcunguard",  # fcg-rewrite
                "permission": [],  # fcg-rewrite
                "root": settings.guardrails_model_name,  # fcg-rewrite
                "parent": None,  # fcg-rewrite
            }
        ]
    }

@router.post("/guardrails/input", response_model=GuardrailResponse)  # fcg-rewrite
async def inspect_detection_input(  # fcg-rewrite
    payload: InputGuardrailRequest,  # fcg-rewrite
    request: Request  # fcg-rewrite
):
    """
    Input detection API - detection service special version (for dify/coze etc. agent platform plugins)
    """
    try:
        # Convert input to messages format
        chat_messages = [Message(role="user", content=payload.input)]  # fcg-rewrite
        
        # Construct standard GuardrailRequest
        normalized_request = GuardrailRequest(  # fcg-rewrite
            model=settings.guardrails_model_name,  # fcg-rewrite
            messages=chat_messages  # fcg-rewrite
        )
        
        # Get client information
        ip_address = request.client.host if request.client else None  # fcg-rewrite
        user_agent = request.headers.get("user-agent")  # fcg-rewrite
        
        # Get user context
        request_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        tenant_id = None  # fcg-rewrite
        application_id = None  # fcg-rewrite
        if request_context:  # fcg-rewrite
            tenant_id = str(request_context['data'].get('tenant_id'))  # fcg-rewrite
            application_id = request_context['data'].get('application_id')  # fcg-rewrite

        # Also check for X-Application-ID header (for frontend/online test)
        header_app_id = request.headers.get('x-application-id') or request.headers.get('X-Application-ID')  # fcg-rewrite
        if header_app_id:  # fcg-rewrite
            application_id = header_app_id  # fcg-rewrite
            logger.info(f"Using application_id from header: {application_id}")  # fcg-rewrite

        if not tenant_id:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="User ID not found in auth context")  # fcg-rewrite

        # Check monthly scan limit (before processing)
        from database.connection import get_admin_db  # fcg-rewrite
        db = next(get_admin_db())  # fcg-rewrite
        try:
            from services.rate_limiter import RateLimitService  # fcg-rewrite
            usage_service = RateLimitService(db)  # fcg-rewrite
            is_allowed, current_usage, monthly_limit = usage_service.check_and_increment_monthly_usage(tenant_id)  # fcg-rewrite

            if not is_allowed:  # fcg-rewrite
                logger.warning(f"Monthly scan limit exceeded for tenant {tenant_id}: {current_usage}/{monthly_limit}")  # fcg-rewrite
                raise HTTPException(  # fcg-rewrite
                    status_code=429,  # fcg-rewrite
                    detail=f"Monthly scan limit exceeded. Used {current_usage}/{monthly_limit} scans this month."  # fcg-rewrite
                )

            if current_usage and monthly_limit:  # fcg-rewrite
                logger.info(f"Monthly usage for tenant {tenant_id}: {current_usage}/{monthly_limit}")  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

        # Create detection service (no database connection)
        detection_service = DetectionPipeline()  # fcg-rewrite

        # Execute detection (only write log file)
        result = await detection_service.run_guardrail_check(  # fcg-rewrite
            normalized_request,  # fcg-rewrite
            ip_address=ip_address,  # fcg-rewrite
            user_agent=user_agent,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id  # fcg-rewrite
        )

        logger.info(f"Input detection completed: {result.id}, action: {result.suggest_action}")  # fcg-rewrite

        return result  # fcg-rewrite

    except Exception as e:  # fcg-rewrite
        logger.error(f"Input detection API error: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Detection service error")  # fcg-rewrite

@router.post("/guardrails/output", response_model=GuardrailResponse)  # fcg-rewrite
async def inspect_detection_output(  # fcg-rewrite
    payload: OutputGuardrailRequest,  # fcg-rewrite
    request: Request  # fcg-rewrite
):
    """
    Output detection API - detection service special version (for dify/coze etc. agent platform plugins)
    """
    try:
        # Convert input output to messages format
        chat_messages = [  # fcg-rewrite
            Message(role="user", content=payload.input),  # fcg-rewrite
            Message(role="assistant", content=payload.output)  # fcg-rewrite
        ]

        # Construct standard GuardrailRequest
        normalized_request = GuardrailRequest(  # fcg-rewrite
            model=settings.guardrails_model_name,  # fcg-rewrite
            messages=chat_messages  # fcg-rewrite
        )

        # Get client information
        ip_address = request.client.host if request.client else None  # fcg-rewrite
        user_agent = request.headers.get("user-agent")  # fcg-rewrite

        # Get user context
        request_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        tenant_id = None  # fcg-rewrite
        application_id = None  # fcg-rewrite
        if request_context:  # fcg-rewrite
            tenant_id = str(request_context['data'].get('tenant_id'))  # fcg-rewrite
            application_id = request_context['data'].get('application_id')  # fcg-rewrite

        # Also check for X-Application-ID header (for frontend/online test)
        header_app_id = request.headers.get('x-application-id') or request.headers.get('X-Application-ID')  # fcg-rewrite
        if header_app_id:  # fcg-rewrite
            application_id = header_app_id  # fcg-rewrite
            logger.info(f"Using application_id from header: {application_id}")  # fcg-rewrite

        if not tenant_id:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="User ID not found in auth context")  # fcg-rewrite

        # Check monthly scan limit (before processing)
        from database.connection import get_admin_db  # fcg-rewrite
        db = next(get_admin_db())  # fcg-rewrite
        try:
            from services.rate_limiter import RateLimitService  # fcg-rewrite
            usage_service = RateLimitService(db)  # fcg-rewrite
            is_allowed, current_usage, monthly_limit = usage_service.check_and_increment_monthly_usage(tenant_id)  # fcg-rewrite

            if not is_allowed:  # fcg-rewrite
                logger.warning(f"Monthly scan limit exceeded for tenant {tenant_id}: {current_usage}/{monthly_limit}")  # fcg-rewrite
                raise HTTPException(  # fcg-rewrite
                    status_code=429,  # fcg-rewrite
                    detail=f"Monthly scan limit exceeded. Used {current_usage}/{monthly_limit} scans this month."  # fcg-rewrite
                )

            if current_usage and monthly_limit:  # fcg-rewrite
                logger.info(f"Monthly usage for tenant {tenant_id}: {current_usage}/{monthly_limit}")  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

        # Create detection service (no database connection)
        detection_service = DetectionPipeline()  # fcg-rewrite

        # Execute detection (only write log file)
        result = await detection_service.run_guardrail_check(  # fcg-rewrite
            normalized_request,  # fcg-rewrite
            ip_address=ip_address,  # fcg-rewrite
            user_agent=user_agent,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id  # fcg-rewrite
        )

        logger.info(f"Output detection completed: {result.id}, action: {result.suggest_action}")  # fcg-rewrite
        
        return result  # fcg-rewrite
        
    except Exception as e:  # fcg-rewrite
        logger.error(f"Output detection API error: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Detection service error")  # fcg-rewrite


@router.post("/guardrails/skill-audit", response_model=SkillAuditResponse)  # fcg-rewrite
async def run_skill_audit(  # fcg-rewrite
    payload: SkillAuditRequest,  # fcg-rewrite
    request: Request  # fcg-rewrite
):
    """
    Skill operation audit API - Two-layer safety analysis for Agent skill operations.

    Layer 1: Qwen3Guard classification (content safety)
    Layer 2: Qwen3-8B LLM review (operation context analysis)

    Returns risk level 0-3 with analysis reasoning.
    """
    try:
        # Verify authentication
        request_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        if not request_context:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite

        tenant_id = str(request_context['data'].get('tenant_id'))  # fcg-rewrite
        if not tenant_id:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="User ID not found in auth context")  # fcg-rewrite

        logger.info(f"Skill audit request: skill={payload.skill_name}, "  # fcg-rewrite
                     f"current_op={payload.current_operation}, tenant={tenant_id}")  # fcg-rewrite

        from services.skill_audit_service import audit_skill_operation  # fcg-rewrite
        result = await audit_skill_operation(payload)  # fcg-rewrite

        logger.info(f"Skill audit completed: {result.id}, risk_level={result.risk_level}, action={result.suggest_action}")  # fcg-rewrite
        return result  # fcg-rewrite

    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Skill audit API error: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Skill audit service error")  # fcg-rewrite


async def apply_ban_check(tenant_id: str, user_id: str):  # fcg-rewrite
    """Check if the user is banned"""
    ban_snapshot = await BanPolicyManager.check_user_banned(tenant_id, user_id)  # fcg-rewrite
    if ban_snapshot:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=403,  # fcg-rewrite
            detail={  # fcg-rewrite
                "error": "User is banned",  # fcg-rewrite
                "ban_until": ban_snapshot['ban_until'].isoformat() if hasattr(ban_snapshot['ban_until'], 'isoformat') else str(ban_snapshot['ban_until']),  # fcg-rewrite
                "reason": ban_snapshot['reason']  # fcg-rewrite
            }
        )
