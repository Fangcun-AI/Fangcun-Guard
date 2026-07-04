"""Request-scope helpers for proxy endpoints."""

from dataclasses import dataclass  # fcg-rewrite
from typing import Any, Mapping, Optional, Sequence  # fcg-rewrite
import uuid  # fcg-rewrite

from fastapi import HTTPException  # fcg-rewrite
from fastapi.responses import JSONResponse  # fcg-rewrite

from database.connection import get_admin_db_session, get_db  # fcg-rewrite
from services.ban_policy_service import BanPolicyManager  # fcg-rewrite
from services.billing_service import billing_service  # fcg-rewrite
from services.data_leakage_disposal_service import LeakageMitigator  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite


logger = setup_logger()  # fcg-rewrite


@dataclass(frozen=True)  # fcg-rewrite
class ProxyRequestContext:  # fcg-rewrite
    """Resolved caller context for a proxy request."""

    tenant_id: str  # fcg-rewrite
    application_id: Optional[str]  # fcg-rewrite
    user_id: str  # fcg-rewrite
    request_id: str  # fcg-rewrite


def resolve_proxy_request_context(  # fcg-rewrite
    request,  # fcg-rewrite
    *,
    extra_body: Optional[Mapping[str, Any]],  # fcg-rewrite
    route_label: str,  # fcg-rewrite
    default_app_log_label: str,  # fcg-rewrite
) -> ProxyRequestContext:  # fcg-rewrite
    """Resolve tenant/application/user identifiers for proxy routes."""
    auth_ctx = getattr(request.state, "auth_context", None)  # fcg-rewrite
    if not auth_ctx:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Authentication required")  # fcg-rewrite

    tenant_id = auth_ctx["data"].get("tenant_id")  # fcg-rewrite
    application_id = auth_ctx["data"].get("application_id")  # fcg-rewrite
    if not application_id and tenant_id:  # fcg-rewrite
        application_id = _load_default_application_id(tenant_id, default_app_log_label)  # fcg-rewrite

    user_id = extract_proxy_user_id(extra_body, tenant_id)  # fcg-rewrite
    request_id = str(uuid.uuid4())  # fcg-rewrite
    logger.info(  # fcg-rewrite
        "%s request %s from tenant %s, application %s, user_id: %s",  # fcg-rewrite
        route_label,  # fcg-rewrite
        request_id,  # fcg-rewrite
        tenant_id,  # fcg-rewrite
        application_id,  # fcg-rewrite
        user_id,  # fcg-rewrite
    )
    return ProxyRequestContext(  # fcg-rewrite
        tenant_id=tenant_id,  # fcg-rewrite
        application_id=application_id,  # fcg-rewrite
        user_id=user_id,  # fcg-rewrite
        request_id=request_id,  # fcg-rewrite
    )


def extract_proxy_user_id(extra_body: Optional[Mapping[str, Any]], tenant_id: str) -> str:  # fcg-rewrite
    """Use the external app user ID when present, otherwise fall back to tenant ID."""
    if extra_body:  # fcg-rewrite
        user_id = extra_body.get("xxai_app_user_id")  # fcg-rewrite
        if user_id:  # fcg-rewrite
            return user_id  # fcg-rewrite
    return tenant_id  # fcg-rewrite


