"""One-way and reversible anonymization for gateway messages."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class UnifiedAnonymizationService:
    PLACEHOLDER_PATTERN = re.compile(r"__[a-z_]+_\d+__")

    def anonymize_messages(
        self,
        messages: List[Dict[str, Any]],
        detected_entities: List[Dict[str, Any]],
        action: str,
        application_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, str]]]:
        if not detected_entities:
            return messages, None
        replacements, mapping = self._replacement_map(detected_entities, action)
        return self._apply_replacements(messages, replacements), mapping

    def _anonymize_only(
        self,
        messages: List[Dict[str, Any]],
        detected_entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        replacements, _ = self._replacement_map(detected_entities, "anonymize")
        return self._apply_replacements(messages, replacements)

    def _anonymize_with_restore(
        self,
        messages: List[Dict[str, Any]],
        detected_entities: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        replacements, mapping = self._replacement_map(
            detected_entities, "anonymize_restore"
        )
        return self._apply_replacements(messages, replacements), mapping or {}

    def anonymize_content(
        self,
        content: str,
        detected_entities: List[Dict[str, Any]],
        action: str = "anonymize",
    ) -> Tuple[str, Optional[Dict[str, str]]]:
        if not detected_entities:
            return content, None
        replacements, mapping = self._replacement_map(
            detected_entities, action, uppercase_fallback=True
        )
        return self._replace(content, replacements), mapping

    def restore_content(self, content: str, mapping: Dict[str, str]) -> str:
        return self._replace(content, mapping) if content and mapping else content

    def _replacement_map(
        self,
        entities: List[Dict[str, Any]],
        action: str,
        *,
        uppercase_fallback: bool = False,
    ) -> Tuple[Dict[str, str], Optional[Dict[str, str]]]:
        reversible = action == "anonymize_restore"
        replacements: Dict[str, str] = {}
        mapping: Dict[str, str] = {}
        counters: Dict[str, int] = {}
        for entity in sorted(entities, key=lambda item: len(item.get("text", "")), reverse=True):
            original = entity.get("text", "")
            if not original or original in replacements:
                continue
            entity_type = entity.get("entity_type", "unknown")
            if reversible:
                entity_type = entity_type.lower()
                counters[entity_type] = counters.get(entity_type, 0) + 1
                replacement = f"__{entity_type}_{counters[entity_type]}__"
                mapping[replacement] = original
            else:
                replacement = entity.get("anonymized_value")
                if replacement is None:
                    label = entity_type.upper() if uppercase_fallback else entity_type
                    replacement = f"<{label}>"
                    logger.warning(f"Entity {entity_type} missing anonymized_value")
            replacements[original] = replacement
        return replacements, mapping if reversible else None

    def _apply_replacements(
        self, messages: List[Dict[str, Any]], replacements: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        if not replacements:
            return messages
        result = []
        for message in messages:
            updated = message.copy()
            if updated.get("role") == "user" and isinstance(updated.get("content"), str):
                updated["content"] = self._replace(updated["content"], replacements)
            result.append(updated)
        return result

    @staticmethod
    def _replace(content: str, replacements: Dict[str, str]) -> str:
        for original, replacement in sorted(
            replacements.items(), key=lambda item: len(item[0]), reverse=True
        ):
            content = content.replace(original, replacement)
        return content


_service_instance: Optional[UnifiedAnonymizationService] = None


def get_unified_anonymization_service() -> UnifiedAnonymizationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = UnifiedAnonymizationService()
    return _service_instance
