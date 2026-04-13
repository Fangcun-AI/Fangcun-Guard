"""FangcunGuard Router - Intelligent multi-model safety router for LLM applications."""

from fangcunguard_router.router import GuardRouter, CheckResult, DimensionResult
from fangcunguard_router.registry import GuardModelRegistry, GuardModelConfig
from fangcunguard_router.client import GuardModelClient

__version__ = "0.1.0"
__all__ = [
    "GuardRouter",
    "CheckResult",
    "DimensionResult",
    "GuardModelRegistry",
    "GuardModelConfig",
    "GuardModelClient",
]
