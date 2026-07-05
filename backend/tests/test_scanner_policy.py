from dataclasses import dataclass, field

from services.scanner_policy import (
    ScannerRuntimeSettings,
    apply_config_updates,
    apply_custom_scanner_updates,
    apply_manifest,
    custom_scanner_payload,
    scanner_config_payload,
    uses_compact_definition,
    validate_custom_scanner_data,
)


@dataclass
class Package:
    package_name: str = "Basic"
    package_type: str = "basic"


@dataclass
class Scanner:
    id: str = "scanner-a"
    package_id: str = "package-a"
    package: object = field(default_factory=Package)
    tag: str = "S1"
    name: str = "Scanner"
    description: str = "Description"
    definition: str = "Definition"
    scanner_type: str = "genai"
    default_risk_level: str = "low_risk"
    default_scan_prompt: bool = True
    default_scan_response: bool = False
    is_active: bool = True


@dataclass
class Config:
    is_enabled: bool = True
    risk_level_override: object = None
    scan_prompt_override: object = None
    scan_response_override: object = None


@dataclass
class CustomRecord:
    scanner: object
    id: str = "custom-a"
    notes: str = "Notes"
    created_by: str = "tenant-a"
    created_at: object = None
    updated_at: object = None


def test_runtime_settings_preserve_false_overrides():
    settings = ScannerRuntimeSettings.resolve(
        Scanner(), Config(scan_prompt_override=False, scan_response_override=True)
    )

    assert settings.scan_prompt is False
    assert settings.scan_response is True


def test_scanner_payload_exposes_effective_and_default_settings():
    payload = scanner_config_payload(
        Scanner(), Config(risk_level_override="high_risk"), is_custom=False
    )

    assert payload["risk_level"] == "high_risk"
    assert payload["default_risk_level"] == "low_risk"
    assert payload["has_risk_level_override"] is True
    assert payload["package_type"] == "basic"


def test_custom_scanner_update_aliases_target_model_fields():
    scanner = Scanner()
    config = Config()

    apply_custom_scanner_updates(
        scanner, {"risk_level": "high_risk", "scan_prompt": False}
    )
    apply_config_updates(config, {"is_enabled": False, "scan_response": True})

    assert scanner.default_risk_level == "high_risk"
    assert scanner.default_scan_prompt is False
    assert config.is_enabled is False
    assert config.scan_response_override is True


def test_custom_scanner_payload_defaults_to_enabled():
    assert custom_scanner_payload(CustomRecord(Scanner()))["is_enabled"] is True


def test_manifest_application_updates_existing_scanner():
    scanner = Scanner()
    apply_manifest(
        scanner,
        "package-b",
        {
            "tag": "S2",
            "name": "Updated",
            "definition": "Updated definition",
            "type": "keyword",
            "risk_level": "high_risk",
        },
    )

    assert scanner.package_id == "package-b"
    assert scanner.tag == "S2"
    assert scanner.default_scan_response is False


def test_official_package_types_use_compact_definitions():
    assert uses_compact_definition("basic") is True
    assert uses_compact_definition("purchasable") is True
    assert uses_compact_definition("custom") is False


def test_custom_scanner_validation_rejects_invalid_type():
    try:
        validate_custom_scanner_data(
            {
                "name": "Scanner",
                "scanner_type": "shell",
                "definition": "Definition",
                "risk_level": "high_risk",
            }
        )
    except ValueError:
        return
    raise AssertionError("Expected invalid scanner type to be rejected")
