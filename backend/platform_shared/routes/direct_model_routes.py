"""OpenAI-compatible direct model access with privacy-aware usage tracking."""

from collections import defaultdict  # fcg-rewrite
from datetime import datetime, timedelta, timezone  # fcg-rewrite
from typing import Any, Dict, List, Optional, Union  # fcg-rewrite
import json  # fcg-rewrite
import uuid  # fcg-rewrite

import httpx  # fcg-rewrite
from fastapi import APIRouter, Depends, HTTPException, Request  # fcg-rewrite
from fastapi.responses import JSONResponse, StreamingResponse  # fcg-rewrite
from pydantic import BaseModel, Field  # fcg-rewrite

from config import settings  # fcg-rewrite
from database.connection import get_admin_db  # fcg-rewrite
from database.models import Application, DetectionResult, Tenant  # fcg-rewrite
from services.billing_service import BillingLedger  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Direct Model Access"])  # fcg-rewrite
billing_service = BillingLedger()  # fcg-rewrite


class ChatMessage(BaseModel):  # fcg-rewrite
    role: str  # fcg-rewrite
    content: Union[str, List[Dict[str, Any]]]  # fcg-rewrite


class ChatCompletionRequest(BaseModel):  # fcg-rewrite
    model: str  # fcg-rewrite
    messages: List[ChatMessage]  # fcg-rewrite
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2)  # fcg-rewrite
    top_p: Optional[float] = Field(default=0.9, ge=0, le=1)  # fcg-rewrite
    max_tokens: Optional[int] = Field(default=None, ge=1)  # fcg-rewrite
    stream: Optional[bool] = False  # fcg-rewrite
    frequency_penalty: Optional[float] = Field(default=0, ge=-2, le=2)  # fcg-rewrite
    presence_penalty: Optional[float] = Field(default=0, ge=-2, le=2)  # fcg-rewrite
    stop: Optional[Union[str, List[str]]] = None  # fcg-rewrite
    n: Optional[int] = Field(default=1, ge=1)  # fcg-rewrite


class EmbeddingRequest(BaseModel):  # fcg-rewrite
    model: str  # fcg-rewrite
    input: Union[str, List[str]]  # fcg-rewrite
    encoding_format: Optional[str] = "float"  # fcg-rewrite
    dimensions: Optional[int] = None  # fcg-rewrite
    user: Optional[str] = None  # fcg-rewrite


def _bearer_token(request: Request) -> str:  # fcg-rewrite
    header = request.headers.get("authorization", "")  # fcg-rewrite
    if not header.startswith("Bearer "):  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=401,  # fcg-rewrite
            detail="Missing or invalid Authorization header. Expected: Bearer sk-xxai-model-...",  # fcg-rewrite
        )
    token = header.removeprefix("Bearer ")  # fcg-rewrite
    if not token.startswith("sk-xxai-model-"):  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Invalid model API key format. Expected: sk-xxai-model-...")  # fcg-rewrite
    return token  # fcg-rewrite


def _check_subscription(db, tenant: Tenant) -> None:  # fcg-rewrite
    if not settings.is_saas_mode or tenant.is_super_admin:  # fcg-rewrite
        return
    subscription = billing_service.get_subscription(str(tenant.id), db)  # fcg-rewrite
    if not subscription or subscription.subscription_type != "subscribed":  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=403,  # fcg-rewrite
            detail="Direct model access requires an active subscription. Please subscribe at the platform.",  # fcg-rewrite
        )
    if subscription.subscription_expires_at and subscription.subscription_expires_at < datetime.now(timezone.utc):  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=403,  # fcg-rewrite
            detail="Your subscription has expired. Please renew your subscription to continue using direct model access.",  # fcg-rewrite
        )
    allowed, error = billing_service.check_and_increment_usage(str(tenant.id), db)  # fcg-rewrite
    if not allowed:  # fcg-rewrite
        raise HTTPException(status_code=429, detail=error)  # fcg-rewrite


async def require_model_key(request: Request) -> dict:  # fcg-rewrite
    token = _bearer_token(request)  # fcg-rewrite
    db = next(get_admin_db())  # fcg-rewrite
    try:
        tenant = db.query(Tenant).filter(Tenant.model_api_key == token).first()  # fcg-rewrite
        if not tenant:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="Invalid model API key")  # fcg-rewrite
        _check_subscription(db, tenant)  # fcg-rewrite
        return {"tenant_id": str(tenant.id), "email": tenant.email, "model_api_key": token}  # fcg-rewrite
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite


