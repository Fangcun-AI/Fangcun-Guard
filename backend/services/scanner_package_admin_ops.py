from typing import Any, Dict, List, Optional  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

from sqlalchemy import func  # fcg-rewrite

from database.models import PackagePurchase, Scanner, ScannerPackage  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

from services.scanner_package_presenter import ScannerPackagePresenter  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


class ScannerPackageAdminOps:  # fcg-rewrite
    """Admin/package management operations for scanner packages."""

    def __init__(self, db):  # fcg-rewrite
        self.db = db  # fcg-rewrite
        self.presenter = ScannerPackagePresenter()  # fcg-rewrite

    def create_purchasable_package(  # fcg-rewrite
        self,
        package_data: Dict[str, Any],  # fcg-rewrite
        created_by: UUID,  # fcg-rewrite
    ) -> ScannerPackage:  # fcg-rewrite
        package_code = package_data["package_code"]  # fcg-rewrite
        package_version = package_data.get("version", "1.0.0")  # fcg-rewrite

        exact_duplicate = self.db.query(ScannerPackage).filter(  # fcg-rewrite
            ScannerPackage.package_code == package_code,  # fcg-rewrite
            ScannerPackage.version == package_version,  # fcg-rewrite
            ScannerPackage.is_active == True,  # fcg-rewrite
            ScannerPackage.archived == False,  # fcg-rewrite
        ).first()  # fcg-rewrite
        if exact_duplicate:  # fcg-rewrite
            raise ValueError(  # fcg-rewrite
                f"Package with code '{package_code}' and version '{package_version}' already exists. "  # fcg-rewrite
                f"Use a different version number."  # fcg-rewrite
            )

        active_packages = self.db.query(ScannerPackage).filter(  # fcg-rewrite
            ScannerPackage.package_code == package_code,  # fcg-rewrite
            ScannerPackage.is_active == True,  # fcg-rewrite
            ScannerPackage.archived == False,  # fcg-rewrite
        ).all()
        if active_packages:  # fcg-rewrite
            package_names = [f"{package.package_name} (v{package.version})" for package in active_packages]  # fcg-rewrite
            raise ValueError(  # fcg-rewrite
                f"Cannot create new version of '{package_code}' because the following "  # fcg-rewrite
                f"packages are still active: {', '.join(package_names)}. "  # fcg-rewrite
                f"Please archive the old version(s) first before uploading a new version."  # fcg-rewrite
            )

        package = ScannerPackage(  # fcg-rewrite
            package_code=package_code,  # fcg-rewrite
            package_name=package_data["package_name"],  # fcg-rewrite
            author=package_data.get("author", "FangcunGuard"),  # fcg-rewrite
            description=package_data.get("description"),  # fcg-rewrite
            version=package_version,  # fcg-rewrite
            license=package_data.get("license", "proprietary"),  # fcg-rewrite
            package_type="purchasable",  # fcg-rewrite
            is_official=True,  # fcg-rewrite
            requires_purchase=True,  # fcg-rewrite
            price=package_data.get("price"),  # fcg-rewrite
            price_display=package_data.get("price_display"),  # fcg-rewrite
            bundle=package_data.get("bundle"),  # fcg-rewrite
            scanner_count=len(package_data.get("scanners", [])),  # fcg-rewrite
        )
        self.db.add(package)  # fcg-rewrite
        self.db.flush()  # fcg-rewrite

        for index, scanner_data in enumerate(package_data.get("scanners", [])):  # fcg-rewrite
            existing_scanner = self.db.query(Scanner).filter(  # fcg-rewrite
                Scanner.tag == scanner_data["tag"]  # fcg-rewrite
            ).first()  # fcg-rewrite

            normalized_risk = self.presenter.normalize_risk_level(scanner_data["risk_level"])  # fcg-rewrite
            if existing_scanner:  # fcg-rewrite
                existing_scanner.package_id = package.id  # fcg-rewrite
                existing_scanner.name = scanner_data["name"]  # fcg-rewrite
                existing_scanner.description = scanner_data.get("description", scanner_data["definition"])  # fcg-rewrite
                existing_scanner.scanner_type = scanner_data["type"]  # fcg-rewrite
                existing_scanner.definition = scanner_data["definition"]  # fcg-rewrite
                existing_scanner.default_risk_level = normalized_risk  # fcg-rewrite
                existing_scanner.default_scan_prompt = scanner_data.get("scan_prompt", True)  # fcg-rewrite
                existing_scanner.default_scan_response = scanner_data.get("scan_response", True)  # fcg-rewrite
                existing_scanner.display_order = index  # fcg-rewrite
                existing_scanner.is_active = True  # fcg-rewrite
                logger.info(f"Reused existing scanner tag {scanner_data['tag']} for new package version")  # fcg-rewrite
            else:
                scanner = Scanner(  # fcg-rewrite
                    package_id=package.id,  # fcg-rewrite
                    tag=scanner_data["tag"],  # fcg-rewrite
                    name=scanner_data["name"],  # fcg-rewrite
                    description=scanner_data.get("description", scanner_data["definition"]),  # fcg-rewrite
                    scanner_type=scanner_data["type"],  # fcg-rewrite
                    definition=scanner_data["definition"],  # fcg-rewrite
                    default_risk_level=normalized_risk,  # fcg-rewrite
                    default_scan_prompt=scanner_data.get("scan_prompt", True),  # fcg-rewrite
                    default_scan_response=scanner_data.get("scan_response", True),  # fcg-rewrite
                    display_order=index,  # fcg-rewrite
                )
                self.db.add(scanner)  # fcg-rewrite
                logger.info(f"Created new scanner with tag {scanner_data['tag']}")  # fcg-rewrite

        self.db.commit()  # fcg-rewrite
        self.db.refresh(package)  # fcg-rewrite
        logger.info(  # fcg-rewrite
            f"Created purchasable package: {package.package_name} v{package.version} "  # fcg-rewrite
            f"({package.scanner_count} scanners) by {created_by}"  # fcg-rewrite
        )
        return package  # fcg-rewrite

    def update_package(self, package_id: UUID, updates: Dict[str, Any]) -> Optional[ScannerPackage]:  # fcg-rewrite
        package = self.db.query(ScannerPackage).filter(ScannerPackage.id == package_id).first()  # fcg-rewrite
        if not package:  # fcg-rewrite
            return None  # fcg-rewrite

        allowed_fields = [  # fcg-rewrite
            "package_name", "description", "version", "price", "price_display",  # fcg-rewrite
            "bundle", "is_active", "display_order",  # fcg-rewrite
        ]
        for field in allowed_fields:  # fcg-rewrite
            if field in updates:  # fcg-rewrite
                setattr(package, field, updates[field])  # fcg-rewrite

        self.db.commit()  # fcg-rewrite
        self.db.refresh(package)  # fcg-rewrite
        logger.info(f"Updated package: {package.package_name} (ID: {package_id})")  # fcg-rewrite
        return package  # fcg-rewrite

    def archive_package(self, package_id: UUID, archived_by: UUID, reason: Optional[str] = None) -> bool:  # fcg-rewrite
        package = self.db.query(ScannerPackage).filter(ScannerPackage.id == package_id).first()  # fcg-rewrite
        if not package:  # fcg-rewrite
            return False  # fcg-rewrite
        if package.archived:  # fcg-rewrite
            logger.warning(f"Package {package.package_name} (ID: {package_id}) is already archived")  # fcg-rewrite
            return True  # fcg-rewrite

        package_name = package.package_name  # fcg-rewrite
        package.archived = True  # fcg-rewrite
        package.archived_at = func.now()  # fcg-rewrite
        package.archived_by = archived_by  # fcg-rewrite
        package.archive_reason = reason  # fcg-rewrite
        self.db.commit()  # fcg-rewrite

        logger.warning(  # fcg-rewrite
            f"Archived package: {package_name} (ID: {package_id}) "  # fcg-rewrite
            f"by admin {archived_by}. Reason: {reason or 'Not specified'}"  # fcg-rewrite
        )
        return True  # fcg-rewrite

    def unarchive_package(self, package_id: UUID, unarchived_by: UUID) -> bool:  # fcg-rewrite
        package = self.db.query(ScannerPackage).filter(  # fcg-rewrite
            ScannerPackage.id == package_id,  # fcg-rewrite
            ScannerPackage.archived == True,  # fcg-rewrite
        ).first()  # fcg-rewrite
        if not package:  # fcg-rewrite
            return False  # fcg-rewrite

        package_name = package.package_name  # fcg-rewrite
        package.archived = False  # fcg-rewrite
        package.archived_at = None  # fcg-rewrite
        package.archived_by = None  # fcg-rewrite
        package.archive_reason = None  # fcg-rewrite
        self.db.commit()  # fcg-rewrite

        logger.info(f"Unarchived package: {package_name} (ID: {package_id}) by admin {unarchived_by}")  # fcg-rewrite
        return True  # fcg-rewrite

    def get_all_packages_admin(  # fcg-rewrite
        self,
        package_type: Optional[str] = None,  # fcg-rewrite
        include_archived: bool = False,  # fcg-rewrite
    ) -> List[ScannerPackage]:  # fcg-rewrite
        query = self.db.query(ScannerPackage).filter(ScannerPackage.is_active == True)  # fcg-rewrite
        if package_type:  # fcg-rewrite
            query = query.filter(ScannerPackage.package_type == package_type)  # fcg-rewrite
        if not include_archived:  # fcg-rewrite
            query = query.filter(ScannerPackage.archived == False)  # fcg-rewrite
        return query.order_by(  # fcg-rewrite
            ScannerPackage.package_code,  # fcg-rewrite
            ScannerPackage.version.desc(),  # fcg-rewrite
        ).all()

    def get_package_statistics(self, package_id: UUID) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        package = self.db.query(ScannerPackage).filter(ScannerPackage.id == package_id).first()  # fcg-rewrite
        if not package:  # fcg-rewrite
            return None  # fcg-rewrite

        total_purchases = self.db.query(PackagePurchase).filter(  # fcg-rewrite
            PackagePurchase.package_id == package_id  # fcg-rewrite
        ).count()  # fcg-rewrite
        approved_purchases = self.db.query(PackagePurchase).filter(  # fcg-rewrite
            PackagePurchase.package_id == package_id,  # fcg-rewrite
            PackagePurchase.status == "approved",  # fcg-rewrite
        ).count()  # fcg-rewrite
        pending_purchases = self.db.query(PackagePurchase).filter(  # fcg-rewrite
            PackagePurchase.package_id == package_id,  # fcg-rewrite
            PackagePurchase.status == "pending",  # fcg-rewrite
        ).count()  # fcg-rewrite

        return {  # fcg-rewrite
            "package_id": str(package_id),  # fcg-rewrite
            "package_name": package.package_name,  # fcg-rewrite
            "total_purchases": total_purchases,  # fcg-rewrite
            "approved_purchases": approved_purchases,  # fcg-rewrite
            "pending_purchases": pending_purchases,  # fcg-rewrite
            "scanner_count": package.scanner_count,  # fcg-rewrite
        }
