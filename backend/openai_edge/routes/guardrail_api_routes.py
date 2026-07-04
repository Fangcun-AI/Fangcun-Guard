from fastapi import APIRouter, Depends, Request, HTTPException  # fcg-rewrite
from config import settings  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite
from database.connection import get_proxy_db  # fcg-rewrite
from services.guardrail_service import GuardrailPipeline  # fcg-rewrite
from services.ban_policy_service import BanPolicyManager  # fcg-rewrite
from utils.i18n import get_language_from_request  # fcg-rewrite
from models.requests import GuardrailRequest, InputGuardrailRequest, OutputGuardrailRequest, Message  # fcg-rewrite
from models.responses import GuardrailResponse  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Fangcun Guard API"])  # fcg-rewrite

@router.post("/guardrails", response_model=GuardrailResponse)  # fcg-rewrite
async def submit_guardrail_check(  # fcg-rewrite
    payload: GuardrailRequest,  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_proxy_db)  # fcg-rewrite
):
    """
    Guardrail detection API - compatible with OpenAI format

    Check if the input content exists security risks or compliance issues.
    """
    try:
        # Get client information
        ip_address = request.client.host if request.client else None  # fcg-rewrite
        user_agent = request.headers.get("user-agent")  # fcg-rewrite

        # Get tenant context
        request_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        tenant_id = None  # fcg-rewrite
        application_id = None  # fcg-rewrite
        if request_context:  # fcg-rewrite
            tenant_id = str(request_context['data'].get('tenant_id') or request_context['data'].get('tenant_id'))  # fcg-rewrite
            application_id = request_context['data'].get('application_id')  # fcg-rewrite

        if not tenant_id:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="Tenant ID not found in auth context")  # fcg-rewrite

        # Get user ID
        user_id = None  # fcg-rewrite
        if payload.extra_body:  # fcg-rewrite
            user_id = payload.extra_body.get('xxai_app_user_id')  # fcg-rewrite

        # If there is no user_id, use tenant_id as fallback
        if not user_id:  # fcg-rewrite
            user_id = tenant_id  # fcg-rewrite

        # Check if the user is banned
        await apply_ban_check(tenant_id, user_id)  # fcg-rewrite

        # Create guardrail service
        evaluation_service = GuardrailPipeline(db)  # fcg-rewrite

        # Execute detection (pass tenant_id and application_id)
        result = await evaluation_service.run_guardrail_check(  # fcg-rewrite
            payload,  # fcg-rewrite
            ip_address=ip_address,  # fcg-rewrite
            user_agent=user_agent,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id  # fcg-rewrite
        )

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
                    language=language  # fcg-rewrite
                )
                logger.info(f"Ban policy check completed for user_id={user_id}")  # fcg-rewrite
            except Exception as e:  # fcg-rewrite
                logger.error(f"Ban policy check failed for user_id={user_id}: {e}", exc_info=True)  # fcg-rewrite
        else:
            logger.info(f"Ban policy check skipped: risk_level={result.overall_risk_level}")  # fcg-rewrite

        logger.info(f"Guardrail check completed: {result.id}, action: {result.suggest_action}, user_id: {user_id}")  # fcg-rewrite

        return result  # fcg-rewrite

    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Guardrail API error: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Internal server error")  # fcg-rewrite

@router.get("/guardrails/health")  # fcg-rewrite
async def guardrail_healthcheck():  # fcg-rewrite
    """Guardrail service health check"""
    return {  # fcg-rewrite
        "status": "healthy",  # fcg-rewrite
        "service": "guardrails",  # fcg-rewrite
        "timestamp": "2025-01-01T00:00:00Z"  # fcg-rewrite
    }

