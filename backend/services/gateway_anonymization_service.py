from typing import Any, Dict, List, Optional, Tuple

from services.gateway_restore_session_store import GatewayRestoreSessionStore
from services.unified_anonymization_service import get_unified_anonymization_service


class GatewayAnonymizationCoordinator:
    """Coordinates gateway anonymization and restore flows."""

    def __init__(self, session_store: GatewayRestoreSessionStore):
        self.session_store = session_store

    def anonymize_messages(
        self,
        messages: List[Dict[str, Any]],
        detected_entities: List[Dict[str, Any]],
        application_id: str,
        tenant_id: str,
        action: str = "anonymize_restore",
    ) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[Dict[str, str]]]:
        if not detected_entities:
            return messages, None, None

        anonymization_service = get_unified_anonymization_service()
        anonymized_messages, restore_mapping = anonymization_service.anonymize_messages(
            messages=messages,
            detected_entities=detected_entities,
            action=action,
            application_id=application_id,
            tenant_id=tenant_id,
        )

        session_id = None
        if restore_mapping:
            session_id = self.session_store.create_session(
                mapping=restore_mapping,
                tenant_id=tenant_id,
            )

        return anonymized_messages, session_id, restore_mapping

    def restore_content(self, content: str, mapping: Dict[str, str]) -> str:
        if not mapping or not content:
            return content

        anonymization_service = get_unified_anonymization_service()
        return anonymization_service.restore_content(content, mapping)

    def anonymize_output_content(
        self,
        content: str,
        detected_entities: List[Dict[str, Any]],
    ) -> str:
        if not detected_entities:
            return content

        anonymization_service = get_unified_anonymization_service()
        anonymized_content, _ = anonymization_service.anonymize_content(
            content=content,
            detected_entities=detected_entities,
            action="anonymize",
        )
        return anonymized_content
