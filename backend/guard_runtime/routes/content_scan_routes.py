"""
Content Scan Router - API endpoints for email and webpage content scanning

Endpoints:
  POST /scan/email   - Scan email (EML) content for risks
  POST /scan/webpage - Scan webpage content for risks
"""
from datetime import datetime, timezone  # fcg-rewrite

from fastapi import APIRouter, Request, HTTPException  # fcg-rewrite

from models.scan_models import EmailScanRequest, WebpageScanRequest, ScanResponse  # fcg-rewrite
from services.content_scan_service import content_scan_service  # fcg-rewrite
from services.async_logger import async_detection_logger  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Content Scan"])  # fcg-rewrite


@router.post("/scan/email", response_model=ScanResponse)  # fcg-rewrite
async def scan_email(request_data: EmailScanRequest, request: Request):  # fcg-rewrite
    """
    Scan email content for security risks.

    Detects: prompt injection, jailbreak, phishing, malware
    """
    auth_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
    if not auth_context:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite

    tenant_id = auth_context['data'].get('tenant_id')  # fcg-rewrite
    application_id = auth_context['data'].get('application_id')  # fcg-rewrite
    ip_address = request.client.host if request.client else None  # fcg-rewrite
    user_agent = request.headers.get("user-agent")  # fcg-rewrite

    result = await content_scan_service.scan_email(request_data.content)  # fcg-rewrite

    # Async logging
    await _persist_scan_outcome(  # fcg-rewrite
        result=result,  # fcg-rewrite
        content=request_data.content,  # fcg-rewrite
        tenant_id=tenant_id,  # fcg-rewrite
        application_id=application_id,  # fcg-rewrite
        ip_address=ip_address,  # fcg-rewrite
        user_agent=user_agent,  # fcg-rewrite
    )

    return ScanResponse(**result)  # fcg-rewrite


@router.post("/scan/webpage", response_model=ScanResponse)  # fcg-rewrite
async def scan_webpage(request_data: WebpageScanRequest, request: Request):  # fcg-rewrite
    """
    Scan webpage content for security risks.

    Detects: prompt injection, jailbreak, phishing, malware
    """
    auth_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
    if not auth_context:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite

    tenant_id = auth_context['data'].get('tenant_id')  # fcg-rewrite
    application_id = auth_context['data'].get('application_id')  # fcg-rewrite
    ip_address = request.client.host if request.client else None  # fcg-rewrite
    user_agent = request.headers.get("user-agent")  # fcg-rewrite

    result = await content_scan_service.scan_webpage(request_data.content, request_data.url)  # fcg-rewrite

    # Async logging
    await _persist_scan_outcome(  # fcg-rewrite
        result=result,  # fcg-rewrite
        content=request_data.content,  # fcg-rewrite
        tenant_id=tenant_id,  # fcg-rewrite
        application_id=application_id,  # fcg-rewrite
        ip_address=ip_address,  # fcg-rewrite
        user_agent=user_agent,  # fcg-rewrite
        url=request_data.url,  # fcg-rewrite
    )

    return ScanResponse(**result)  # fcg-rewrite


async def _persist_scan_outcome(  # fcg-rewrite
    result: dict,  # fcg-rewrite
    content: str,  # fcg-rewrite
    tenant_id: str,  # fcg-rewrite
    application_id: str,  # fcg-rewrite
    ip_address: str,  # fcg-rewrite
    user_agent: str,  # fcg-rewrite
    url: str = None,  # fcg-rewrite
):
    """Log scan result asynchronously."""
    try:
        detection_data = {  # fcg-rewrite
            "request_id": result["id"],  # fcg-rewrite
            "tenant_id": tenant_id,  # fcg-rewrite
            "application_id": application_id,  # fcg-rewrite
            "content": content[:10000],  # Truncate for logging  # fcg-rewrite
            "scan_type": result["scan_type"],  # fcg-rewrite
            "risk_level": result["risk_level"],  # fcg-rewrite
            "risk_types": result["risk_types"],  # fcg-rewrite
            "risk_content": result["risk_content"],  # fcg-rewrite
            "score": result["score"],  # fcg-rewrite
            "suggest_action": "block" if result["risk_level"] == "high" else "pass",  # fcg-rewrite
            "ip_address": ip_address,  # fcg-rewrite
            "user_agent": user_agent,  # fcg-rewrite
            "url": url,  # fcg-rewrite
            "created_at": datetime.now(timezone.utc).isoformat(),  # fcg-rewrite
        }
        await async_detection_logger.log_detection(detection_data)  # fcg-rewrite
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to log scan result: {e}")  # fcg-rewrite
