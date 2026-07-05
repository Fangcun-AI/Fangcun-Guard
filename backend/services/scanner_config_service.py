from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from database.models import (
    ApplicationScannerConfig,
    CustomScanner,
    PackagePurchase,
    Scanner,
    ScannerPackage,
    Tenant,
)
from services.scanner_policy import (
    PURCHASED_PACKAGE_TYPES,
    apply_config_updates,
    reset_config_overrides,
    scanner_config_payload,
)
from utils.logger import setup_logger

logger = setup_logger()


class ScannerConfigService:
    """Resolve package defaults and application-specific scanner overrides."""

    def __init__(self, db: Session):
        self.db = db

    def get_application_scanners(
        self,
        application_id: UUID,
        tenant_id: UUID,
        include_disabled: bool = True,
    ) -> List[Dict[str, Any]]:
        packaged = [(scanner, False) for scanner in self._get_available_scanners(tenant_id)]
        custom = [(scanner, True) for scanner in self._get_custom_scanners(application_id)]
        config_map = self._config_map(application_id)

        result = []
        for scanner, is_custom in packaged + custom:
            payload = scanner_config_payload(
                scanner, config_map.get(str(scanner.id)), is_custom=is_custom
            )
            if include_disabled or payload["is_enabled"]:
                result.append(payload)
        return result

    def get_enabled_scanners(
        self,
        application_id: UUID,
        tenant_id: UUID,
        scan_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        scanners = self.get_application_scanners(
            application_id, tenant_id, include_disabled=False
        )
        if scan_type == "prompt":
            return [scanner for scanner in scanners if scanner["scan_prompt"]]
        if scan_type == "response":
            return [scanner for scanner in scanners if scanner["scan_response"]]
        return scanners

    def update_scanner_config(
        self, application_id: UUID, scanner_id: UUID, updates: Dict[str, Any]
    ) -> ApplicationScannerConfig:
        config = self._upsert_config(application_id, scanner_id)
        apply_config_updates(config, updates)
        self.db.commit()
        self.db.refresh(config)
        logger.info(
            f"Updated scanner config: app={application_id}, scanner={scanner_id}, "
            f"updates={list(updates)}"
        )
        return config

    def bulk_update_scanner_configs(
        self, application_id: UUID, updates: List[Dict[str, Any]]
    ) -> List[ApplicationScannerConfig]:
        configs = []
        for update in updates:
            scanner_id = UUID(update["scanner_id"])
            config = self._upsert_config(application_id, scanner_id)
            apply_config_updates(config, update)
            configs.append(config)

        self.db.commit()
        for config in configs:
            self.db.refresh(config)
        logger.info(f"Bulk updated {len(configs)} scanner configs for app={application_id}")
        return configs

    def reset_scanner_config(self, application_id: UUID, scanner_id: UUID) -> bool:
        config = self._find_config(application_id, scanner_id)
        if not config:
            return False
        reset_config_overrides(config)
        self.db.commit()
        logger.info(f"Reset scanner config: app={application_id}, scanner={scanner_id}")
        return True

    def reset_all_configs(self, application_id: UUID) -> int:
        configs = (
            self.db.query(ApplicationScannerConfig)
            .filter(ApplicationScannerConfig.application_id == application_id)
            .all()
        )
        for config in configs:
            reset_config_overrides(config)
        self.db.commit()
        logger.info(f"Reset {len(configs)} scanner configs for app={application_id}")
        return len(configs)

    def initialize_default_configs(self, application_id: UUID, tenant_id: UUID) -> int:
        existing_ids = {
            str(config.scanner_id)
            for config in self.db.query(ApplicationScannerConfig)
            .filter(ApplicationScannerConfig.application_id == application_id)
            .all()
        }
        created = 0
        for scanner in self._get_available_scanners(tenant_id):
            if str(scanner.id) in existing_ids:
                continue
            self.db.add(
                ApplicationScannerConfig(
                    application_id=application_id,
                    scanner_id=scanner.id,
                    is_enabled=True,
                )
            )
            created += 1
        self.db.commit()
        logger.info(f"Initialized {created} scanner configs for app={application_id}")
        return created

    def _get_available_scanners(self, tenant_id: UUID) -> List[Scanner]:
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        is_super_admin = bool(getattr(tenant, "is_super_admin", False))

        basic = (
            self.db.query(Scanner)
            .join(ScannerPackage)
            .filter(
                ScannerPackage.package_type == "basic",
                ScannerPackage.is_active == True,
                Scanner.is_active == True,
            )
            .all()
        )
        if is_super_admin:
            premium = (
                self.db.query(Scanner)
                .join(ScannerPackage)
                .filter(
                    ScannerPackage.package_type.in_(PURCHASED_PACKAGE_TYPES),
                    ScannerPackage.is_active == True,
                    Scanner.is_active == True,
                )
                .all()
            )
            return basic + premium

        package_ids = [
            row[0]
            for row in self.db.query(PackagePurchase.package_id)
            .filter(
                PackagePurchase.tenant_id == tenant_id,
                PackagePurchase.status == "approved",
            )
            .all()
        ]
        if not package_ids:
            return basic

        purchased = (
            self.db.query(Scanner)
            .filter(Scanner.package_id.in_(package_ids), Scanner.is_active == True)
            .all()
        )
        return basic + purchased

    def _get_custom_scanners(self, application_id: UUID) -> List[Scanner]:
        return (
            self.db.query(Scanner)
            .join(CustomScanner)
            .filter(
                CustomScanner.application_id == application_id,
                Scanner.is_active == True,
            )
            .all()
        )

    def _config_map(self, application_id: UUID) -> Dict[str, ApplicationScannerConfig]:
        configs = (
            self.db.query(ApplicationScannerConfig)
            .filter(ApplicationScannerConfig.application_id == application_id)
            .all()
        )
        return {str(config.scanner_id): config for config in configs}

    def _find_config(
        self, application_id: UUID, scanner_id: UUID
    ) -> Optional[ApplicationScannerConfig]:
        return (
            self.db.query(ApplicationScannerConfig)
            .filter(
                ApplicationScannerConfig.application_id == application_id,
                ApplicationScannerConfig.scanner_id == scanner_id,
            )
            .first()
        )

    def _upsert_config(
        self, application_id: UUID, scanner_id: UUID
    ) -> ApplicationScannerConfig:
        config = self._find_config(application_id, scanner_id)
        if config:
            return config
        config = ApplicationScannerConfig(
            application_id=application_id, scanner_id=scanner_id
        )
        self.db.add(config)
        return config
