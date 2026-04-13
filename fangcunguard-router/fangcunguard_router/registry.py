"""Guard Model Registry - loads guard_models.yaml and provides model configs."""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger("fangcunguard_router")

_ENV_VAR_PATTERN = re.compile(r'\$\{([^}:]+)(?::-([^}]*))?\}')


def _resolve_env(value: str) -> str:
    """Replace ${VAR} or ${VAR:-default} with env values."""
    def _rep(m):
        return os.environ.get(m.group(1), m.group(2) if m.group(2) is not None else "")
    return _ENV_VAR_PATTERN.sub(_rep, value)


@dataclass
class GuardModelConfig:
    id: str
    name: str
    api_url: str
    api_key: str
    model_name: str
    api_type: str = "chat_completion"
    prompt_format: str = "inst"
    response_format: str = "safe_unsafe_tags"
    dimension: str = ""
    description: str = ""
    specialties: List[str] = field(default_factory=list)
    max_context_length: int = 8192
    is_default: bool = False
    failure_threshold: int = 5
    cooldown_seconds: float = 30.0


@dataclass
class RoutingCondition:
    language: Optional[str] = None
    min_confidence: float = 0.8
    max_content_length: Optional[int] = None
    no_assistant_messages: Optional[bool] = None
    only_scanner_tags: Optional[List[str]] = None
    has_image: Optional[bool] = None
    has_code: Optional[bool] = None
    has_tool_calls: Optional[bool] = None
    dimension: Optional[str] = None


@dataclass
class RoutingRule:
    name: str
    description: str
    condition: RoutingCondition
    target_model: str
    priority: int = 0


class GuardModelRegistry:
    """Loads guard_models.yaml and provides model configs + routing rules."""

    def __init__(self, config_path: str):
        self._models: Dict[str, GuardModelConfig] = {}
        self._rules: List[RoutingRule] = []
        self._default_model_id: str = ""
        self._routing_enabled: bool = False
        self._ml_fallback_enabled: bool = False
        self._ml_min_confidence: float = 0.6

        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        self._load(path)

    def _load(self, path: Path):
        with open(path) as f:
            config = yaml.safe_load(f)

        # Load models
        for mid, mdata in config.get("models", {}).items():
            api_url = _resolve_env(str(mdata.get("api_url", "")))
            api_key = _resolve_env(str(mdata.get("api_key", "")))
            model_name = _resolve_env(str(mdata.get("model_name", "")))

            if not api_url:
                logger.debug(f"Model '{mid}' skipped: no api_url")
                continue

            cb = mdata.get("circuit_breaker", {})
            self._models[mid] = GuardModelConfig(
                id=mid,
                name=mdata.get("name", mid),
                api_url=api_url.rstrip("/"),
                api_key=api_key,
                model_name=model_name,
                api_type=mdata.get("api_type", "chat_completion"),
                prompt_format=mdata.get("prompt_format", "inst"),
                response_format=mdata.get("response_format", "safe_unsafe_tags"),
                dimension=mdata.get("dimension", ""),
                description=mdata.get("description", ""),
                specialties=mdata.get("specialties", []),
                max_context_length=mdata.get("max_context_length", 8192),
                is_default=mdata.get("is_default", False),
                failure_threshold=cb.get("failure_threshold", 5),
                cooldown_seconds=cb.get("cooldown_seconds", 30.0),
            )
            if mdata.get("is_default"):
                self._default_model_id = mid

        # Routing config
        routing = config.get("routing", {})
        self._routing_enabled = routing.get("enabled", False)
        if routing.get("default_model"):
            self._default_model_id = routing["default_model"]

        ml = routing.get("ml_fallback", {})
        self._ml_fallback_enabled = ml.get("enabled", False)
        self._ml_min_confidence = ml.get("min_confidence", 0.6)

        # Load rules
        for rd in routing.get("rules", []):
            cd = rd.get("condition", {})
            cond = RoutingCondition(
                language=cd.get("language"),
                min_confidence=cd.get("min_confidence", 0.8),
                max_content_length=cd.get("max_content_length"),
                no_assistant_messages=cd.get("no_assistant_messages"),
                only_scanner_tags=cd.get("only_scanner_tags"),
                has_image=cd.get("has_image"),
                has_code=cd.get("has_code"),
                has_tool_calls=cd.get("has_tool_calls"),
                dimension=cd.get("dimension"),
            )
            rule = RoutingRule(
                name=rd.get("name", "unnamed"),
                description=rd.get("description", ""),
                condition=cond,
                target_model=rd.get("target_model", ""),
                priority=rd.get("priority", 0),
            )
            if rule.target_model in self._models:
                self._rules.append(rule)

        self._rules.sort(key=lambda r: r.priority, reverse=True)

        if self._default_model_id not in self._models and self._models:
            self._default_model_id = next(iter(self._models))

        logger.info(f"Registry loaded: {len(self._models)} models, "
                     f"{len(self._rules)} rules, default='{self._default_model_id}'")

    def get_model(self, model_id: str) -> Optional[GuardModelConfig]:
        return self._models.get(model_id)

    def get_default_model(self) -> Optional[GuardModelConfig]:
        return self._models.get(self._default_model_id)

    def get_all_models(self) -> Dict[str, GuardModelConfig]:
        return self._models

    def get_model_by_dimension(self, dimension: str) -> Optional[GuardModelConfig]:
        for m in self._models.values():
            if m.dimension == dimension:
                return m
        return None

    def get_models_for_dimensions(self, dimensions: List[str]) -> Dict[str, GuardModelConfig]:
        """Get models for multiple dimensions at once."""
        result = {}
        for dim in dimensions:
            m = self.get_model_by_dimension(dim)
            if m:
                result[dim] = m
        return result

    @property
    def routing_enabled(self) -> bool:
        return self._routing_enabled

    @property
    def rules(self) -> List[RoutingRule]:
        return self._rules

    @property
    def ml_fallback_enabled(self) -> bool:
        return self._ml_fallback_enabled

    @property
    def ml_min_confidence(self) -> float:
        return self._ml_min_confidence
