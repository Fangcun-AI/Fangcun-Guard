"""
Agent safety policy cache — DB-backed with short in-process TTL.

Each worker always loads from DB (shared state), but caches locally for
a short TTL (60s) to reduce DB load. This ensures cross-process consistency
within an acceptable window (vs the old 5-min asyncio.Lock-only design
that was invisible across Uvicorn workers).
"""

import time
from typing import Dict, Optional
from utils.logger import setup_logger

logger = setup_logger()

# Short TTL — ensures workers converge quickly after policy updates
_LOCAL_CACHE_TTL = 60  # seconds


class AgentSafetyPolicyStore:
    """DB-backed cache for agent safety policies with short local TTL."""

    def __init__(self):
        self._cache: Dict[str, object] = {}
        self._timestamps: Dict[str, float] = {}

    async def get_policy(self, application_id: str):
        """Get agent safety policy — short local TTL, always DB-backed."""
        if not application_id:
            return None

        current_time = time.time()

        # Check local cache (no lock needed — worst case is an extra
        # idempotent DB read, which is acceptable)
        if (application_id in self._cache and
            application_id in self._timestamps and
            current_time - self._timestamps[application_id] < _LOCAL_CACHE_TTL):
            return self._cache[application_id]

        # Cache miss or expired — load from DB
        try:
            policy = await self._load_from_db(application_id)
            self._cache[application_id] = policy
            self._timestamps[application_id] = current_time
            return policy
        except Exception as e:
            logger.error(f"Failed to load agent safety policy for {application_id}: {e}")
            # On DB error, return stale cache if available
            if application_id in self._cache:
                logger.warning(f"Using stale cache for {application_id} due to DB error")
                return self._cache[application_id]
            return None

    async def _load_from_db(self, application_id: str):
        """Load agent safety policy from database"""
        from database.connection import get_db
        from database.models import AgentSafetyPolicy
        from sqlalchemy.orm import Session

        db: Session = next(get_db())
        try:
            policy = db.query(AgentSafetyPolicy).filter(
                AgentSafetyPolicy.application_id == application_id
            ).first()
            if policy:
                return _PolicySnapshot(
                    enabled=policy.enabled,
                    tool_whitelist=policy.tool_whitelist,
                    tool_blacklist=policy.tool_blacklist or [],
                    max_tool_calls_per_request=policy.max_tool_calls_per_request,
                    enable_argument_inspection=policy.enable_argument_inspection,
                    argument_patterns=policy.argument_patterns or [],
                    enable_reasoning_safety=policy.enable_reasoning_safety,
                    enable_tool_definition_scan=getattr(policy, 'enable_tool_definition_scan', True),
                    tool_violation_action=policy.tool_violation_action,
                    reasoning_violation_action=policy.reasoning_violation_action,
                    tool_definition_scan_action=getattr(policy, 'tool_definition_scan_action', 'warn'),
                )
            return None
        finally:
            db.close()

    async def invalidate(self, application_id: str):
        """Invalidate local cache for an application."""
        if not application_id:
            return
        self._cache.pop(application_id, None)
        self._timestamps.pop(application_id, None)
        logger.info(f"Invalidated agent safety cache for {application_id}")

    async def clear_cache(self):
        """Clear all local caches."""
        self._cache.clear()
        self._timestamps.clear()


class _PolicySnapshot:
    """Detached snapshot of AgentSafetyPolicy for caching outside DB session"""
    __slots__ = ('enabled', 'tool_whitelist', 'tool_blacklist', 'max_tool_calls_per_request',
                 'enable_argument_inspection', 'argument_patterns', 'enable_reasoning_safety',
                 'enable_tool_definition_scan', 'tool_violation_action', 'reasoning_violation_action',
                 'tool_definition_scan_action')

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# Global instance
agent_safety_cache = AgentSafetyPolicyStore()