def build_chat_messages(messages: Sequence[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:  # fcg-rewrite
    """Build both detection-safe and forwarding-safe message payloads."""
    input_messages = [{"role": msg.role, "content": msg.content} for msg in messages]  # fcg-rewrite

    full_messages = []  # fcg-rewrite
    for msg in messages:  # fcg-rewrite
        msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else msg.dict()  # fcg-rewrite
        full_messages.append({key: value for key, value in msg_dict.items() if value is not None})  # fcg-rewrite

    return input_messages, full_messages  # fcg-rewrite


def apply_content_overrides(  # fcg-rewrite
    full_messages: Sequence[dict[str, Any]],  # fcg-rewrite
    actual_messages: Sequence[dict[str, Any]],  # fcg-rewrite
    original_messages: Sequence[dict[str, Any]],  # fcg-rewrite
) -> list[dict[str, Any]]:  # fcg-rewrite
    """Apply content-only guardrail edits while preserving tool metadata."""
    clean_messages = list(full_messages)  # fcg-rewrite
    if actual_messages is original_messages:  # fcg-rewrite
        return clean_messages  # fcg-rewrite

    for index, (original, modified) in enumerate(zip(clean_messages, actual_messages)):  # fcg-rewrite
        modified_content = modified.get("content") if isinstance(modified, dict) else getattr(modified, "content", None)  # fcg-rewrite
        if modified_content != original.get("content"):  # fcg-rewrite
            clean_messages[index] = dict(original)  # fcg-rewrite
            clean_messages[index]["content"] = modified_content  # fcg-rewrite

    return clean_messages  # fcg-rewrite


def merge_passthrough_fields(request_data, known_fields: set[str]) -> Optional[dict[str, Any]]:  # fcg-rewrite
    """Promote undeclared SDK extras into ``extra_body`` for upstream transport."""
    request_dict = request_data.model_dump() if hasattr(request_data, "model_dump") else request_data.dict()  # fcg-rewrite
    extra_fields = {  # fcg-rewrite
        key: value  # fcg-rewrite
        for key, value in request_dict.items()  # fcg-rewrite
        if key not in known_fields and value is not None  # fcg-rewrite
    }
    if not extra_fields:  # fcg-rewrite
        return request_data.extra_body  # fcg-rewrite

    merged_extra = dict(request_data.extra_body or {})  # fcg-rewrite
    merged_extra.update(extra_fields)  # fcg-rewrite
    request_data.extra_body = merged_extra  # fcg-rewrite
    return merged_extra  # fcg-rewrite


def messages_contain_images(messages: Sequence[Any]) -> bool:  # fcg-rewrite
    """Detect whether a request includes multimodal image parts."""
    for msg in messages:  # fcg-rewrite
        content = getattr(msg, "content", None)  # fcg-rewrite
        if not isinstance(content, list):  # fcg-rewrite
            continue  # fcg-rewrite
        for part in content:  # fcg-rewrite
            if hasattr(part, "type") and part.type == "image_url":  # fcg-rewrite
                return True  # fcg-rewrite
    return False  # fcg-rewrite


def ensure_image_detection_subscription(tenant_id: str, messages: Sequence[Any]) -> Optional[JSONResponse]:  # fcg-rewrite
    """Guard image detection behind a paid subscription."""
    if not messages_contain_images(messages):  # fcg-rewrite
        return None  # fcg-rewrite

    subscription = billing_service.get_subscription(tenant_id, None)  # fcg-rewrite
    if not subscription:  # fcg-rewrite
        logger.warning("Image detection attempted without subscription for tenant %s", tenant_id)  # fcg-rewrite
        return JSONResponse(  # fcg-rewrite
            status_code=403,  # fcg-rewrite
            content={  # fcg-rewrite
                "error": {  # fcg-rewrite
                    "message": "Subscription not found. Please contact support to enable image detection.",  # fcg-rewrite
                    "type": "subscription_required",  # fcg-rewrite
                }
            },
        )

    if subscription.subscription_type != "subscribed":  # fcg-rewrite
        logger.warning("Image detection attempted by free user for tenant %s", tenant_id)  # fcg-rewrite
        return JSONResponse(  # fcg-rewrite
            status_code=403,  # fcg-rewrite
            content={  # fcg-rewrite
                "error": {  # fcg-rewrite
                    "message": "Image detection is only available for subscribed users. Please upgrade your plan to access this feature.",  # fcg-rewrite
                    "type": "subscription_required",  # fcg-rewrite
                }
            },
        )

    return None  # fcg-rewrite


def should_force_nonstream(stream_requested: bool, application_id: Optional[str], request_id: str) -> bool:  # fcg-rewrite
    """Output anonymization needs a buffered response, not a live stream."""
    if not stream_requested or not application_id:  # fcg-rewrite
        return False  # fcg-rewrite

    try:
        db = next(get_db())  # fcg-rewrite
        try:
            disposal_service = LeakageMitigator(db)  # fcg-rewrite
            for risk_level in ("high_risk", "medium_risk", "low_risk"):  # fcg-rewrite
                if disposal_service.get_disposal_action(application_id, risk_level, direction="output") == "anonymize":  # fcg-rewrite
                    logger.info("[%s] Forcing non-streaming for output anonymization", request_id)  # fcg-rewrite
                    return True  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.debug("[%s] Failed to inspect output disposal policy: %s", request_id, exc)  # fcg-rewrite
    return False  # fcg-rewrite


async def apply_proxy_ban_check(tenant_id: str, user_id: str) -> None:  # fcg-rewrite
    """Reject requests from banned callers."""
    if not user_id:  # fcg-rewrite
        return

    ban_snapshot = await BanPolicyManager.check_user_banned(tenant_id, user_id)  # fcg-rewrite
    if not ban_snapshot:  # fcg-rewrite
        return

    ban_until = ban_snapshot["ban_until"].isoformat() if ban_snapshot["ban_until"] else ""  # fcg-rewrite
    raise HTTPException(  # fcg-rewrite
        status_code=403,  # fcg-rewrite
        detail={  # fcg-rewrite
            "error": {  # fcg-rewrite
                "message": "User has been banned",  # fcg-rewrite
                "type": "user_banned",  # fcg-rewrite
                "user_id": user_id,  # fcg-rewrite
                "ban_until": ban_until,  # fcg-rewrite
                "reason": ban_snapshot.get("reason", "Trigger ban policy"),  # fcg-rewrite
            }
        },
    )


def _load_default_application_id(tenant_id: str, log_label: str) -> Optional[str]:  # fcg-rewrite
    from database.models import Application  # fcg-rewrite

    try:
        db = get_admin_db_session()  # fcg-rewrite
        try:
            tenant_uuid = uuid.UUID(str(tenant_id))  # fcg-rewrite
            default_app = (  # fcg-rewrite
                db.query(Application)  # fcg-rewrite
                .filter(Application.tenant_id == tenant_uuid, Application.is_active == True)  # fcg-rewrite
                .order_by(Application.created_at.asc())  # fcg-rewrite
                .first()  # fcg-rewrite
            )
            if default_app:  # fcg-rewrite
                logger.debug("%s: Using default application %s for tenant %s", log_label, default_app.id, tenant_id)  # fcg-rewrite
                return str(default_app.id)  # fcg-rewrite
            logger.warning("%s: No active application found for tenant %s", log_label, tenant_id)  # fcg-rewrite
            return None  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite
    except (ValueError, Exception) as exc:  # fcg-rewrite
        logger.warning("%s: Failed to find default application for tenant %s: %s", log_label, tenant_id, exc)  # fcg-rewrite
        return None  # fcg-rewrite
