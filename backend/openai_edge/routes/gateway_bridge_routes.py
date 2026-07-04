"""
Gateway Integration API

Provides unified API endpoints for third-party AI gateways (Higress, LiteLLM, Kong, etc.)
to integrate FangcunGuard' full security capabilities.

Endpoints:
- POST /v1/gateway/process-input  - Process incoming messages through detection pipeline
- POST /v1/gateway/process-output - Process LLM output with restoration

See docs/THIRD_PARTY_GATEWAY_INTEGRATION.md for full documentation.
"""

from fastapi import APIRouter, HTTPException, Request, Depends  # fcg-rewrite
from fastapi.responses import JSONResponse  # fcg-rewrite
from pydantic import BaseModel, Field  # fcg-rewrite
from typing import Dict, Any, Optional, List  # fcg-rewrite
import time  # fcg-rewrite

from database.connection import get_db  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite
from services.gateway_integration_service import wire_gateway_bridge  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite
from utils.bypass_token import parse_bypass_token, read_bypass_token  # fcg-rewrite

router = APIRouter(prefix="/v1/gateway", tags=["Gateway Integration"])  # fcg-rewrite
logger = setup_logger()  # fcg-rewrite


class ProcessInputRequest(BaseModel):  # fcg-rewrite
    """Request model for process-input endpoint"""
    messages: List[Dict[str, Any]] = Field(..., description="OpenAI-format messages array")  # fcg-rewrite
    stream: bool = Field(default=False, description="Whether the request is for streaming response")  # fcg-rewrite
    client_ip: Optional[str] = Field(default=None, description="Client IP address for ban policy")  # fcg-rewrite
    user_id: Optional[str] = Field(default=None, description="User identifier for ban policy")  # fcg-rewrite

    class Config:  # fcg-rewrite
        json_schema_extra = {  # fcg-rewrite
            "example": {  # fcg-rewrite
                "messages": [  # fcg-rewrite
                    {"role": "user", "content": "My email is john@example.com"}  # fcg-rewrite
                ],
                "stream": False  # fcg-rewrite
            }
        }


class ProcessOutputRequest(BaseModel):  # fcg-rewrite
    """Request model for process-output endpoint"""
    content: str = Field(..., description="LLM response content")  # fcg-rewrite
    session_id: Optional[str] = Field(default=None, description="Session ID from process-input for restoration (deprecated, use restore_mapping instead)")  # fcg-rewrite
    restore_mapping: Optional[Dict[str, str]] = Field(default=None, description="Mapping of placeholders to original values (e.g., {'__email_1__': 'john@example.com'})")  # fcg-rewrite
    is_streaming: bool = Field(default=False, description="Whether this is a streaming chunk")  # fcg-rewrite
    chunk_index: int = Field(default=0, description="Chunk index for streaming (0-based)")  # fcg-rewrite
    messages: Optional[List[Dict[str, Any]]] = Field(default=None, description="Input messages as context for output detection")  # fcg-rewrite

    class Config:  # fcg-rewrite
        json_schema_extra = {  # fcg-rewrite
            "example": {  # fcg-rewrite
                "content": "I have received your email __email_1__",  # fcg-rewrite
                "restore_mapping": {"__email_1__": "john@example.com"},  # fcg-rewrite
                "messages": [{"role": "user", "content": "My email is john@example.com"}]  # fcg-rewrite
            }
        }


def auth_ids_from_request(request: Request) -> Dict[str, str]:  # fcg-rewrite
    """Extract tenant_id and application_id from request auth context"""
    auth_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
    if not auth_context:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=401,  # fcg-rewrite
            detail={"error": {"message": "Authentication required", "type": "authentication_error"}}  # fcg-rewrite
        )

    # Auth context structure: {"type": "...", "data": {"tenant_id": "...", "application_id": "...", ...}}
    data = auth_context.get('data', {})  # fcg-rewrite
    tenant_id = data.get('tenant_id')  # fcg-rewrite
    application_id = data.get('application_id')  # fcg-rewrite

    if not tenant_id or not application_id:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=401,  # fcg-rewrite
            detail={"error": {"message": "Invalid API key - must use application API key", "type": "authentication_error"}}  # fcg-rewrite
        )

    return {"tenant_id": tenant_id, "application_id": application_id}  # fcg-rewrite


def elapsed_ms(start_time: float) -> float:  # fcg-rewrite
    """Return elapsed milliseconds from a ``time.time()`` value."""
    return round((time.time() - start_time) * 1000, 2)  # fcg-rewrite


