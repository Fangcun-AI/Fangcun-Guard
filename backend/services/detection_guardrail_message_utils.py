import uuid
from typing import Any, Dict, List, Optional, Tuple

from database.connection import get_db_session
from database.models import Application
from models.requests import Message
from utils.logger import setup_logger

logger = setup_logger()


class DetectionRequestContextResolver:
    """Helpers for request shaping and application/message context resolution."""

    def resolve_default_application(
        self, tenant_id: Optional[str], application_id: Optional[str]
    ) -> Optional[str]:
        if application_id or not tenant_id:
            return application_id

        try:
            db = get_db_session()
            try:
                tenant_uuid = uuid.UUID(str(tenant_id))
                default_app = (
                    db.query(Application)
                    .filter(
                        Application.tenant_id == tenant_uuid,
                        Application.is_active == True,
                    )
                    .order_by(Application.created_at.asc())
                    .first()
                )
                if default_app:
                    resolved_id = str(default_app.id)
                    logger.debug(
                        f"Using default application {resolved_id} for tenant {tenant_id}"
                    )
                    return resolved_id

                logger.warning(f"No active application found for tenant {tenant_id}")
                return None
            finally:
                db.close()
        except (ValueError, Exception) as exc:
            logger.warning(
                f"Failed to find default application for tenant {tenant_id}: {exc}"
            )
            return None

    def render_conversation_text(self, messages: List[Message]) -> str:
        """Extract complete conversation content for logging and model detection."""
        if len(messages) == 1 and messages[0].role == "user":
            return self._flatten_message_content(messages[0].content, multimodal_fallback="[Multi-modal content]")

        conversation_parts = []
        for message in messages:
            role_label = (
                "User"
                if message.role == "user"
                else "Assistant"
                if message.role == "assistant"
                else message.role
            )
            content_str = self._flatten_message_content(
                message.content, multimodal_fallback="[多模态内容]"
            )
            conversation_parts.append(f"[{role_label}]: {content_str}")
        return "\n".join(conversation_parts)

    def choose_data_inspection_text(self, messages: List[Message], direction: str) -> str:
        """Extract only the relevant user/assistant slices for DLP inspection."""
        target_role = "assistant" if direction == "output" else "user"
        selected_parts: List[str] = []

        for message in messages:
            if message.role != target_role:
                continue
            content_str = self._flatten_message_content(message.content, multimodal_fallback="")
            if content_str:
                selected_parts.append(content_str)

        return "\n".join(selected_parts) if selected_parts else ""

    def build_model_messages(
        self, messages: List[Message], tenant_id: Optional[str]
    ) -> Tuple[List[Dict[str, Any]], bool, List[str]]:
        """Convert request messages into model-service payloads, preserving image info."""
        from utils.image_utils import image_utils

        messages_dict: List[Dict[str, Any]] = []
        has_image = False
        saved_image_paths: List[str] = []

        for message in messages:
            content = message.content
            if isinstance(content, str):
                messages_dict.append({"role": message.role, "content": content})
                continue

            if not isinstance(content, list):
                continue

            content_parts = []
            for part in content:
                if not hasattr(part, "type"):
                    continue
                if part.type == "text" and hasattr(part, "text"):
                    content_parts.append({"type": "text", "text": part.text})
                elif part.type == "image_url" and hasattr(part, "image_url"):
                    has_image = True
                    original_url = part.image_url.url
                    processed_url, saved_path = image_utils.process_image_url(
                        original_url, tenant_id
                    )
                    if saved_path:
                        saved_image_paths.append(saved_path)
                    content_parts.append(
                        {"type": "image_url", "image_url": {"url": processed_url}}
                    )

            messages_dict.append({"role": message.role, "content": content_parts})

        return messages_dict, has_image, saved_image_paths

    def _flatten_message_content(
        self, content: Any, multimodal_fallback: str = "[Multi-modal content]"
    ) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return multimodal_fallback

        text_parts = []
        for part in content:
            if hasattr(part, "type") and part.type == "text" and hasattr(part, "text"):
                text_parts.append(part.text)
            elif hasattr(part, "type") and part.type == "image_url":
                text_parts.append("[Image]")

        return " ".join(text_parts) if text_parts else multimodal_fallback
