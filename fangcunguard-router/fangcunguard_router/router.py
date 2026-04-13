"""
Guard Router - Total dispatcher for multi-model safety detection.

This is the main entry point. A single check() call:
1. Analyzes input features (language, format, content type)
2. Determines which safety dimensions are relevant
3. Dispatches to multiple guard models in parallel
4. Aggregates results into a unified safety verdict
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from fangcunguard_router.client import GuardModelClient, GuardModelError
from fangcunguard_router.classifier import MLClassifier
from fangcunguard_router.registry import (
    GuardModelConfig,
    GuardModelRegistry,
    RoutingRule,
)

logger = logging.getLogger("fangcunguard_router")


# ── Language Detection ───────────────────────────────────────────────────

_CJK_RANGES = ((0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x3000, 0x303F), (0xFF00, 0xFFEF))
_LATIN_RANGES = ((0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x00FF))


def _detect_language(text: str) -> tuple:
    """Detect dominant script. Returns (lang, confidence)."""
    if not text:
        return ("other", 0.0)
    cjk = lat = total = 0
    for ch in text[:500]:
        if ch.isspace():
            continue
        total += 1
        cp = ord(ch)
        if any(s <= cp <= e for s, e in _CJK_RANGES):
            cjk += 1
        elif any(s <= cp <= e for s, e in _LATIN_RANGES):
            lat += 1
    if total == 0:
        return ("other", 0.0)
    if cjk > lat:
        return ("zh", cjk / total)
    elif lat > cjk:
        return ("en", lat / total)
    return ("other", 0.0)


def _has_code(text: str) -> bool:
    if "```" in text:
        return True
    indicators = ["def ", "class ", "import ", "function ", "const ", "var ",
                   "SELECT ", "INSERT ", "#include", "package "]
    return any(i in text for i in indicators)


# ── Data Classes ─────────────────────────────────────────────────────────

@dataclass
class DimensionResult:
    """Result from a single safety dimension check."""
    dimension: str
    model_id: str
    model_name: str
    safe: bool
    details: List[str] = field(default_factory=list)
    score: float = 0.0
    error: Optional[str] = None


@dataclass
class CheckResult:
    """Aggregated result from all dimension checks."""
    safe: bool
    risk_level: str  # "safe" | "low" | "medium" | "high"
    flagged_dimensions: List[str] = field(default_factory=list)
    dimension_results: List[DimensionResult] = field(default_factory=list)
    routing_info: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "safe": self.safe,
            "risk_level": self.risk_level,
            "flagged_dimensions": self.flagged_dimensions,
            "dimension_results": [
                {
                    "dimension": r.dimension,
                    "model_id": r.model_id,
                    "model_name": r.model_name,
                    "safe": r.safe,
                    "details": r.details,
                    "score": r.score,
                    "error": r.error,
                }
                for r in self.dimension_results
            ],
            "routing_info": self.routing_info,
        }


# ── Guard Router ─────────────────────────────────────────────────────────

class GuardRouter:
    """Multi-model safety router.

    Usage:
        router = GuardRouter("guard_models.yaml")
        result = await router.check("some user input")
        print(result.safe, result.flagged_dimensions)

    The router analyzes input content and dispatches to relevant guard models
    in parallel. It combines results from multiple models into a single verdict.
    """

    def __init__(self, config_path: str, ml_weights_path: Optional[str] = None):
        self._registry = GuardModelRegistry(config_path)
        self._clients: Dict[str, GuardModelClient] = {}

        # Initialize clients for all available models
        for mid, config in self._registry.get_all_models().items():
            self._clients[mid] = GuardModelClient(config)

        # Initialize ML classifier if available
        self._ml_classifier: Optional[MLClassifier] = None
        if self._registry.ml_fallback_enabled and ml_weights_path:
            from fangcunguard_router.registry import GuardModelConfig
            # Find embedding config from any model or use defaults
            import os
            self._ml_classifier = MLClassifier(
                weights_path=ml_weights_path,
                embedding_url=os.environ.get("EMBEDDING_API_BASE_URL", "http://localhost:58004/v1"),
                embedding_key=os.environ.get("EMBEDDING_API_KEY", "EMPTY"),
                embedding_model=os.environ.get("EMBEDDING_MODEL_NAME", "bge-m3"),
            )

        logger.info(f"GuardRouter initialized: {len(self._clients)} models, "
                     f"ML={'on' if self._ml_classifier and self._ml_classifier.is_available else 'off'}")

    async def check(
        self,
        text: str,
        messages: Optional[List[Dict]] = None,
        dimensions: Optional[List[str]] = None,
    ) -> CheckResult:
        """Run safety check across multiple models.

        Args:
            text: Content to check
            messages: Full conversation context (optional)
            dimensions: Explicitly request specific dimensions (optional).
                        If None, the router auto-selects based on content.

        Returns:
            CheckResult with aggregated safety verdict
        """
        if messages is None:
            messages = [{"role": "user", "content": text}]

        # Determine which dimensions to check
        if dimensions:
            target_dims = dimensions
            routing_method = "explicit"
        else:
            target_dims = self._select_dimensions(text, messages)
            routing_method = "auto"

        # Map dimensions to models
        dispatch_plan: Dict[str, GuardModelConfig] = {}
        for dim in target_dims:
            model = self._registry.get_model_by_dimension(dim)
            if model and model.id in self._clients:
                dispatch_plan[dim] = model

        # If no specific dimensions matched, use default model
        if not dispatch_plan:
            default = self._registry.get_default_model()
            if default:
                dispatch_plan["content_safety"] = default

        routing_info = {
            "method": routing_method,
            "dimensions_requested": target_dims,
            "models_dispatched": {dim: m.id for dim, m in dispatch_plan.items()},
        }

        # Dispatch to all models in parallel
        dimension_results = await self._dispatch_parallel(text, messages, dispatch_plan)

        # Aggregate results
        return self._aggregate(dimension_results, routing_info)

    def _select_dimensions(self, text: str, messages: List[Dict]) -> List[str]:
        """Auto-select which safety dimensions to check based on content features."""
        dims = []

        # Always check content safety (use language to pick the right one)
        lang, conf = _detect_language(text)
        if lang == "zh" and conf > 0.6:
            dims.append("chinese_safety")
        elif lang == "en" and conf > 0.6:
            dims.append("english_safety")
        elif lang == "other":
            dims.append("multilingual_safety")
        else:
            dims.append("chinese_safety")  # mixed content → default

        # Always check prompt injection
        dims.append("prompt_injection")

        # Check for PII
        if self._likely_contains_pii(text):
            dims.append("pii_detection")

        # Check for code
        if _has_code(text):
            dims.append("code_security")

        # Check for image content
        if any(isinstance(m.get("content"), list) and
               any(p.get("type") == "image_url" for p in m["content"] if isinstance(p, dict))
               for m in messages):
            dims.append("image_safety")

        # Check for tool calls
        if any(m.get("tool_calls") for m in messages):
            dims.append("agent_safety")

        # Short safe content → fast screening only
        if len(text) < 100 and len(dims) == 2:  # only content_safety + injection
            dims = ["fast_screening"]

        # ML classifier as additional signal
        if self._ml_classifier and self._ml_classifier.is_available:
            ml_result = self._ml_classifier.classify(text, self._registry.ml_min_confidence)
            if ml_result:
                ml_dim, ml_conf = ml_result
                if ml_dim not in dims:
                    dims.append(ml_dim)
                    logger.debug(f"ML added dimension: {ml_dim} ({ml_conf:.3f})")

        return dims

    def _likely_contains_pii(self, text: str) -> bool:
        """Fast heuristic for PII presence."""
        patterns = [
            r'\b\d{3}[-.]?\d{2}[-.]?\d{4}\b',  # SSN-like
            r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # credit card
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # email
            r'\b1[3-9]\d{9}\b',  # Chinese phone
            r'(?:sk-|api[_-]?key|password|secret|token)\s*[:=]\s*\S+',  # credentials
        ]
        return any(re.search(p, text) for p in patterns)

    async def _dispatch_parallel(
        self,
        text: str,
        messages: List[Dict],
        dispatch_plan: Dict[str, GuardModelConfig],
    ) -> List[DimensionResult]:
        """Call multiple guard models in parallel."""

        async def _call_one(dim: str, model: GuardModelConfig) -> DimensionResult:
            client = self._clients.get(model.id)
            if not client:
                return DimensionResult(
                    dimension=dim, model_id=model.id, model_name=model.name,
                    safe=True, error="Client not available",
                )
            try:
                result = await client.check(text, messages)
                return DimensionResult(
                    dimension=dim,
                    model_id=result.get("model_id", model.id),
                    model_name=model.name,
                    safe=result["safe"],
                    details=result.get("details", []),
                    score=result.get("score", 0.0),
                )
            except GuardModelError as e:
                logger.warning(f"Model {model.id} failed for {dim}: {e}")
                return DimensionResult(
                    dimension=dim, model_id=model.id, model_name=model.name,
                    safe=True, error=str(e),  # fail-open per dimension
                )

        tasks = [_call_one(dim, model) for dim, model in dispatch_plan.items()]
        return await asyncio.gather(*tasks)

    def _aggregate(self, results: List[DimensionResult], routing_info: Dict) -> CheckResult:
        """Aggregate results from multiple dimensions into a single verdict."""
        flagged = [r.dimension for r in results if not r.safe]

        if not flagged:
            risk = "safe"
        elif any(d in flagged for d in ("prompt_injection", "jailbreak", "child_safety")):
            risk = "high"
        elif any(d in flagged for d in ("chinese_safety", "english_safety", "self_harm", "agent_safety")):
            risk = "high"
        elif any(d in flagged for d in ("toxicity", "pii_detection", "code_security")):
            risk = "medium"
        else:
            risk = "low"

        return CheckResult(
            safe=len(flagged) == 0,
            risk_level=risk,
            flagged_dimensions=flagged,
            dimension_results=results,
            routing_info=routing_info,
        )

    async def check_sync_wrapper(self, text: str, **kwargs) -> CheckResult:
        """Convenience wrapper for sync contexts."""
        return await self.check(text, **kwargs)

    async def close(self):
        """Close all HTTP clients."""
        for client in self._clients.values():
            await client.close()