@router.post("/process-input")  # fcg-rewrite
async def gate_inbound_traffic(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    payload: ProcessInputRequest,  # fcg-rewrite
    db: Session = Depends(get_db)  # fcg-rewrite
):
    """
    Process incoming messages through FangcunGuard' full detection pipeline.

    Authentication: Use application API key (Bearer sk-xxai-xxx).
    The application_id is automatically extracted from the API key.

    This endpoint performs:
    1. Ban policy check (user/IP)
    2. Blacklist/Whitelist keyword check
    3. Data leakage prevention (DLP) detection
    4. Security/Compliance scanning (21 risk categories)
    5. Risk aggregation and disposition decision

    Returns an action and any necessary data for the gateway to execute:
    - **block**: Return error response to client
    - **replace**: Return knowledge base / template response
    - **anonymize**: Forward anonymized messages to LLM
    - **switch_private_model**: Redirect to private/on-premise model
    - **pass**: Forward request as-is
    """
    start_time = time.time()  # fcg-rewrite

    # Check for bypass token (skip detection for private model requests)
    bypass_token = read_bypass_token(request.headers)  # fcg-rewrite
    if bypass_token:  # fcg-rewrite
        is_valid, token_tenant_id, token_request_id = parse_bypass_token(bypass_token)  # fcg-rewrite
        if is_valid:  # fcg-rewrite
            logger.info(f"Bypass token valid: tenant={token_tenant_id}, request={token_request_id}, skipping detection")  # fcg-rewrite
            return JSONResponse(content={  # fcg-rewrite
                "action": "pass",  # fcg-rewrite
                "request_id": f"bypass-{token_request_id}",  # fcg-rewrite
                "detection_result": {  # fcg-rewrite
                    "bypassed": True,  # fcg-rewrite
                    "original_request_id": token_request_id,  # fcg-rewrite
                    "overall_risk_level": "no_risk"  # fcg-rewrite
                },
                "processing_time_ms": elapsed_ms(start_time)  # fcg-rewrite
            })
        else:
            logger.warning(f"Invalid bypass token received, proceeding with normal detection")  # fcg-rewrite

    # Get tenant_id and application_id from API key
    auth_info = auth_ids_from_request(request)  # fcg-rewrite
    tenant_id = auth_info["tenant_id"]  # fcg-rewrite
    application_id = auth_info["application_id"]  # fcg-rewrite

    # Debug: log received messages
    logger.info(f"Gateway process-input received: messages_count={len(payload.messages)}, stream={payload.stream}")  # fcg-rewrite
    if payload.messages:  # fcg-rewrite
        for i, msg in enumerate(payload.messages):  # fcg-rewrite
            logger.info(f"  Message {i}: role={msg.get('role')}, content_len={len(str(msg.get('content', '')))}, content_preview={str(msg.get('content', ''))[:100]}")  # fcg-rewrite

    service = wire_gateway_bridge(db)  # fcg-rewrite

    result = await service.gate_inbound_traffic(  # fcg-rewrite
        application_id=application_id,  # fcg-rewrite
        tenant_id=tenant_id,  # fcg-rewrite
        messages=payload.messages,  # fcg-rewrite
        stream=payload.stream,  # fcg-rewrite
        client_ip=payload.client_ip,  # fcg-rewrite
        user_id=payload.user_id  # fcg-rewrite
    )

    result["processing_time_ms"] = elapsed_ms(start_time)  # fcg-rewrite

    logger.info(  # fcg-rewrite
        f"Gateway process-input: app={application_id[:8]}..., "  # fcg-rewrite
        f"action={result.get('action')}, "  # fcg-rewrite
        f"risk={result.get('detection_result', {}).get('overall_risk_level', 'unknown')}, "  # fcg-rewrite
        f"time={result['processing_time_ms']}ms"  # fcg-rewrite
    )

    return JSONResponse(content=result)  # fcg-rewrite


@router.post("/process-output")  # fcg-rewrite
async def gate_outbound_traffic(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    payload: ProcessOutputRequest,  # fcg-rewrite
    db: Session = Depends(get_db)  # fcg-rewrite
):
    """
    Process LLM output through detection and optionally restore anonymized data.

    Authentication: Use application API key (Bearer sk-xxai-xxx).
    The application_id is automatically extracted from the API key.

    This endpoint:
    1. Restores anonymized placeholders if session_id is provided
    2. Runs output detection for security/compliance risks
    3. Returns appropriate action and content

    Returns:
    - **block**: Output contains security risk, return error
    - **replace**: Output contains compliance risk, return template
    - **restore**: Return restored content (anonymized placeholders replaced with originals)
    - **pass**: Return content as-is
    """
    start_time = time.time()  # fcg-rewrite

    # Get tenant_id and application_id from API key
    auth_info = auth_ids_from_request(request)  # fcg-rewrite
    tenant_id = auth_info["tenant_id"]  # fcg-rewrite
    application_id = auth_info["application_id"]  # fcg-rewrite

    service = wire_gateway_bridge(db)  # fcg-rewrite

    result = await service.gate_outbound_traffic(  # fcg-rewrite
        application_id=application_id,  # fcg-rewrite
        tenant_id=tenant_id,  # fcg-rewrite
        content=payload.content,  # fcg-rewrite
        session_id=payload.session_id,  # fcg-rewrite
        restore_mapping=payload.restore_mapping,  # fcg-rewrite
        is_streaming=payload.is_streaming,  # fcg-rewrite
        chunk_index=payload.chunk_index,  # fcg-rewrite
        input_messages=payload.messages  # fcg-rewrite
    )

    result["processing_time_ms"] = elapsed_ms(start_time)  # fcg-rewrite

    logger.info(  # fcg-rewrite
        f"Gateway process-output: app={application_id[:8]}..., "  # fcg-rewrite
        f"action={result.get('action')}, "  # fcg-rewrite
        f"session={'yes' if payload.session_id else 'no'}, "  # fcg-rewrite
        f"time={result['processing_time_ms']}ms"  # fcg-rewrite
    )

    return JSONResponse(content=result)  # fcg-rewrite


@router.get("/health")  # fcg-rewrite
async def health_check():  # fcg-rewrite
    """Health check endpoint for gateway integration"""
    return {"status": "healthy", "service": "gateway-integration", "version": "1.0.0"}  # fcg-rewrite
