from dataclasses import dataclass  # fcg-rewrite
from typing import Dict, List, Optional  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

from fastapi import HTTPException  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import Application  # fcg-rewrite
from models.requests import Message  # fcg-rewrite
from services.billing_service import billing_service  # fcg-rewrite
from utils.image_utils import image_utils  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


@dataclass  # fcg-rewrite
class PreparedGuardrailMessages:  # fcg-rewrite
    user_content: str  # fcg-rewrite
    assistant_content: str  # fcg-rewrite
    messages_dict: List[Dict]  # fcg-rewrite
    has_assistant_message: bool  # fcg-rewrite
    has_image: bool  # fcg-rewrite
    saved_image_paths: List[str]  # fcg-rewrite


def resolve_default_application_id(db: Session, tenant_id: Optional[str]) -> Optional[str]:  # fcg-rewrite
    if not tenant_id:  # fcg-rewrite
        return None  # fcg-rewrite

    try:
        tenant_uuid = UUID(str(tenant_id))  # fcg-rewrite
        default_app = (  # fcg-rewrite
            db.query(Application)  # fcg-rewrite
            .filter(Application.tenant_id == tenant_uuid, Application.is_active == True)  # fcg-rewrite
            .order_by(Application.created_at.asc())  # fcg-rewrite
            .first()  # fcg-rewrite
        )
        if default_app:  # fcg-rewrite
            return str(default_app.id)  # fcg-rewrite
        logger.warning(f"No active application found for tenant {tenant_id}")  # fcg-rewrite
    except (ValueError, Exception) as exc:  # fcg-rewrite
        logger.warning(f"Failed to find default application for tenant {tenant_id}: {exc}")  # fcg-rewrite

    return None  # fcg-rewrite


def extract_assistant_text(messages: List[Message]) -> str:  # fcg-rewrite
    for message in reversed(messages):  # fcg-rewrite
        if message.role != "assistant":  # fcg-rewrite
            continue  # fcg-rewrite

        content = message.content  # fcg-rewrite
        if isinstance(content, str):  # fcg-rewrite
            return content  # fcg-rewrite
        if isinstance(content, list):  # fcg-rewrite
            text_parts = []  # fcg-rewrite
            for part in content:  # fcg-rewrite
                if hasattr(part, "type") and part.type == "text" and hasattr(part, "text"):  # fcg-rewrite
                    text_parts.append(part.text)  # fcg-rewrite
            return " ".join(text_parts) if text_parts else ""  # fcg-rewrite
        return str(content)  # fcg-rewrite
    return ""  # fcg-rewrite


def render_conversation_text(messages: List[Message]) -> str:  # fcg-rewrite
    if len(messages) == 1 and messages[0].role == "user":  # fcg-rewrite
        content = messages[0].content  # fcg-rewrite
        if isinstance(content, str):  # fcg-rewrite
            return content  # fcg-rewrite
        if isinstance(content, list):  # fcg-rewrite
            text_parts = []  # fcg-rewrite
            for part in content:  # fcg-rewrite
                if hasattr(part, "type") and part.type == "text" and hasattr(part, "text"):  # fcg-rewrite
                    text_parts.append(part.text)  # fcg-rewrite
                elif hasattr(part, "type") and part.type == "image_url":  # fcg-rewrite
                    text_parts.append("[Image]")  # fcg-rewrite
            return " ".join(text_parts) if text_parts else "[Multimodal content]"  # fcg-rewrite
        return str(content)  # fcg-rewrite

    conversation_parts = []  # fcg-rewrite
    for message in messages:  # fcg-rewrite
        role_label = (  # fcg-rewrite
            "User"
            if message.role == "user"  # fcg-rewrite
            else "Assistant"  # fcg-rewrite
            if message.role == "assistant"  # fcg-rewrite
            else message.role  # fcg-rewrite
        )
        content = message.content  # fcg-rewrite
        if isinstance(content, str):  # fcg-rewrite
            conversation_parts.append(f"[{role_label}]: {content}")  # fcg-rewrite
        elif isinstance(content, list):  # fcg-rewrite
            text_parts = []  # fcg-rewrite
            for part in content:  # fcg-rewrite
                if hasattr(part, "type") and part.type == "text" and hasattr(part, "text"):  # fcg-rewrite
                    text_parts.append(part.text)  # fcg-rewrite
                elif hasattr(part, "type") and part.type == "image_url":  # fcg-rewrite
                    text_parts.append("[Image]")  # fcg-rewrite
            content_str = " ".join(text_parts) if text_parts else "[Multimodal content]"  # fcg-rewrite
            conversation_parts.append(f"[{role_label}]: {content_str}")  # fcg-rewrite
        else:
            conversation_parts.append(f"[{role_label}]: {content}")  # fcg-rewrite
    return "\n".join(conversation_parts)  # fcg-rewrite