@router.get("/guardrails/models")  # fcg-rewrite
async def list_guardrail_models():  # fcg-rewrite
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
async def inspect_input_guardrails(  # fcg-rewrite
    payload: InputGuardrailRequest,  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_proxy_db)  # fcg-rewrite
):
    """
    Input detection API - compatible with dify/coze etc. agent platform plugins

    Check if the input content exists security risks or compliance issues.
    Convert input to messages format for detection.
    """
    try:
        # Convert input to messages format
        chat_messages = [Message(role="user", content=payload.input)]  # fcg-rewrite

        # Construct standard GuardrailRequest
        normalized_request = GuardrailRequest(  # fcg-rewrite
            model=payload.model,  # fcg-rewrite
            messages=chat_messages  # fcg-rewrite
        )

        # Get client information
        ip_address = request.client.host if request.client else None  # fcg-rewrite
        user_agent = request.headers.get("user-agent")  # fcg-rewrite

        # Get tenant context
        request_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        tenant_id = None  # fcg-rewrite
        if request_context:  # fcg-rewrite
            tenant_id = str(request_context['data'].get('tenant_id') or request_context['data'].get('tenant_id'))  # fcg-rewrite

        if not tenant_id:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="Tenant ID not found in auth context")  # fcg-rewrite

        # Get user ID
        user_id = payload.xxai_app_user_id if payload.xxai_app_user_id else tenant_id  # fcg-rewrite

        # Check if the user is banned
        await apply_ban_check(tenant_id, user_id)  # fcg-rewrite

        # Create guardrail service
        evaluation_service = GuardrailPipeline(db)  # fcg-rewrite

        # Execute detection
        result = await evaluation_service.run_guardrail_check(  # fcg-rewrite
            normalized_request,  # fcg-rewrite
            ip_address=ip_address,  # fcg-rewrite
            user_agent=user_agent,  # fcg-rewrite
            tenant_id=tenant_id  # fcg-rewrite
        )

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
                    language=language  # fcg-rewrite
                )
                logger.info(f"Ban policy check completed for user_id={user_id}")  # fcg-rewrite
            except Exception as e:  # fcg-rewrite
                logger.error(f"Ban policy check failed for user_id={user_id}: {e}", exc_info=True)  # fcg-rewrite
        else:
            logger.info(f"Ban policy check skipped: risk_level={result.overall_risk_level}")  # fcg-rewrite

        logger.info(f"Input guardrail check completed: {result.id}, action: {result.suggest_action}, user_id: {user_id}")  # fcg-rewrite

        return result  # fcg-rewrite

    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Input guardrail API error: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Internal server error")  # fcg-rewrite

@router.post("/guardrails/output", response_model=GuardrailResponse)  # fcg-rewrite
async def inspect_output_guardrails(  # fcg-rewrite
    payload: OutputGuardrailRequest,  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_proxy_db)  # fcg-rewrite
):
    """
    Output detection API - compatible with dify/coze etc. agent platform plugins

    Check if the input and output content exists security risks or compliance issues.
    Convert input output to messages format for detection.
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

        # Get tenant context
        request_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        tenant_id = None  # fcg-rewrite
        if request_context:  # fcg-rewrite
            tenant_id = str(request_context['data'].get('tenant_id') or request_context['data'].get('tenant_id'))  # fcg-rewrite

        if not tenant_id:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="Tenant ID not found in auth context")  # fcg-rewrite

        # Get user ID
        user_id = payload.xxai_app_user_id if payload.xxai_app_user_id else tenant_id  # fcg-rewrite

        # Check if the user is banned
        await apply_ban_check(tenant_id, user_id)  # fcg-rewrite

        # Create guardrail service
        evaluation_service = GuardrailPipeline(db)  # fcg-rewrite

        # Execute detection
        result = await evaluation_service.run_guardrail_check(  # fcg-rewrite
            normalized_request,  # fcg-rewrite
            ip_address=ip_address,  # fcg-rewrite
            user_agent=user_agent,  # fcg-rewrite
            tenant_id=tenant_id  # fcg-rewrite
        )

        # Check and apply ban policy
        if result.overall_risk_level in ['中风险', '高风险']:  # fcg-rewrite
            # Get language setting
            language = get_language_from_request(request, tenant_id)  # fcg-rewrite
            await BanPolicyManager.check_and_apply_ban_policy(  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                user_id=user_id,  # fcg-rewrite
                risk_level=result.overall_risk_level,  # fcg-rewrite
                detection_result_id=result.id,  # fcg-rewrite
                language=language  # fcg-rewrite
            )

        logger.info(f"Output guardrail check completed: {result.id}, action: {result.suggest_action}, user_id: {user_id}")  # fcg-rewrite

        return result  # fcg-rewrite

    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Output guardrail API error: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Internal server error")  # fcg-rewrite


async def apply_ban_check(tenant_id: str, user_id: str):  # fcg-rewrite
    """Check if the user is banned, if banned, throw an exception"""
    if not user_id:  # fcg-rewrite
        return None  # fcg-rewrite

    ban_snapshot = await BanPolicyManager.check_user_banned(tenant_id, user_id)  # fcg-rewrite
    if ban_snapshot:  # fcg-rewrite
        ban_until = ban_snapshot['ban_until'].isoformat() if ban_snapshot['ban_until'] else ''  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=403,  # fcg-rewrite
            detail={  # fcg-rewrite
                "error": "User is banned",  # fcg-rewrite
                "user_id": user_id,  # fcg-rewrite
                "ban_until": ban_until,  # fcg-rewrite
                "reason": ban_snapshot.get('reason', 'Trigger ban policy')  # fcg-rewrite
            }
        )
    return None  # fcg-rewrite
