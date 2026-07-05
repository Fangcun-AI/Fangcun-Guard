from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

SCANNER_TYPES = frozenset({"genai", "regex", "keyword"})
SCANNER_RISK_LEVELS = frozenset({"low_risk", "medium_risk", "high_risk"})
PURCHASED_PACKAGE_TYPES = frozenset({"premium", "purchasable"})
COMPACT_DEFINITION_PACKAGE_TYPES = frozenset({"basic", "premium", "purchasable"})

CONFIG_UPDATE_FIELDS = {
    "is_enabled": "is_enabled",
    "risk_level": "risk_level_override",
    "scan_prompt": "scan_prompt_override",
    "scan_response": "scan_response_override",
}

CUSTOM_SCANNER_UPDATE_FIELDS = {
    "name": "name",
    "description": "description",
    "definition": "definition",
    "risk_level": "default_risk_level",
    "default_risk_level": "default_risk_level",
    "scan_prompt": "default_scan_prompt",
    "default_scan_prompt": "default_scan_prompt",
    "scan_response": "default_scan_response",
    "default_scan_response": "default_scan_response",
}


def validate_custom_scanner_data(scanner_data: Mapping[str, Any]) -> None:
    required_fields = ("name", "scanner_type", "definition", "risk_level")
    missing = [field for field in required_fields if field not in scanner_data]
    if missing:
        raise ValueError(f"Missing required field: {missing[0]}")

    if scanner_data["scanner_type"] not in SCANNER_TYPES:
        raise ValueError(
            f"Invalid scanner_type: {scanner_data['scanner_type']}. "
            f"Must be one of: {', '.join(sorted(SCANNER_TYPES))}"
        )
    if scanner_data["risk_level"] not in SCANNER_RISK_LEVELS:
        raise ValueError(
            f"Invalid risk_level: {scanner_data['risk_level']}. "
            f"Must be one of: {', '.join(sorted(SCANNER_RISK_LEVELS))}"
        )
    if not scanner_data["name"] or len(scanner_data["name"]) > 200:
        raise ValueError("Name must contain 1 to 200 characters")
    if not scanner_data["definition"] or len(scanner_data["definition"]) > 2000:
        raise ValueError("Definition must contain 1 to 2000 characters")


def apply_config_updates(config: object, updates: Mapping[str, Any]) -> None:
    for input_field, model_field in CONFIG_UPDATE_FIELDS.items():
        if input_field in updates:
            setattr(config, model_field, updates[input_field])


def apply_custom_scanner_updates(scanner: object, updates: Mapping[str, Any]) -> None:
    for input_field, model_field in CUSTOM_SCANNER_UPDATE_FIELDS.items():
        if input_field in updates:
            setattr(scanner, model_field, updates[input_field])


def reset_config_overrides(config: object) -> None:
    config.is_enabled = True
    config.risk_level_override = None
    config.scan_prompt_override = None
    config.scan_response_override = None


def uses_compact_definition(package_type: Optional[str]) -> bool:
    return package_type in COMPACT_DEFINITION_PACKAGE_TYPES


def _effective(config: Optional[object], override_field: str, default: Any) -> Any:
    override = getattr(config, override_field, None)
    return default if override is None else override


@dataclass(frozen=True)
class ScannerRuntimeSettings:
    enabled: bool
    risk_level: str
    scan_prompt: bool
    scan_response: bool

    @classmethod
    def resolve(
        cls, scanner: object, config: Optional[object] = None
    ) -> "ScannerRuntimeSettings":
        return cls(
            enabled=getattr(config, "is_enabled", True),
            risk_level=_effective(
                config, "risk_level_override", scanner.default_risk_level
            ),
            scan_prompt=_effective(
                config, "scan_prompt_override", scanner.default_scan_prompt
            ),
            scan_response=_effective(
                config, "scan_response_override", scanner.default_scan_response
            ),
        )


def scanner_config_payload(
    scanner: object, config: Optional[object] = None, *, is_custom: bool = False
) -> Dict[str, Any]:
    package = getattr(scanner, "package", None)
    settings = ScannerRuntimeSettings.resolve(scanner, config)
    return {
        "id": str(scanner.id),
        "tag": scanner.tag,
        "name": scanner.name,
        "description": scanner.description,
        "definition": scanner.definition,
        "scanner_type": scanner.scanner_type,
        "package_name": package.package_name if package else "Custom",
        "package_id": str(scanner.package_id) if scanner.package_id else None,
        "package_type": package.package_type if package else "custom",
        "is_custom": is_custom,
        "is_enabled": settings.enabled,
        "risk_level": settings.risk_level,
        "scan_prompt": settings.scan_prompt,
        "scan_response": settings.scan_response,
        "default_risk_level": scanner.default_risk_level,
        "default_scan_prompt": scanner.default_scan_prompt,
        "default_scan_response": scanner.default_scan_response,
        "has_risk_level_override": getattr(config, "risk_level_override", None) is not None,
        "has_scan_prompt_override": getattr(config, "scan_prompt_override", None) is not None,
        "has_scan_response_override": getattr(config, "scan_response_override", None) is not None,
    }


def custom_scanner_payload(
    custom_scanner: object, config: Optional[object] = None
) -> Dict[str, Any]:
    scanner = custom_scanner.scanner
    return {
        "id": str(scanner.id),
        "custom_scanner_id": str(custom_scanner.id),
        "tag": scanner.tag,
        "name": scanner.name,
        "description": scanner.description,
        "scanner_type": scanner.scanner_type,
        "definition": scanner.definition,
        "default_risk_level": scanner.default_risk_level,
        "default_scan_prompt": scanner.default_scan_prompt,
        "default_scan_response": scanner.default_scan_response,
        "notes": custom_scanner.notes,
        "created_by": str(custom_scanner.created_by),
        "created_at": custom_scanner.created_at.isoformat()
        if custom_scanner.created_at
        else None,
        "updated_at": custom_scanner.updated_at.isoformat()
        if custom_scanner.updated_at
        else None,
        "is_enabled": getattr(config, "is_enabled", True),
    }


def apply_manifest(scanner: object, package_id: object, scanner_data: Mapping[str, Any]) -> None:
    scanner.package_id = package_id
    scanner.tag = scanner_data["tag"]
    scanner.name = scanner_data["name"]
    scanner.description = scanner_data.get("description", scanner_data["definition"])
    scanner.scanner_type = scanner_data["type"]
    scanner.definition = scanner_data["definition"]
    scanner.default_risk_level = scanner_data["risk_level"]
    scanner.default_scan_prompt = scanner_data.get("scan_prompt", True)
    scanner.default_scan_response = scanner_data.get("scan_response", False)
    scanner.is_active = True
