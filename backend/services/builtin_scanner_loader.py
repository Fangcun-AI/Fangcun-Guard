"""Load official scanner manifests and seed application defaults."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from database.models import (
    Application,
    ApplicationScannerConfig,
    RiskTypeConfig,
    Scanner,
    ScannerPackage,
)
from services.risk_policy import risk_switches_from_record
from services.scanner_policy import apply_manifest
from utils.logger import setup_logger

logger = setup_logger()


def _read_manifest(file_path: Path) -> dict:
    with file_path.open(encoding="utf-8") as manifest_file:
        return json.load(manifest_file)


def _sync_package(db: Session, manifest: dict) -> ScannerPackage:
    package = (
        db.query(ScannerPackage)
        .filter(ScannerPackage.package_code == manifest["package_code"])
        .first()
    )
    values = {
        "package_name": manifest["package_name"],
        "author": manifest["author"],
        "description": manifest["description"],
        "version": manifest["version"],
        "license": manifest.get("license", "Apache-2.0"),
        "bundle": manifest.get("bundle"),
        "package_type": "basic",
        "is_active": True,
    }
    if package:
        for field, value in values.items():
            setattr(package, field, value)
    else:
        package = ScannerPackage(package_code=manifest["package_code"], **values)
        db.add(package)
    db.flush()
    return package


def _sync_scanners(
    db: Session, package: ScannerPackage, scanner_manifests: Iterable[dict]
) -> List[Scanner]:
    scanners = []
    for scanner_manifest in scanner_manifests:
        scanner = (
            db.query(Scanner)
            .filter(Scanner.tag == scanner_manifest["tag"])
            .first()
        )
        if not scanner:
            scanner = Scanner()
            db.add(scanner)
        apply_manifest(scanner, package.id, scanner_manifest)
        db.flush()
        scanners.append(scanner)
    return scanners


def _active_applications(db: Session) -> List[Application]:
    return db.query(Application).filter(Application.is_active == True).all()


def _existing_config_ids(db: Session, application_id) -> set:
    return {
        str(config.scanner_id)
        for config in db.query(ApplicationScannerConfig)
        .filter(ApplicationScannerConfig.application_id == application_id)
        .all()
    }


def _seed_scanner_configs(db: Session, scanners: List[Scanner]) -> None:
    for application in _active_applications(db):
        risk_record = (
            db.query(RiskTypeConfig)
            .filter(RiskTypeConfig.application_id == application.id)
            .first()
        )
        risk_switches = risk_switches_from_record(risk_record)
        configured = _existing_config_ids(db, application.id)
        for scanner in scanners:
            if str(scanner.id) in configured:
                continue
            db.add(
                ApplicationScannerConfig(
                    application_id=application.id,
                    scanner_id=scanner.id,
                    is_enabled=risk_switches.get(scanner.tag, True),
                    risk_level_override=None,
                    scan_prompt_override=None,
                    scan_response_override=None,
                )
            )
        db.flush()


def _seed_response_templates(db: Session, scanners: List[Scanner]) -> None:
    from services.response_template_service import ResponseTemplateService

    template_service = ResponseTemplateService(db)
    for application in _active_applications(db):
        for scanner in scanners:
            if not scanner.is_active:
                continue
            try:
                template_service.create_template_for_official_scanner(
                    scanner=scanner,
                    application_id=application.id,
                    tenant_id=application.tenant_id,
                )
            except Exception as exc:
                logger.error(
                    f"Failed to create template for scanner {scanner.tag} "
                    f"in app {application.id}: {exc}"
                )
        db.flush()


def _manifest_directory(builtin_dir: Optional[Path], language: Optional[str]) -> Path:
    if language is None:
        from config import settings

        language = settings.default_language
    root = builtin_dir or Path(__file__).resolve().parent.parent / "builtin_scanners"
    if not root.exists():
        raise FileNotFoundError(f"Built-in scanners directory not found: {root}")
    directory = root / language
    if not directory.exists():
        raise FileNotFoundError(
            f"Built-in scanners directory for language '{language}' not found: {directory}"
        )
    return directory


def load_builtin_scanner_packages(
    db: Session,
    builtin_dir: Optional[Path] = None,
    initialize_configs: bool = True,
    auto_commit: bool = True,
    language: Optional[str] = None,
) -> Dict[str, int]:
    directory = _manifest_directory(builtin_dir, language)
    manifests = sorted(directory.glob("*.json"))
    scanners = []
    for manifest_path in manifests:
        manifest = _read_manifest(manifest_path)
        package = _sync_package(db, manifest)
        scanners.extend(_sync_scanners(db, package, manifest["scanners"]))

    if initialize_configs and scanners:
        _seed_scanner_configs(db, scanners)
        _seed_response_templates(db, scanners)
    if auto_commit:
        db.commit()

    summary = {"packages": len(manifests), "scanners": len(scanners)}
    logger.info(
        "Built-in scanners loaded (packages=%d, scanners=%d)",
        summary["packages"],
        summary["scanners"],
    )
    return summary
