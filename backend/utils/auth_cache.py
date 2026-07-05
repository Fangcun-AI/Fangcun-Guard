"""Small thread-safe cache for resolved caller identities."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import threading
import time
from typing import Any, Callable, Dict, Optional

from utils.logger import setup_logger


logger = setup_logger()


@dataclass(frozen=True)
class AuthCacheEntry:
    context: Dict[str, Any]
    expires_at: float


class AuthSessionStore:
    """Keep short-lived identity lookups in process memory."""

    def __init__(self, ttl: int = 300):
        self._entries: Dict[str, AuthCacheEntry] = {}
        self._ttl_seconds = ttl
        self._lock = threading.RLock()

    def get(self, token: str) -> Optional[Dict[str, Any]]:
        key = self._digest(token)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= time.monotonic():
                self._entries.pop(key, None)
                return None
            return entry.context

    def set(self, token: str, auth_data: Dict[str, Any]) -> None:
        with self._lock:
            self._entries[self._digest(token)] = AuthCacheEntry(
                context=auth_data,
                expires_at=time.monotonic() + self._ttl_seconds,
            )

    def invalidate(self, token: str) -> None:
        with self._lock:
            self._entries.pop(self._digest(token), None)

    def clear_expired(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired_keys = [
                key for key, entry in self._entries.items() if entry.expires_at <= now
            ]
            for key in expired_keys:
                self._entries.pop(key, None)
        if expired_keys:
            logger.debug("Cleared %s expired auth cache entries", len(expired_keys))

    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    def invalidate_by_application(self, application_id: str) -> None:
        self._invalidate_matching(
            lambda context: context.get("data", {}).get("application_id") == application_id,
            f"application {application_id}",
        )

    def invalidate_by_tenant(self, tenant_id: str) -> None:
        self._invalidate_matching(
            lambda context: context.get("data", {}).get("tenant_id") == tenant_id,
            f"tenant {tenant_id}",
        )

    def _invalidate_matching(
        self,
        predicate: Callable[[Dict[str, Any]], bool],
        scope_description: str,
    ) -> None:
        with self._lock:
            matching_keys = [
                key for key, entry in self._entries.items() if predicate(entry.context)
            ]
            for key in matching_keys:
                self._entries.pop(key, None)
        if matching_keys:
            logger.info(
                "Invalidated %s auth cache entries for %s",
                len(matching_keys),
                scope_description,
            )

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


auth_cache = AuthSessionStore(ttl=300)
