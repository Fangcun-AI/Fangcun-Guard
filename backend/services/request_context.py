"""Request-local placeholder state for reversible anonymization."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
import logging
from typing import Dict, Optional


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnonymizationState:
    replacements: Dict[str, str] = field(default_factory=dict)
    counters: Dict[str, int] = field(default_factory=dict)


_request_state: ContextVar[AnonymizationState] = ContextVar(
    "anonymization_state",
    default=AnonymizationState(),
)


class AnonymizationContext:
    """Store placeholder mappings without leaking mutable state across tasks."""

    @staticmethod
    def set_mapping(mapping: Dict[str, str]) -> None:
        state = _request_state.get()
        replacements = {**state.replacements, **mapping}
        _request_state.set(
            AnonymizationState(replacements=replacements, counters=dict(state.counters))
        )
        logger.debug(
            "Stored %s anonymization replacements (%s total)",
            len(mapping),
            len(replacements),
        )

    @staticmethod
    def get_mapping() -> Dict[str, str]:
        return dict(_request_state.get().replacements)

    @staticmethod
    def has_mapping() -> bool:
        return bool(_request_state.get().replacements)

    @staticmethod
    def clear() -> None:
        _request_state.set(AnonymizationState())
        logger.debug("Cleared request anonymization state")

    @staticmethod
    def get_next_counter(entity_type: str) -> int:
        state = _request_state.get()
        counters = dict(state.counters)
        next_value = counters.get(entity_type, 0) + 1
        counters[entity_type] = next_value
        _request_state.set(
            AnonymizationState(replacements=dict(state.replacements), counters=counters)
        )
        return next_value

    @staticmethod
    def get_counters() -> Dict[str, int]:
        return dict(_request_state.get().counters)


def restore_placeholders(text: str, mapping: Optional[Dict[str, str]] = None) -> str:
    replacements = mapping if mapping is not None else AnonymizationContext.get_mapping()
    restored = text
    for placeholder in sorted(replacements, key=len, reverse=True):
        restored = restored.replace(placeholder, replacements[placeholder])
    return restored
