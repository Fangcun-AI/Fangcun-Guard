from typing import Any, Dict, List

from database.models import Scanner, ScannerPackage
from utils.logger import setup_logger

logger = setup_logger()


class ScannerPackagePresenter:
    """Serialization and normalization helpers for scanner packages."""

    def normalize_risk_level(self, risk_level: str) -> str:
        risk_mapping = {
            "high": "high_risk",
            "medium": "medium_risk",
            "low": "low_risk",
            "high_risk": "high_risk",
            "medium_risk": "medium_risk",
            "low_risk": "low_risk",
        }

        result = risk_mapping.get(risk_level, "medium_risk")
        if result != risk_level:
            logger.info(f"Normalized risk level '{risk_level}' to '{result}'")

        if result not in ["high_risk", "medium_risk", "low_risk"]:
            logger.warning(f"Invalid risk level '{risk_level}', defaulting to 'medium_risk'")
            return "medium_risk"

        return result

    def serialize_scanner(self, scanner: Scanner, include_definition: bool = True) -> Dict[str, Any]:
        if scanner.default_scan_prompt and scanner.default_scan_response:
            scan_target = "both"
        elif scanner.default_scan_prompt:
            scan_target = "prompt"
        elif scanner.default_scan_response:
            scan_target = "response"
        else:
            scan_target = "both"

        risk_level = scanner.default_risk_level.replace("_risk", "") if scanner.default_risk_level else "medium"
        scanner_info = {
            "id": str(scanner.id),
            "scanner_tag": scanner.tag,
            "scanner_name": scanner.name,
            "tag": scanner.tag,
            "name": scanner.name,
            "description": scanner.description,
            "scanner_type": scanner.scanner_type,
            "risk_level": risk_level,
            "default_risk_level": scanner.default_risk_level,
            "scan_target": scan_target,
            "default_scan_prompt": scanner.default_scan_prompt,
            "default_scan_response": scanner.default_scan_response,
            "is_active": scanner.is_active,
        }
        scanner_info["definition"] = scanner.definition if include_definition else None
        return scanner_info

    def build_package_detail(
        self,
        package: ScannerPackage,
        scanners: List[Scanner],
        *,
        include_definitions: bool = True,
        include_marketplace_fields: bool = False,
    ) -> Dict[str, Any]:
        scanner_list = [
            self.serialize_scanner(scanner, include_definition=include_definitions)
            for scanner in scanners
        ]

        detail = {
            "id": str(package.id),
            "package_code": package.package_code,
            "package_name": package.package_name,
            "author": package.author,
            "description": package.description,
            "version": package.version,
            "license": package.license,
            "package_type": package.package_type,
            "scanner_count": len(scanner_list),
            "scanners": scanner_list,
            "created_at": package.created_at.isoformat() if package.created_at else None,
            "updated_at": package.updated_at.isoformat() if package.updated_at else None,
        }

        if include_marketplace_fields:
            detail["price"] = package.price
            detail["price_display"] = package.price_display

        return detail
