"""Interactive guardrail and upstream-model comparison endpoints."""

from typing import Any, Dict, List, Optional, Tuple  # fcg-rewrite
import asyncio  # fcg-rewrite
import uuid  # fcg-rewrite

import httpx  # fcg-rewrite
from fastapi import APIRouter, Depends, HTTPException, Request  # fcg-rewrite
from openai import AsyncOpenAI  # fcg-rewrite
from pydantic import BaseModel, ConfigDict, Field  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from config import settings  # fcg-rewrite
from database.connection import get_admin_db  # fcg-rewrite
from database.models import Application, OnlineTestModelSelection, Tenant, UpstreamApiConfig  # fcg-rewrite
from services.billing_service import billing_service  # fcg-rewrite
from services.proxy_service import proxy_service  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Online Test"])  # fcg-rewrite


def check_image_detection_subscription(tenant_uuid: uuid.UUID, db: Session) -> Tuple[bool, Optional[str]]:  # fcg-rewrite
    try:
        subscription = billing_service.get_subscription(str(tenant_uuid), db)  # fcg-rewrite
        if not subscription:  # fcg-rewrite
            return False, "Subscription not found. Please contact support to enable image detection."  # fcg-rewrite
        if subscription.subscription_type != "subscribed":  # fcg-rewrite
            return False, "Image detection is only available for subscribed users. Please upgrade your plan to access this feature."  # fcg-rewrite
        return True, None  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.error("Image subscription check failed for %s: %s", tenant_uuid, exc)  # fcg-rewrite
        return True, None  # fcg-rewrite


class ModelConfig(BaseModel):  # fcg-rewrite
    id: str
    name: str  # fcg-rewrite
    base_url: str  # fcg-rewrite
    api_key: str  # fcg-rewrite
    model_name: str  # fcg-rewrite
    enabled: bool = True  # fcg-rewrite
    model_config = ConfigDict(protected_namespaces=())  # fcg-rewrite


class ModelIdRequest(BaseModel):  # fcg-rewrite
    id: int
    enabled: bool = True  # fcg-rewrite


class OnlineTestRequest(BaseModel):  # fcg-rewrite
    content: str  # fcg-rewrite
    input_type: str  # fcg-rewrite
    models: Optional[List[ModelIdRequest]] = Field(default_factory=list)  # fcg-rewrite
    images: Optional[List[str]] = Field(default_factory=list)  # fcg-rewrite


class ModelResponse(BaseModel):  # fcg-rewrite
    content: Optional[str] = None  # fcg-rewrite
    error: Optional[str] = None  # fcg-rewrite


class OnlineTestResponse(BaseModel):  # fcg-rewrite
    guardrail: Dict[str, Any]  # fcg-rewrite
    models: Dict[str, ModelResponse] = Field(default_factory=dict)  # fcg-rewrite
    original_responses: Dict[str, ModelResponse] = Field(default_factory=dict)  # fcg-rewrite


class OnlineTestModelInfo(BaseModel):  # fcg-rewrite
    id: str
    config_name: str  # fcg-rewrite
    api_base_url: str  # fcg-rewrite
    provider: Optional[str] = None  # fcg-rewrite
    is_active: bool  # fcg-rewrite
    selected: bool = False  # fcg-rewrite
    model_name: Optional[str] = None  # fcg-rewrite
    model_config = ConfigDict(protected_namespaces=())  # fcg-rewrite


class UpdateModelSelectionRequest(BaseModel):  # fcg-rewrite
    model_selections: List[Dict[str, Any]]  # fcg-rewrite
    model_config = ConfigDict(protected_namespaces=())  # fcg-rewrite


def _auth_context(request: Request) -> dict:  # fcg-rewrite
    context = getattr(request.state, "auth_context", None)  # fcg-rewrite
    if not context or not context.get("data", {}).get("tenant_id"):  # fcg-rewrite
        raise HTTPException(status_code=401, detail="User ID not found in auth context")  # fcg-rewrite
    return context  # fcg-rewrite


