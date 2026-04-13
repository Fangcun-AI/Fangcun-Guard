"""
Guard Model Registry - Loads and manages guard model configurations.

Reads guard_models.yaml at startup, resolves environment variables,
and provides typed GuardModelConfig instances to the router and model service.

Backward compatible: if no config file is specified, creates a single-model
registry from existing settings (guardrails_model_api_url, etc.).
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from utils.logger import setup_logger

logger = setup_logger()

# Regex for ${VAR_NAME} and ${VAR_NAME:-default} patterns
_ENV_VAR_PATTERN = re.compile(r'\$\{([^}:]+)(?::-([^}]*))?\}')


def _resolve_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} or ${VAR_NAME:-default} with environment variable values."""
    def _replacer(match):
        var_name = match.group(1)
        default_value = match.group(2) if match.group(2) is not None else ""
        return os.environ.get(var_name, default_value)
    return _ENV_VAR_PATTERN.sub(_replacer, value)


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    cooldown_seconds: float = 30.0


@dataclass
class GuardModelConfig:
    id: str
    name: str
    api_url: str
    api_key: str
    model_name: str
    prompt_format: str  # "qwen3guard" | "inst" | "llamaguard4" | "wildguard" | etc.
    response_format: str  # "qwen3guard" | "safe_unsafe_tags" | "llamaguard4" | etc.
    api_type: str = "chat_completion"  # "chat_completion" | "classification" | "moderation" | "ner" | "custom"
    dimension: str = ""  # The safety dimension this model specializes in
    description: str = ""
    specialties: List[str] = field(default_factory=list)
    max_context_length: int = 8192
    is_default: bool = False
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)


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
    """Singleton registry for guard model configurations and routing rules."""

    def __init__(self, config_path: str = ""):
        self._models: Dict[str, GuardModelConfig] = {}
        self._rules: List[RoutingRule] = []
        self._default_model_id: str = ""
        self._routing_enabled: bool = False

        if config_path:
            resolved_path = self._resolve_config_path(config_path)
            if resolved_path and resolved_path.exists():
                self._load_from_yaml(resolved_path)
            else:
                logger.warning(f"Guard models config not found at '{config_path}', "
                               "falling back to single-model mode")
                self._load_from_settings()
        else:
            self._load_from_settings()

    def _resolve_config_path(self, config_path: str) -> Optional[Path]:
        """Resolve config path relative to backend/ directory."""
        path = Path(config_path)
        if path.is_absolute():
            return path
        # Relative to backend/ directory
        backend_dir = Path(__file__).parent.parent
        return backend_dir / config_path

    def _load_from_yaml(self, path: Path):
        """Load configuration from YAML file."""
        try:
            with open(path) as f:
                config = yaml.safe_load(f)

            if not config:
                logger.warning("Guard models config file is empty, using single-model mode")
                self._load_from_settings()
                return

            # Load models
            models_config = config.get("models", {})
            for model_id, model_data in models_config.items():
                cb_data = model_data.get("circuit_breaker", {})
                cb_config = CircuitBreakerConfig(
                    failure_threshold=cb_data.get("failure_threshold", 5),
                    cooldown_seconds=cb_data.get("cooldown_seconds", 30.0),
                )

                api_url = _resolve_env_vars(str(model_data.get("api_url", "")))
                api_key = _resolve_env_vars(str(model_data.get("api_key", "")))
                model_name = _resolve_env_vars(str(model_data.get("model_name", "")))

                # Skip models with unresolved/empty API URLs
                if not api_url:
                    logger.info(f"Guard model '{model_id}' skipped: no api_url configured")
                    continue

                model_config = GuardModelConfig(
                    id=model_id,
                    name=model_data.get("name", model_id),
                    api_url=api_url.rstrip("/"),
                    api_key=api_key,
                    model_name=model_name,
                    prompt_format=model_data.get("prompt_format", "inst"),
                    response_format=model_data.get("response_format", "safe_unsafe_tags"),
                    api_type=model_data.get("api_type", "chat_completion"),
                    dimension=model_data.get("dimension", ""),
                    description=model_data.get("description", ""),
                    specialties=model_data.get("specialties", []),
                    max_context_length=model_data.get("max_context_length", 8192),
                    is_default=model_data.get("is_default", False),
                    circuit_breaker=cb_config,
                )
                self._models[model_id] = model_config

                if model_config.is_default:
                    self._default_model_id = model_id

            # Load routing config
            routing_config = config.get("routing", {})
            self._routing_enabled = routing_config.get("enabled", False)

            if routing_config.get("default_model"):
                self._default_model_id = routing_config["default_model"]

            # Load routing rules
            for rule_data in routing_config.get("rules", []):
                cond_data = rule_data.get("condition", {})
                condition = RoutingCondition(
                    language=cond_data.get("language"),
                    min_confidence=cond_data.get("min_confidence", 0.8),
                    max_content_length=cond_data.get("max_content_length"),
                    no_assistant_messages=cond_data.get("no_assistant_messages"),
                    only_scanner_tags=cond_data.get("only_scanner_tags"),
                    has_image=cond_data.get("has_image"),
                    has_code=cond_data.get("has_code"),
                    has_tool_calls=cond_data.get("has_tool_calls"),
                    dimension=cond_data.get("dimension"),
                )
                rule = RoutingRule(
                    name=rule_data.get("name", "unnamed"),
                    description=rule_data.get("description", ""),
                    condition=condition,
                    target_model=rule_data.get("target_model", ""),
                    priority=rule_data.get("priority", 0),
                )
                # Only add rules whose target model is available
                if rule.target_model in self._models:
                    self._rules.append(rule)
                else:
                    logger.warning(f"Routing rule '{rule.name}' references unavailable model "
                                   f"'{rule.target_model}', skipping")

            # Sort rules by priority descending
            self._rules.sort(key=lambda r: r.priority, reverse=True)

            # Ensure we have a default model
            if self._default_model_id not in self._models:
                if self._models:
                    self._default_model_id = next(iter(self._models))
                    logger.warning(f"Default model not found, using '{self._default_model_id}'")
                else:
                    logger.warning("No guard models configured, falling back to settings")
                    self._load_from_settings()
                    return

            loaded_count = len(self._models)
            rule_count = len(self._rules)
            logger.info(f"Guard model registry loaded: {loaded_count} models, "
                        f"{rule_count} routing rules, "
                        f"default='{self._default_model_id}', "
                        f"routing={'enabled' if self._routing_enabled else 'disabled'}")

        except Exception as e:
            logger.error(f"Failed to load guard models config: {e}, falling back to single-model mode")
            self._load_from_settings()

    def _load_from_settings(self):
        """Create single-model registry from existing settings (backward compatibility)."""
        from config import settings

        model_id = "default"
        self._models = {
            model_id: GuardModelConfig(
                id=model_id,
                name=settings.guardrails_model_name,
                api_url=settings.guardrails_model_api_url.rstrip("/"),
                api_key=settings.guardrails_model_api_key,
                model_name=settings.guardrails_model_name,
                prompt_format="qwen3guard" if "qwen3guard" in settings.guardrails_model_name.lower() else "inst",
                response_format="qwen3guard" if "qwen3guard" in settings.guardrails_model_name.lower() else "safe_unsafe_tags",
                specialties=["chinese", "general"],
                max_context_length=settings.max_detection_context_length,
                is_default=True,
            )
        }
        self._default_model_id = model_id
        self._routing_enabled = False
        self._rules = []
        logger.info("Guard model registry: single-model mode (from settings)")

    def get_model(self, model_id: str) -> Optional[GuardModelConfig]:
        return self._models.get(model_id)

    def get_default_model(self) -> GuardModelConfig:
        return self._models[self._default_model_id]

    def get_all_models(self) -> Dict[str, GuardModelConfig]:
        return self._models

    def is_routing_enabled(self) -> bool:
        return self._routing_enabled and len(self._models) > 1

    def get_routing_rules(self) -> List[RoutingRule]:
        return self._rules

    def get_model_by_dimension(self, dimension: str) -> Optional[GuardModelConfig]:
        """Find a model that specializes in the given safety dimension."""
        for model in self._models.values():
            if model.dimension == dimension:
                return model
        return None


def _create_registry() -> GuardModelRegistry:
    """Create the global registry instance."""
    from config import settings
    return GuardModelRegistry(config_path=settings.guard_models_config_path)


# Lazy singleton - initialized on first access
_registry_instance: Optional[GuardModelRegistry] = None


def get_guard_model_registry() -> GuardModelRegistry:
    """Get or create the global guard model registry."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = _create_registry()
    return _registry_instance
