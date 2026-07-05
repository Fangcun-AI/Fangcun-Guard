"""
Basic guard policy cache (5 min TTL).
"""

import asyncio
import time
from typing import Dict, Optional
from utils.logger import setup_logger

logger = setup_logger()


class BasicGuardPolicyStore:
    """Cache for basic guard policies (5 min TTL)"""

    def __init__(self):
        self._cache: Dict[str, object] = {}
        self._timestamps: Dict[str, float] = {}
        self._cache_ttl = 300  # 5 minutes
        self._lock = asyncio.Lock()

    async def get_policy(self, application_id: str):
        """Get cached basic guard policy for application"""
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
                logger.error(f"Failed to load basic guard policy for {application_id}: {e}")
                self._cache[application_id] = None
                self._timestamps[application_id] = current_time
                return None

    async def _load_from_db(self, application_id: str):
        """Load basic guard policy from database"""
        from database.connection import get_db
        from database.models import BasicGuardPolicy
        from sqlalchemy.orm import Session

        db: Session = next(get_db())
        try:
            policy = db.query(BasicGuardPolicy).filter(
                BasicGuardPolicy.application_id == application_id
            ).first()
            if policy:
                return _BasicGuardPolicySnapshot(
                    enabled=policy.enabled,
                    enable_content_pattern_check=policy.enable_content_pattern_check,
                    enable_reasoning_divergence_check=policy.enable_reasoning_divergence_check,
                    enable_output_anomaly_check=policy.enable_output_anomaly_check,
                    max_repetition_ratio=policy.max_repetition_ratio,
                    min_content_length=policy.min_content_length,
                    violation_action=policy.violation_action,
                    enable_prompt_injection_check=getattr(policy, 'enable_prompt_injection_check', True),
                    prompt_injection_threshold=getattr(policy, 'prompt_injection_threshold', 0.5),
                    prompt_injection_action=getattr(policy, 'prompt_injection_action', 'block'),
                    scan_user_messages=getattr(policy, 'scan_user_messages', True),
                    scan_system_messages=getattr(policy, 'scan_system_messages', True),
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
            logger.info(f"Invalidated basic guard cache for {application_id}")

    async def clear_cache(self):
        """Clear all caches"""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()


class _BasicGuardPolicySnapshot:
    """Detached snapshot of BasicGuardPolicy for caching outside DB session"""
    __slots__ = (
        'enabled', 'enable_content_pattern_check', 'enable_reasoning_divergence_check',
        'enable_output_anomaly_check', 'max_repetition_ratio', 'min_content_length',
        'violation_action',
        'enable_prompt_injection_check', 'prompt_injection_threshold',
        'prompt_injection_action', 'scan_user_messages', 'scan_system_messages',
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# Global instance
basic_guard_cache = BasicGuardPolicyStore()
