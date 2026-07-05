import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from database.models import ApplicationScannerConfig, CustomScanner, Scanner
from services.scanner_policy import (
    apply_custom_scanner_updates,
    custom_scanner_payload,
    validate_custom_scanner_data,
)
from utils.logger import setup_logger

logger = setup_logger()


class CustomScannerRegistryService:
    """CRUD operations for application-owned scanner definitions."""

    def __init__(self, db: Session):
        self.db = db

    def get_custom_scanners(self, application_id: UUID) -> List[Dict[str, Any]]:
        records = (
            self.db.query(CustomScanner)
            .join(Scanner)
            .filter(
                CustomScanner.application_id == application_id,
                Scanner.is_active == True,
            )
            .all()
        )
        config_map = self._config_map(application_id)
        return [
            custom_scanner_payload(record, config_map.get(str(record.scanner.id)))
            for record in records
        ]

    def get_custom_scanner(
        self, scanner_id: UUID, application_id: UUID
    ) -> Optional[Dict[str, Any]]:
        record = self._find_custom_scanner(scanner_id, application_id, active_only=True)
        if not record:
            return None
        return custom_scanner_payload(
            record, self._find_config(application_id, record.scanner.id)
        )

    def create_custom_scanner(
        self, application_id: UUID, tenant_id: UUID, scanner_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        validate_custom_scanner_data(scanner_data)
        scanner = Scanner(
            package_id=None,
            tag=self._get_next_custom_tag(application_id),
            name=scanner_data["name"],
            description=scanner_data.get("description", scanner_data["definition"]),
            scanner_type=scanner_data["scanner_type"],
            definition=scanner_data["definition"],
            default_risk_level=scanner_data["risk_level"],
            default_scan_prompt=scanner_data.get("scan_prompt", True),
            default_scan_response=scanner_data.get("scan_response", True),
            is_active=True,
        )
        self.db.add(scanner)
        self.db.flush()

        record = CustomScanner(
            application_id=application_id,
            scanner_id=scanner.id,
            created_by=tenant_id,
            notes=scanner_data.get("notes"),
        )
        self.db.add(record)
        self.db.add(
            ApplicationScannerConfig(
                application_id=application_id, scanner_id=scanner.id, is_enabled=True
            )
        )
        self.db.commit()
        self.db.refresh(scanner)
        self.db.refresh(record)
        logger.info(f"Created custom scanner {scanner.tag} for app={application_id}")
        self._create_response_template(scanner, application_id, tenant_id)
        return custom_scanner_payload(record)

    def update_custom_scanner(
        self, scanner_id: UUID, application_id: UUID, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        record = self._find_custom_scanner(scanner_id, application_id)
        if not record:
            return None

        apply_custom_scanner_updates(record.scanner, updates)
        if "notes" in updates:
            record.notes = updates["notes"]
        if "is_enabled" in updates:
            config = self._find_config(application_id, scanner_id)
            if not config:
                config = ApplicationScannerConfig(
                    application_id=application_id, scanner_id=scanner_id
                )
                self.db.add(config)
            config.is_enabled = updates["is_enabled"]

        self.db.commit()
        self.db.refresh(record.scanner)
        self.db.refresh(record)
        logger.info(f"Updated custom scanner {record.scanner.tag}: {list(updates)}")
        return self.get_custom_scanner(scanner_id, application_id)

    def delete_custom_scanner(self, scanner_id: UUID, application_id: UUID) -> bool:
        record = self._find_custom_scanner(scanner_id, application_id)
        if not record:
            return False

        scanner = record.scanner
        original_tag = scanner.tag
        self._delete_response_template(original_tag, application_id)
        self._delete_knowledge_bases(original_tag, application_id)
        deleted_configs = (
            self.db.query(ApplicationScannerConfig)
            .filter(ApplicationScannerConfig.scanner_id == scanner_id)
            .delete(synchronize_session=False)
        )
        scanner.tag = f"{original_tag}_deleted_{int(time.time())}"
        scanner.is_active = False
        self.db.commit()
        logger.warning(
            f"Disabled custom scanner {original_tag} for app={application_id}; "
            f"removed {deleted_configs} config records"
        )
        return True

    def _find_custom_scanner(
        self, scanner_id: UUID, application_id: UUID, *, active_only: bool = False
    ) -> Optional[CustomScanner]:
        query = self.db.query(CustomScanner).join(Scanner).filter(
            CustomScanner.application_id == application_id,
            CustomScanner.scanner_id == scanner_id,
        )
        if active_only:
            query = query.filter(Scanner.is_active == True)
        return query.first()

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

    def _config_map(self, application_id: UUID) -> Dict[str, ApplicationScannerConfig]:
        configs = (
            self.db.query(ApplicationScannerConfig)
            .filter(ApplicationScannerConfig.application_id == application_id)
            .all()
        )
        return {str(config.scanner_id): config for config in configs}

    def _create_response_template(
        self, scanner: Scanner, application_id: UUID, tenant_id: UUID
    ) -> None:
        try:
            from services.response_template_service import ResponseTemplateService

            ResponseTemplateService(self.db).create_template_for_custom_scanner(
                scanner=scanner, application_id=application_id, tenant_id=tenant_id
            )
        except Exception as exc:
            logger.error(f"Failed to create response template for {scanner.tag}: {exc}")

    def _delete_response_template(self, scanner_tag: str, application_id: UUID) -> None:
        try:
            from services.response_template_service import ResponseTemplateService

            ResponseTemplateService(self.db).delete_template_for_scanner(
                scanner_tag=scanner_tag,
                scanner_type="custom_scanner",
                application_id=application_id,
            )
        except Exception as exc:
            logger.error(f"Failed to delete response template for {scanner_tag}: {exc}")

    def _delete_knowledge_bases(self, scanner_tag: str, application_id: UUID) -> None:
        try:
            from database.models import KnowledgeBase

            deleted = (
                self.db.query(KnowledgeBase)
                .filter(
                    KnowledgeBase.application_id == application_id,
                    KnowledgeBase.scanner_type == "custom_scanner",
                    KnowledgeBase.scanner_identifier == scanner_tag,
                )
                .delete(synchronize_session=False)
            )
            if deleted:
                logger.info(f"Deleted {deleted} knowledge bases for {scanner_tag}")
        except Exception as exc:
            logger.error(f"Failed to delete knowledge bases for {scanner_tag}: {exc}")

    def _validate_scanner_data(self, scanner_data: Dict[str, Any]) -> None:
        validate_custom_scanner_data(scanner_data)

    def _get_next_custom_tag(self, application_id: UUID) -> str:
        highest_number = (
            self.db.query(func.max(func.cast(func.substr(Scanner.tag, 2), Integer)))
            .filter(
                Scanner.tag.like("S%"),
                Scanner.tag.op("~")("^[S][0-9]+$"),
                Scanner.is_active == True,
            )
            .scalar()
        )
        return "S100" if highest_number is None or highest_number < 100 else f"S{highest_number + 1}"
