"""
Hallucination policy cache (5 min TTL).
(Extracted from backend/services/agent_safety_cache.py — hallucination portion)
"""

import asyncio
import time
from typing import Dict, Optional
from utils.logger import setup_logger

logger = setup_logger()


class HallucinationPolicyStore:
    """Cache for hallucination detection policies (5 min TTL)"""

    def __init__(self):
        self._cache: Dict[str, object] = {}
        self._timestamps: Dict[str, float] = {}
        self._cache_ttl = 300  # 5 minutes
        self._lock = asyncio.Lock()

    async def get_policy(self, application_id: str):
        """Get cached hallucination policy for application"""
        if not application_id:
            return None

        async with self._lock:
            current_time = time.time()
            if (application_id in self._cache and
                application_id in self._timestamps and
                current_time - self._timestamps[application_id] < self._cache_ttl):
                return self._cache[application_id]

            try:
                policy = await self._load_from_db(application_id)
                self._cache[application_id] = policy
                self._timestamps[application_id] = current_time
                return policy
            except Exception as e:
                logger.error(f"Failed to load hallucination policy for {application_id}: {e}")
                self._cache[application_id] = None
                self._timestamps[application_id] = current_time
                return None

    async def _load_from_db(self, application_id: str):
        """Load hallucination policy from database"""
        from database.connection import get_db
        from database.models import HallucinationPolicy
        from sqlalchemy.orm import Session

        db: Session = next(get_db())
        try:
            policy = db.query(HallucinationPolicy).filter(
                HallucinationPolicy.application_id == application_id
            ).first()
            if policy:
                return _HallucinationPolicySnapshot(
                    enabled=policy.enabled,
                    enable_groundedness=policy.enable_groundedness,
                    enable_consistency=policy.enable_consistency,
                    groundedness_threshold=policy.groundedness_threshold,
                    consistency_threshold=policy.consistency_threshold,
                    source_context_field=policy.source_context_field,
                    violation_action=policy.violation_action,
                )
            return None
        finally:
            db.close()

    async def invalidate(self, application_id: str):
        """Invalidate cache for an application"""
        if not application_id:
            return
        async with self._lock:
            self._cache.pop(application_id, None)
            self._timestamps.pop(application_id, None)
            logger.info(f"Invalidated hallucination cache for {application_id}")

    async def clear_cache(self):
        """Clear all caches"""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()


class _HallucinationPolicySnapshot:
    """Detached snapshot of HallucinationPolicy for caching outside DB session"""
    __slots__ = ('enabled', 'enable_groundedness', 'enable_consistency',
                 'groundedness_threshold', 'consistency_threshold',
                 'source_context_field', 'violation_action')

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# Global instance
hallucination_cache = HallucinationPolicyStore()
