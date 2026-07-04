import time
import uuid
from typing import Any, Dict, Optional

from utils.logger import setup_logger

logger = setup_logger()

SESSION_TTL_SECONDS = 3600

_session_store: Dict[str, Dict[str, Any]] = {}


class GatewayRestoreSessionStore:
    """In-memory restore session store for gateway anonymization flows."""

    def create_session(self, mapping: Dict[str, str], tenant_id: str) -> str:
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        expires_at = time.time() + SESSION_TTL_SECONDS

        _session_store[session_id] = {
            "mapping": mapping,
            "tenant_id": tenant_id,
            "expires_at": expires_at,
            "created_at": time.time(),
        }

        self.cleanup_expired_sessions()
        logger.info(f"Created restore session {session_id} with {len(mapping)} mappings")
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = _session_store.get(session_id)
        if not session:
            return None

        if session.get("expires_at", 0) < time.time():
            del _session_store[session_id]
            return None

        return session

    def cleanup_expired_sessions(self) -> None:
        current_time = time.time()
        expired = [
            session_id
            for session_id, session in _session_store.items()
            if session.get("expires_at", 0) < current_time
        ]
        for session_id in expired:
            del _session_store[session_id]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired sessions")