def _tenant_uuid(request: Request) -> uuid.UUID:  # fcg-rewrite
    try:
        return uuid.UUID(str(_auth_context(request)["data"]["tenant_id"]))  # fcg-rewrite
    except ValueError as exc:  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Invalid user ID format") from exc  # fcg-rewrite


@router.get("/test/models", response_model=List[OnlineTestModelInfo])  # fcg-rewrite
async def get_online_test_models(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    try:
        tenant_id = _tenant_uuid(request)  # fcg-rewrite
        models = db.query(UpstreamApiConfig).filter(  # fcg-rewrite
            UpstreamApiConfig.tenant_id == tenant_id, UpstreamApiConfig.is_active == True  # fcg-rewrite
        ).all()
        selections = db.query(OnlineTestModelSelection).filter(  # fcg-rewrite
            OnlineTestModelSelection.tenant_id == tenant_id  # fcg-rewrite
        ).all()
        selected = {  # fcg-rewrite
            str(item.proxy_model_id): {"selected": item.selected, "model_name": item.model_name}  # fcg-rewrite
            for item in selections  # fcg-rewrite
        }
        return [  # fcg-rewrite
            OnlineTestModelInfo(  # fcg-rewrite
                id=str(model.id),  # fcg-rewrite
                config_name=model.config_name,  # fcg-rewrite
                api_base_url=model.api_base_url,  # fcg-rewrite
                provider=model.provider,  # fcg-rewrite
                is_active=model.is_active,  # fcg-rewrite
                **selected.get(str(model.id), {"selected": False, "model_name": None}),  # fcg-rewrite
            )
            for model in models  # fcg-rewrite
        ]
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Get model list failed: {exc}") from exc  # fcg-rewrite


@router.post("/test/models/selection")  # fcg-rewrite
async def update_model_selection(  # fcg-rewrite
    request_data: UpdateModelSelectionRequest, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    try:
        tenant_id = _tenant_uuid(request)  # fcg-rewrite
        for item in request_data.model_selections:  # fcg-rewrite
            try:
                model_id = uuid.UUID(item["id"])  # fcg-rewrite
            except (ValueError, KeyError):  # fcg-rewrite
                continue  # fcg-rewrite
            if not db.query(UpstreamApiConfig).filter(  # fcg-rewrite
                UpstreamApiConfig.id == model_id, UpstreamApiConfig.tenant_id == tenant_id  # fcg-rewrite
            ).first():  # fcg-rewrite
                continue  # fcg-rewrite
            selection = db.query(OnlineTestModelSelection).filter(  # fcg-rewrite
                OnlineTestModelSelection.tenant_id == tenant_id,  # fcg-rewrite
                OnlineTestModelSelection.proxy_model_id == model_id,  # fcg-rewrite
            ).first()  # fcg-rewrite
            values = {"selected": item["selected"], "model_name": item.get("model_name")}  # fcg-rewrite
            if selection:  # fcg-rewrite
                for field, value in values.items():  # fcg-rewrite
                    setattr(selection, field, value)  # fcg-rewrite
            else:
                db.add(OnlineTestModelSelection(tenant_id=tenant_id, proxy_model_id=model_id, **values))  # fcg-rewrite
        db.commit()  # fcg-rewrite
        return {"message": "Model selection updated"}  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        db.rollback()  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Update model selection failed: {exc}") from exc  # fcg-rewrite


def _application_id(request: Request, db: Session, tenant_id: uuid.UUID):  # fcg-rewrite
    context = _auth_context(request)  # fcg-rewrite
    raw_id = request.headers.get("x-application-id") or context["data"].get("application_id")  # fcg-rewrite
    if raw_id:  # fcg-rewrite
        try:
            return uuid.UUID(str(raw_id))  # fcg-rewrite
        except ValueError:  # fcg-rewrite
            if request.headers.get("x-application-id"):  # fcg-rewrite
                raise HTTPException(status_code=400, detail="Invalid application ID format")  # fcg-rewrite
    application = db.query(Application).filter(Application.tenant_id == tenant_id).first()  # fcg-rewrite
    return application.id if application else None  # fcg-rewrite


def _messages(data: OnlineTestRequest) -> list[dict]:  # fcg-rewrite
    if data.input_type != "question":  # fcg-rewrite
        parts = {}  # fcg-rewrite
        for line in data.content.splitlines():  # fcg-rewrite
            if line.strip().startswith(("Q:", "A:")):  # fcg-rewrite
                parts[line.strip()[0]] = line.strip()[2:].strip()  # fcg-rewrite
        if not parts.get("Q") or not parts.get("A"):  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Qa pair format error, please use Q: question\nA: answer format")  # fcg-rewrite
        return [{"role": "user", "content": parts["Q"]}, {"role": "assistant", "content": parts["A"]}]  # fcg-rewrite
    if not data.images:  # fcg-rewrite
        return [{"role": "user", "content": data.content}]  # fcg-rewrite
    content = [{"type": "text", "text": data.content}] if data.content.strip() else []  # fcg-rewrite
    content.extend({"type": "image_url", "image_url": {"url": image}} for image in data.images)  # fcg-rewrite
    return [{"role": "user", "content": content}]  # fcg-rewrite


def _api_key(request: Request, db: Session, tenant_id: uuid.UUID) -> Optional[str]:  # fcg-rewrite
    context = _auth_context(request)  # fcg-rewrite
    if context.get("type") in {"api_key", "api_key_switched"}:  # fcg-rewrite
        api_key = context["data"].get("api_key")  # fcg-rewrite
        if api_key:  # fcg-rewrite
            return api_key  # fcg-rewrite
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()  # fcg-rewrite
    return tenant.api_key if tenant else None  # fcg-rewrite


def _models_for_test(db: Session, tenant_id: uuid.UUID, requested: Optional[List[ModelIdRequest]]):  # fcg-rewrite
    pair = db.query(UpstreamApiConfig, OnlineTestModelSelection.model_name)  # fcg-rewrite
    if requested:  # fcg-rewrite
        enabled_ids = [item.id for item in requested if item.enabled]  # fcg-rewrite
        return pair.outerjoin(  # fcg-rewrite
            OnlineTestModelSelection,  # fcg-rewrite
            (UpstreamApiConfig.id == OnlineTestModelSelection.proxy_model_id)  # fcg-rewrite
            & (OnlineTestModelSelection.tenant_id == tenant_id),  # fcg-rewrite
        ).filter(  # fcg-rewrite
            UpstreamApiConfig.id.in_(enabled_ids),  # fcg-rewrite
            UpstreamApiConfig.tenant_id == tenant_id,  # fcg-rewrite
            UpstreamApiConfig.is_active == True,  # fcg-rewrite
        ).all()
    return pair.join(  # fcg-rewrite
        OnlineTestModelSelection, UpstreamApiConfig.id == OnlineTestModelSelection.proxy_model_id  # fcg-rewrite
    ).filter(  # fcg-rewrite
        UpstreamApiConfig.tenant_id == tenant_id,  # fcg-rewrite
        UpstreamApiConfig.is_active == True,  # fcg-rewrite
        OnlineTestModelSelection.selected == True,  # fcg-rewrite
    ).all()


async def _original_responses(  # fcg-rewrite
    db: Session, tenant_id: uuid.UUID, requested, messages: List[Dict[str, Any]]  # fcg-rewrite
) -> Dict[str, ModelResponse]:  # fcg-rewrite
    tasks = []  # fcg-rewrite
    for model, custom_name in _models_for_test(db, tenant_id, requested):  # fcg-rewrite
        try:
            api_key = proxy_service._unseal_api_key(model.api_key_encrypted)  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error("Failed to decrypt API key for model %s: %s", model.id, exc)  # fcg-rewrite
            continue  # fcg-rewrite
        config = ModelConfig(  # fcg-rewrite
            id=str(model.id),  # fcg-rewrite
            name=model.config_name,  # fcg-rewrite
            base_url=model.api_base_url,  # fcg-rewrite
            api_key=api_key,  # fcg-rewrite
            model_name=custom_name or model.model_name,  # fcg-rewrite
            enabled=model.is_active,  # fcg-rewrite
        )
        tasks.append((str(model.id), test_model_api(config, messages)))  # fcg-rewrite
    results = await asyncio.gather(*(task for _, task in tasks), return_exceptions=True)  # fcg-rewrite
    return {  # fcg-rewrite
        model_id: ModelResponse(error=f"Request failed: {result}") if isinstance(result, Exception) else result  # fcg-rewrite
        for (model_id, _), result in zip(tasks, results)  # fcg-rewrite
    }


def _protected_responses(guardrail: dict, originals: Dict[str, ModelResponse]) -> Dict[str, ModelResponse]:  # fcg-rewrite
    if guardrail.get("suggest_action") == "pass" or guardrail.get("overall_risk_level") in {"no_risk", "safe"}:  # fcg-rewrite
        return dict(originals)  # fcg-rewrite
    message = guardrail.get("suggest_answer") or "Sorry, I cannot answer this question, because it may violate the security criteria."  # fcg-rewrite
    return {model_id: ModelResponse(content=message) for model_id in originals}  # fcg-rewrite


@router.post("/test/online", response_model=OnlineTestResponse)  # fcg-rewrite
async def online_test(  # fcg-rewrite
    request_data: OnlineTestRequest, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    try:
        tenant_id = _tenant_uuid(request)  # fcg-rewrite
        messages = _messages(request_data)  # fcg-rewrite
        has_images = bool(request_data.images)  # fcg-rewrite
        if has_images:  # fcg-rewrite
            allowed, error = check_image_detection_subscription(tenant_id, db)  # fcg-rewrite
            if not allowed:  # fcg-rewrite
                raise HTTPException(status_code=403, detail=error)  # fcg-rewrite
        api_key = _api_key(request, db, tenant_id)  # fcg-rewrite
        if not api_key:  # fcg-rewrite
            raise HTTPException(status_code=400, detail="User API key not found")  # fcg-rewrite
        guardrail = await call_guardrail_api(  # fcg-rewrite
            api_key, messages, tenant_id, db, has_images, _application_id(request, db, tenant_id)  # fcg-rewrite
        )
        originals = await _original_responses(db, tenant_id, request_data.models, messages) if request_data.input_type == "question" else {}  # fcg-rewrite
        return OnlineTestResponse(  # fcg-rewrite
            guardrail=guardrail,  # fcg-rewrite
            models=_protected_responses(guardrail, originals),  # fcg-rewrite
            original_responses=originals,  # fcg-rewrite
        )
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        if "timeout" in str(exc).lower() or "timed out" in str(exc).lower():  # fcg-rewrite
            raise HTTPException(status_code=408, detail="Test execution timeout, this may be due to model response time being too long. Please try again later, or contact the administrator to check the model configuration.") from exc  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Test execution failed: {exc}") from exc  # fcg-rewrite


def _rate_limit_error(db: Session, tenant_id: uuid.UUID) -> HTTPException:  # fcg-rewrite
    try:
        from services.rate_limiter import RateLimitService  # fcg-rewrite
        config = RateLimitService(db).get_user_rate_limit(str(tenant_id))  # fcg-rewrite
        limit = config.requests_per_second if config and config.is_active else 10  # fcg-rewrite
        text = "No limit" if limit == 0 else f"{limit} requests/second"  # fcg-rewrite
        detail = f"API call frequency exceeds limit, please try again later. Current rate limit: {text}. If you need to adjust, please contact the administrator {settings.support_email}"  # fcg-rewrite
    except Exception:  # fcg-rewrite
        detail = "API call frequency exceeds limit, please try again later. Please check your API speed limit settings."  # fcg-rewrite
    return HTTPException(status_code=429, detail=detail)  # fcg-rewrite


async def call_guardrail_api(  # fcg-rewrite
    api_key: str,  # fcg-rewrite
    messages: List[Dict[str, Any]],  # fcg-rewrite
    tenant_uuid: uuid.UUID,  # fcg-rewrite
    db: Session,  # fcg-rewrite
    has_images: bool = False,  # fcg-rewrite
    application_id: Optional[uuid.UUID] = None,  # fcg-rewrite
) -> Dict[str, Any]:  # fcg-rewrite
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}", "X-Online-Test": "true"}  # fcg-rewrite
    if application_id:  # fcg-rewrite
        headers["X-Application-ID"] = str(application_id)  # fcg-rewrite
    model = settings.guardrails_vl_model_name if has_images else settings.guardrails_model_name  # fcg-rewrite
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:  # fcg-rewrite
            response = await client.post(  # fcg-rewrite
                f"http://{settings.detection_host}:{settings.detection_port}/v1/guardrails",  # fcg-rewrite
                headers=headers,  # fcg-rewrite
                json={"model": model, "messages": messages},  # fcg-rewrite
            )
        if response.status_code == 429:  # fcg-rewrite
            raise _rate_limit_error(db, tenant_uuid)  # fcg-rewrite
        if response.status_code != 200:  # fcg-rewrite
            raise RuntimeError(f"Guardrail API call failed: HTTP {response.status_code}")  # fcg-rewrite
        result = response.json()  # fcg-rewrite
        detected = result.get("result", {})  # fcg-rewrite
        return {  # fcg-rewrite
            key: {
                "risk_level": detected.get(key, {}).get("risk_level", "无风险"),  # fcg-rewrite
                "categories": detected.get(key, {}).get("categories", []),  # fcg-rewrite
            }
            for key in ("compliance", "security", "data")  # fcg-rewrite
        } | {
            "overall_risk_level": result.get("overall_risk_level", "无风险"),  # fcg-rewrite
            "suggest_action": result.get("suggest_action", "通过"),  # fcg-rewrite
            "suggest_answer": result.get("suggest_answer", ""),  # fcg-rewrite
        }
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        lowered = str(exc).lower()  # fcg-rewrite
        if "rate limit" in lowered or "429" in lowered or "too many requests" in lowered:  # fcg-rewrite
            raise _rate_limit_error(db, tenant_uuid)  # fcg-rewrite
        return {  # fcg-rewrite
            "compliance": {"risk_level": "Test failed", "categories": ["System error"]},  # fcg-rewrite
            "security": {"risk_level": "Test failed", "categories": ["System error"]},  # fcg-rewrite
            "data": {"risk_level": "Test failed", "categories": []},  # fcg-rewrite
            "overall_risk_level": "Test failed",  # fcg-rewrite
            "suggest_action": "System error",  # fcg-rewrite
            "suggest_answer": f"Guardrail detection system error: {exc}",  # fcg-rewrite
        }


async def test_model_api(model: ModelConfig, messages: List[Dict[str, Any]]) -> ModelResponse:  # fcg-rewrite
    try:
        client = AsyncOpenAI(api_key=model.api_key, base_url=model.base_url.rstrip("/"), timeout=600.0)  # fcg-rewrite
        response = await client.chat.completions.create(model=model.model_name, messages=messages, temperature=0.0)  # fcg-rewrite
        answer = response.choices[0].message.content if response.choices else "No response"  # fcg-rewrite
        reasoning = getattr(response.choices[0].message, "reasoning_content", None) if response.choices else None  # fcg-rewrite
        return ModelResponse(content=f"<think>\n{reasoning}\n</think>\n\n{answer}" if reasoning else answer)  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        text = str(exc)  # fcg-rewrite
        if "401" in text or "Unauthorized" in text:  # fcg-rewrite
            text = "API Key invalid or unauthorized"  # fcg-rewrite
        elif "404" in text or "Not Found" in text:  # fcg-rewrite
            text = "API endpoint not found or model not exists"  # fcg-rewrite
        elif "timeout" in text.lower() or "timed out" in text.lower():  # fcg-rewrite
            text = "Request timeout, model response time too long, please try again later or contact the administrator"  # fcg-rewrite
        elif "rate limit" in text.lower():  # fcg-rewrite
            text = "API call frequency limit"  # fcg-rewrite
        else:
            text = f"Request failed: {text}"  # fcg-rewrite
        return ModelResponse(error=text)  # fcg-rewrite
