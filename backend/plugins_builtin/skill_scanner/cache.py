"""
Skill Scanner policy cache (5 min TTL).
"""

import asyncio
import time
from typing import Dict, Optional
from utils.logger import setup_logger

logger = setup_logger()


class SkillScannerPolicyCache:
    """Cache for skill scanner policies (5 min TTL)"""

    def __init__(self):
        self._cache: Dict[str, object] = {}
        self._timestamps: Dict[str, float] = {}
        self._cache_ttl = 300  # 5 minutes
        self._lock = asyncio.Lock()

    async def get_policy(self, application_id: str):
        """Get cached skill scanner policy for application"""
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
                logger.error(f"Failed to load skill scanner policy for {application_id}: {e}")
                self._cache[application_id] = None
                self._timestamps[application_id] = current_time
                return None

    async def _load_from_db(self, application_id: str):
        """Load skill scanner policy from database"""
        from database.connection import get_db
        from database.models import SkillScannerPolicy
        from sqlalchemy.orm import Session

        db: Session = next(get_db())
        try:
            policy = db.query(SkillScannerPolicy).filter(
                SkillScannerPolicy.application_id == application_id
            ).first()
            if policy:
                return _PolicySnapshot(
                    enabled=policy.enabled,
                    enable_static_pattern=policy.enable_static_pattern,
                    enable_structural_validation=policy.enable_structural_validation,
                    enable_capability_risk=policy.enable_capability_risk,
                    enable_llm_semantic=policy.enable_llm_semantic,
                    llm_auto_trigger_on_medium=policy.llm_auto_trigger_on_medium,
                    policy_mode=policy.policy_mode,
                    critical_action=policy.critical_action,
                    high_action=policy.high_action,
                    medium_action=policy.medium_action,
                    low_action=policy.low_action,
                    custom_patterns=policy.custom_patterns or [],
                    dangerous_capability_keywords=policy.dangerous_capability_keywords or [],
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
            logger.info(f"Invalidated skill scanner cache for {application_id}")

    async def clear_cache(self):
        """Clear all caches"""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()


class _PolicySnapshot:
    """Detached snapshot of SkillScannerPolicy for caching outside DB session"""
    __slots__ = (
        'enabled', 'enable_static_pattern', 'enable_structural_validation',
        'enable_capability_risk', 'enable_llm_semantic', 'llm_auto_trigger_on_medium',
        'policy_mode', 'critical_action', 'high_action', 'medium_action',
        'low_action', 'custom_patterns', 'dangerous_capability_keywords',
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# Global instance
skill_scanner_cache = SkillScannerPolicyCache()
