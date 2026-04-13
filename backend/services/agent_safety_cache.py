"""
DEPRECATED: This module has been split into:
  - plugins_builtin/agent_safety/cache.py
  - plugins_builtin/hallucination_detection/cache.py
This file provides backward compatibility via a unified facade.
"""
from utils.logger import setup_logger

logger = setup_logger()


class AgentSafetyPolicyCache:
    """Backward-compatible facade delegating to plugin caches"""

    async def get_agent_safety_policy(self, application_id: str):
        from plugins_builtin.agent_safety.cache import agent_safety_cache
        return await agent_safety_cache.get_policy(application_id)

    async def get_hallucination_policy(self, application_id: str):
        from plugins_builtin.hallucination_detection.cache import hallucination_cache
        return await hallucination_cache.get_policy(application_id)

    async def invalidate(self, application_id: str):
        from plugins_builtin.agent_safety.cache import agent_safety_cache
        from plugins_builtin.hallucination_detection.cache import hallucination_cache
        await agent_safety_cache.invalidate(application_id)
        await hallucination_cache.invalidate(application_id)

    async def clear_cache(self):
        from plugins_builtin.agent_safety.cache import agent_safety_cache
        from plugins_builtin.hallucination_detection.cache import hallucination_cache
        await agent_safety_cache.clear_cache()
        await hallucination_cache.clear_cache()


# Global instance (backward compatible)
agent_safety_cache = AgentSafetyPolicyCache()