def _injection_risk(model_name: str, response_content: Optional[str]) -> tuple[str, list[str], str]:  # fcg-rewrite
    aliases = ("fangcunguard-text", "guardrails-text", "og-text")  # fcg-rewrite
    if not response_content or not any(alias in model_name.lower() for alias in aliases):  # fcg-rewrite
        return "no_risk", [], "pass"  # fcg-rewrite
    try:
        result = json.loads(response_content)  # fcg-rewrite
        if not result.get("isInjection", False):  # fcg-rewrite
            return "no_risk", [], "pass"  # fcg-rewrite
        categories = ["Prompt Attacks"]  # fcg-rewrite
        for finding in result.get("findings", [])[:3]:  # fcg-rewrite
            suspicious = finding.get("suspiciousContent", "")  # fcg-rewrite
            if suspicious:  # fcg-rewrite
                categories.append(f"Suspicious: {suspicious[:50]}")  # fcg-rewrite
        return "high_risk", categories, "reject"  # fcg-rewrite
    except (json.JSONDecodeError, AttributeError, TypeError):  # fcg-rewrite
        return "no_risk", [], "pass"  # fcg-rewrite


def _dma_application(db, tenant_id: str):  # fcg-rewrite
    application = db.query(Application).filter(  # fcg-rewrite
        Application.tenant_id == tenant_id, Application.source == "direct_model_access"  # fcg-rewrite
    ).first()  # fcg-rewrite
    if application:  # fcg-rewrite
        return application.id  # fcg-rewrite
    application = Application(  # fcg-rewrite
        tenant_id=tenant_id,  # fcg-rewrite
        name="Direct Model Access",  # fcg-rewrite
        description="Auto-created application for direct model access calls",  # fcg-rewrite
        source="direct_model_access",  # fcg-rewrite
        is_active=True,  # fcg-rewrite
    )
    db.add(application)  # fcg-rewrite
    db.flush()  # fcg-rewrite
    return application.id  # fcg-rewrite


async def log_direct_access(  # fcg-rewrite
    tenant_id: str,  # fcg-rewrite
    model_name: str,  # fcg-rewrite
    request_content: str,  # fcg-rewrite
    response_content: Optional[str] = None,  # fcg-rewrite
    ip_address: Optional[str] = None,  # fcg-rewrite
    user_agent: Optional[str] = None,  # fcg-rewrite
):
    """Persist one usage row while storing full content only when the tenant opts in."""
    db = next(get_admin_db())  # fcg-rewrite
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()  # fcg-rewrite
        if not tenant:  # fcg-rewrite
            logger.warning("Tenant %s not found when tracking DMA", tenant_id)  # fcg-rewrite
            return
        risk, categories, action = _injection_risk(model_name, response_content)  # fcg-rewrite
        full_logging = tenant.log_direct_model_access  # fcg-rewrite
        content = request_content if full_logging else f"[Direct Model Access: {model_name}]"  # fcg-rewrite
        model_response = response_content or "" if full_logging else ""  # fcg-rewrite
        try:
            application_id = _dma_application(db, tenant_id)  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.warning("DMA application lookup failed for %s: %s", tenant_id, exc)  # fcg-rewrite
            application_id = None  # fcg-rewrite
        db.add(DetectionResult(  # fcg-rewrite
            request_id=str(uuid.uuid4()),  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            content=content,  # fcg-rewrite
            is_direct_model_access=True,  # fcg-rewrite
            suggest_action=action,  # fcg-rewrite
            suggest_answer=None,  # fcg-rewrite
            hit_keywords=None,  # fcg-rewrite
            model_response=model_response,  # fcg-rewrite
            security_risk_level=risk,  # fcg-rewrite
            security_categories=categories,  # fcg-rewrite
            compliance_risk_level="no_risk",  # fcg-rewrite
            compliance_categories=[],  # fcg-rewrite
            data_risk_level="no_risk",  # fcg-rewrite
            data_categories=[],  # fcg-rewrite
            has_image=False,  # fcg-rewrite
            image_count=0,  # fcg-rewrite
            image_paths=[],  # fcg-rewrite
            ip_address=ip_address,  # fcg-rewrite
            user_agent=user_agent,  # fcg-rewrite
        ))
        db.commit()  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        logger.error("Failed to track direct model access: %s", exc)  # fcg-rewrite
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite


def resolve_model_backend(model_name: str) -> dict:  # fcg-rewrite
    lowered = model_name.lower()  # fcg-rewrite
    choices = (  # fcg-rewrite
        (("fangcunguard-vl", "guardrails-vl", "og-vl"), "guardrails_vl_model_api_url", "guardrails_vl_model_api_key", "guardrails_vl_model_name"),  # fcg-rewrite
        (("bge-m3", "bge", "embedding"), "embedding_api_base_url", "embedding_api_key", "embedding_model_name"),  # fcg-rewrite
    )
    for aliases, url, key, configured_name in choices:  # fcg-rewrite
        if any(alias in lowered for alias in aliases):  # fcg-rewrite
            return {"api_url": getattr(settings, url), "api_key": getattr(settings, key), "model_name": getattr(settings, configured_name)}  # fcg-rewrite
    return {  # fcg-rewrite
        "api_url": settings.guardrails_model_api_url,  # fcg-rewrite
        "api_key": settings.guardrails_model_api_key,  # fcg-rewrite
        "model_name": settings.guardrails_model_name,  # fcg-rewrite
    }


def _upstream_headers(backend: dict) -> dict:  # fcg-rewrite
    return {"Authorization": f"Bearer {backend['api_key']}", "Content-Type": "application/json"}  # fcg-rewrite


def _chat_payload(request: ChatCompletionRequest) -> dict:  # fcg-rewrite
    payload = {  # fcg-rewrite
        "model": request.model,  # fcg-rewrite
        "messages": [{"role": message.role, "content": message.content} for message in request.messages],  # fcg-rewrite
        "temperature": request.temperature,  # fcg-rewrite
        "top_p": request.top_p,  # fcg-rewrite
        "stream": request.stream,  # fcg-rewrite
    }
    for name in ("max_tokens", "frequency_penalty", "presence_penalty", "stop", "n"):  # fcg-rewrite
        value = getattr(request, name)  # fcg-rewrite
        if value:  # fcg-rewrite
            payload[name] = value  # fcg-rewrite
    return payload  # fcg-rewrite


def _request_metadata(request: Request) -> tuple[Optional[str], Optional[str]]:  # fcg-rewrite
    return (request.client.host if request.client else None, request.headers.get("user-agent"))  # fcg-rewrite


def _messages_text(messages: List[ChatMessage]) -> str:  # fcg-rewrite
    return " ".join(f"{message.role}: {message.content}" for message in messages)  # fcg-rewrite


def _raise_upstream_error(exc: Exception, label: str, connection_label: str):  # fcg-rewrite
    if isinstance(exc, httpx.HTTPStatusError):  # fcg-rewrite
        raise HTTPException(status_code=exc.response.status_code, detail=f"{label} error: {exc.response.text}") from exc  # fcg-rewrite
    if isinstance(exc, httpx.RequestError):  # fcg-rewrite
        raise HTTPException(status_code=503, detail=f"Failed to connect to {connection_label} API: {exc}") from exc  # fcg-rewrite
    raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc  # fcg-rewrite


@router.post("/model/")  # fcg-rewrite
@router.post("/model/chat/completions")  # fcg-rewrite
async def model_chat_completions(  # fcg-rewrite
    request_data: ChatCompletionRequest,  # fcg-rewrite
    request: Request,  # fcg-rewrite
    auth_context: dict = Depends(require_model_key),  # fcg-rewrite
):
    tenant_id = auth_context["tenant_id"]  # fcg-rewrite
    backend = resolve_model_backend(request_data.model)  # fcg-rewrite
    url = f"{backend['api_url']}/chat/completions"  # fcg-rewrite
    headers = _upstream_headers(backend)  # fcg-rewrite
    payload = _chat_payload(request_data)  # fcg-rewrite
    ip_address, user_agent = _request_metadata(request)  # fcg-rewrite
    try:
        if request_data.stream:  # fcg-rewrite
            async def stream_response():  # fcg-rewrite
                chunks = []  # fcg-rewrite
                async with httpx.AsyncClient(timeout=120.0) as client:  # fcg-rewrite
                    async with client.stream("POST", url, json=payload, headers=headers) as response:  # fcg-rewrite
                        response.raise_for_status()  # fcg-rewrite
                        async for chunk in response.aiter_text():  # fcg-rewrite
                            if chunk.strip():  # fcg-rewrite
                                chunks.append(chunk)  # fcg-rewrite
                                yield chunk  # fcg-rewrite
                await log_direct_access(  # fcg-rewrite
                    tenant_id,  # fcg-rewrite
                    request_data.model,  # fcg-rewrite
                    f"[Streaming] {_messages_text(request_data.messages)}",  # fcg-rewrite
                    "".join(chunks),  # fcg-rewrite
                    ip_address,  # fcg-rewrite
                    user_agent,  # fcg-rewrite
                )
            return StreamingResponse(stream_response(), media_type="text/event-stream")  # fcg-rewrite

        async with httpx.AsyncClient(timeout=120.0) as client:  # fcg-rewrite
            response = await client.post(url, json=payload, headers=headers)  # fcg-rewrite
            response.raise_for_status()  # fcg-rewrite
            data = response.json()  # fcg-rewrite
        choices = data.get("choices", [])  # fcg-rewrite
        content = choices[0].get("message", {}).get("content", "") if choices else ""  # fcg-rewrite
        await log_direct_access(  # fcg-rewrite
            tenant_id, request_data.model, _messages_text(request_data.messages), content, ip_address, user_agent  # fcg-rewrite
        )
        return JSONResponse(content=data)  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        _raise_upstream_error(exc, "Model API", "model")  # fcg-rewrite