def prepare_detection_messages(  # fcg-rewrite
    messages: List[Message],  # fcg-rewrite
    tenant_id: Optional[str],  # fcg-rewrite
) -> PreparedGuardrailMessages:  # fcg-rewrite
    messages_dict: List[Dict] = []  # fcg-rewrite
    has_image = False  # fcg-rewrite
    saved_image_paths: List[str] = []  # fcg-rewrite
    has_assistant_message = any(message.role == "assistant" for message in messages)  # fcg-rewrite

    for message in messages:  # fcg-rewrite
        content = message.content  # fcg-rewrite
        if isinstance(content, str):  # fcg-rewrite
            messages_dict.append({"role": message.role, "content": content})  # fcg-rewrite
            continue  # fcg-rewrite

        if isinstance(content, list):  # fcg-rewrite
            content_parts = []  # fcg-rewrite
            for part in content:  # fcg-rewrite
                if hasattr(part, "type"):  # fcg-rewrite
                    if part.type == "text" and hasattr(part, "text"):  # fcg-rewrite
                        content_parts.append({"type": "text", "text": part.text})  # fcg-rewrite
                    elif part.type == "image_url" and hasattr(part, "image_url"):  # fcg-rewrite
                        has_image = True  # fcg-rewrite
                        original_url = part.image_url.url  # fcg-rewrite
                        processed_url, saved_path = image_utils.process_image_url(  # fcg-rewrite
                            original_url, tenant_id  # fcg-rewrite
                        )
                        if saved_path:  # fcg-rewrite
                            saved_image_paths.append(saved_path)  # fcg-rewrite
                        content_parts.append(  # fcg-rewrite
                            {"type": "image_url", "image_url": {"url": processed_url}}  # fcg-rewrite
                        )
            messages_dict.append({"role": message.role, "content": content_parts})  # fcg-rewrite
            continue  # fcg-rewrite

        messages_dict.append({"role": message.role, "content": content})  # fcg-rewrite

    return PreparedGuardrailMessages(  # fcg-rewrite
        user_content=render_conversation_text(messages),  # fcg-rewrite
        assistant_content=extract_assistant_text(messages),  # fcg-rewrite
        messages_dict=messages_dict,  # fcg-rewrite
        has_assistant_message=has_assistant_message,  # fcg-rewrite
        has_image=has_image,  # fcg-rewrite
        saved_image_paths=saved_image_paths,  # fcg-rewrite
    )


def ensure_image_detection_subscription(  # fcg-rewrite
    db: Session,  # fcg-rewrite
    tenant_id: Optional[str],  # fcg-rewrite
    has_image: bool,  # fcg-rewrite
) -> None:  # fcg-rewrite
    if not has_image or not tenant_id:  # fcg-rewrite
        return

    subscription = billing_service.get_subscription(tenant_id, db)  # fcg-rewrite
    if not subscription:  # fcg-rewrite
        logger.warning(f"Image detection attempted without subscription for tenant {tenant_id}")  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=403,  # fcg-rewrite
            detail="Subscription not found. Please contact support to enable image detection.",  # fcg-rewrite
        )

    if subscription.subscription_type != "subscribed":  # fcg-rewrite
        logger.warning(f"Image detection attempted by free user for tenant {tenant_id}")  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=403,  # fcg-rewrite
            detail="Image detection is only available for subscribed users. Please upgrade your plan to access this feature.",  # fcg-rewrite
        )