@router.post("/model/embeddings")  # fcg-rewrite
async def model_embeddings(  # fcg-rewrite
    request_data: EmbeddingRequest,  # fcg-rewrite
    request: Request,  # fcg-rewrite
    auth_context: dict = Depends(require_model_key),  # fcg-rewrite
):
    backend = resolve_model_backend(request_data.model)  # fcg-rewrite
    payload = {"model": request_data.model, "input": request_data.input}  # fcg-rewrite
    for name in ("encoding_format", "dimensions", "user"):  # fcg-rewrite
        value = getattr(request_data, name)  # fcg-rewrite
        if value:  # fcg-rewrite
            payload[name] = value  # fcg-rewrite
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:  # fcg-rewrite
            response = await client.post(  # fcg-rewrite
                f"{backend['api_url']}/embeddings", json=payload, headers=_upstream_headers(backend)  # fcg-rewrite
            )
            response.raise_for_status()  # fcg-rewrite
            data = response.json()  # fcg-rewrite
        ip_address, user_agent = _request_metadata(request)  # fcg-rewrite
        await log_direct_access(  # fcg-rewrite
            auth_context["tenant_id"],  # fcg-rewrite
            request_data.model,  # fcg-rewrite
            f"[Embeddings] {request_data.input}",  # fcg-rewrite
            "[Embedding vectors]",  # fcg-rewrite
            ip_address,  # fcg-rewrite
            user_agent,  # fcg-rewrite
        )
        return JSONResponse(content=data)  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        _raise_upstream_error(exc, "Embedding API", "embedding")  # fcg-rewrite


def _parse_date(raw: Optional[str], field: str) -> Optional[datetime]:  # fcg-rewrite
    if not raw:  # fcg-rewrite
        return None  # fcg-rewrite
    try:
        return datetime.fromisoformat(raw)  # fcg-rewrite
    except ValueError as exc:  # fcg-rewrite
        raise HTTPException(status_code=400, detail=f"Invalid {field} format. Use YYYY-MM-DD") from exc  # fcg-rewrite


@router.get("/model/usage")  # fcg-rewrite
async def get_model_usage(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    auth_context: dict = Depends(require_model_key),  # fcg-rewrite
    start_date: Optional[str] = None,  # fcg-rewrite
    end_date: Optional[str] = None,  # fcg-rewrite
):
    tenant_id = auth_context["tenant_id"]  # fcg-rewrite
    db = next(get_admin_db())  # fcg-rewrite
    try:
        query = db.query(DetectionResult).filter(  # fcg-rewrite
            DetectionResult.tenant_id == tenant_id,  # fcg-rewrite
            DetectionResult.is_direct_model_access == True,  # fcg-rewrite
        )
        start = _parse_date(start_date, "start_date")  # fcg-rewrite
        end = _parse_date(end_date, "end_date")  # fcg-rewrite
        if start:  # fcg-rewrite
            query = query.filter(DetectionResult.created_at >= start)  # fcg-rewrite
        if end:
            query = query.filter(DetectionResult.created_at < end + timedelta(days=1))  # fcg-rewrite
        records = query.order_by(DetectionResult.created_at.desc()).all()  # fcg-rewrite
        counts = defaultdict(int)  # fcg-rewrite
        for record in records:  # fcg-rewrite
            counts[record.created_at.date().isoformat()] += 1  # fcg-rewrite
        return {  # fcg-rewrite
            "tenant_id": tenant_id,  # fcg-rewrite
            "start_date": start_date,  # fcg-rewrite
            "end_date": end_date,  # fcg-rewrite
            "total_requests": len(records),  # fcg-rewrite
            "usage_by_day": [  # fcg-rewrite
                {"date": day, "request_count": count}  # fcg-rewrite
                for day, count in sorted(counts.items(), reverse=True)  # fcg-rewrite
            ],
        }
    finally:  # fcg-rewrite
        db.close()  # fcg-rewrite
