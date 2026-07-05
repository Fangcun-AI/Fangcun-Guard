from typing import Any, Dict, List, Optional  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

from database.models import PackagePurchase, Scanner, ScannerPackage, Tenant  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

from services.scanner_package_presenter import ScannerPackagePresenter  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


class ScannerPackageCatalog:  # fcg-rewrite
    """Read/query operations for scanner packages."""

    def __init__(self, db):  # fcg-rewrite
        self.db = db  # fcg-rewrite
        self.presenter = ScannerPackagePresenter()  # fcg-rewrite

    def get_all_packages(  # fcg-rewrite
        self,
        tenant_id: UUID,  # fcg-rewrite
        package_type: Optional[str] = None,  # fcg-rewrite
        include_scanners: bool = False,  # fcg-rewrite
    ) -> List[ScannerPackage]:  # fcg-rewrite
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()  # fcg-rewrite
        is_super_admin = tenant and hasattr(tenant, "is_super_admin") and tenant.is_super_admin  # fcg-rewrite

        query = self.db.query(ScannerPackage).filter(  # fcg-rewrite
            ScannerPackage.is_active == True,  # fcg-rewrite
            ScannerPackage.archived == False,  # fcg-rewrite
        )
        if package_type:  # fcg-rewrite
            query = query.filter(ScannerPackage.package_type == package_type)  # fcg-rewrite

        packages = query.order_by(  # fcg-rewrite
            ScannerPackage.display_order,  # fcg-rewrite
            ScannerPackage.package_name,  # fcg-rewrite
        ).all()

        visible_packages = []  # fcg-rewrite
        for package in packages:  # fcg-rewrite
            if package.package_type == "basic":  # fcg-rewrite
                visible_packages.append(package)  # fcg-rewrite
            elif package.package_type == "purchasable":  # fcg-rewrite
                if is_super_admin:  # fcg-rewrite
                    visible_packages.append(package)  # fcg-rewrite
                    logger.debug(f"Super admin granted access to premium package: {package.package_name}")  # fcg-rewrite
                else:
                    purchase = self.db.query(PackagePurchase).filter(  # fcg-rewrite
                        PackagePurchase.tenant_id == tenant_id,  # fcg-rewrite
                        PackagePurchase.package_id == package.id,  # fcg-rewrite
                        PackagePurchase.status == "approved",  # fcg-rewrite
                    ).first()  # fcg-rewrite
                    if purchase:  # fcg-rewrite
                        visible_packages.append(package)  # fcg-rewrite

        return visible_packages  # fcg-rewrite

    def get_purchasable_packages(self, tenant_id: UUID) -> List[Dict[str, Any]]:  # fcg-rewrite
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()  # fcg-rewrite
        is_super_admin = tenant and hasattr(tenant, "is_super_admin") and tenant.is_super_admin  # fcg-rewrite

        packages = self.db.query(ScannerPackage).filter(  # fcg-rewrite
            ScannerPackage.package_type == "purchasable",  # fcg-rewrite
            ScannerPackage.is_active == True,  # fcg-rewrite
            ScannerPackage.archived == False,  # fcg-rewrite
        ).order_by(  # fcg-rewrite
            ScannerPackage.bundle.asc().nullslast(),  # fcg-rewrite
            ScannerPackage.display_order,  # fcg-rewrite
            ScannerPackage.package_name,  # fcg-rewrite
        ).all()

        result = []  # fcg-rewrite
        for package in packages:  # fcg-rewrite
            if is_super_admin:  # fcg-rewrite
                result.append({  # fcg-rewrite
                    "id": str(package.id),  # fcg-rewrite
                    "package_code": package.package_code,  # fcg-rewrite
                    "package_name": package.package_name,  # fcg-rewrite
                    "author": package.author,  # fcg-rewrite
                    "description": package.description,  # fcg-rewrite
                    "version": package.version,  # fcg-rewrite
                    "package_type": package.package_type,  # fcg-rewrite
                    "scanner_count": package.scanner_count,  # fcg-rewrite
                    "price": package.price,  # fcg-rewrite
                    "price_display": package.price_display,  # fcg-rewrite
                    "bundle": package.bundle,  # fcg-rewrite
                    "purchase_status": "approved",  # fcg-rewrite
                    "purchased": True,  # fcg-rewrite
                    "purchase_requested": False,  # fcg-rewrite
                    "created_at": package.created_at.isoformat() if package.created_at else None,  # fcg-rewrite
                })
                continue  # fcg-rewrite

            purchase = self.db.query(PackagePurchase).filter(  # fcg-rewrite
                PackagePurchase.tenant_id == tenant_id,  # fcg-rewrite
                PackagePurchase.package_id == package.id,  # fcg-rewrite
            ).first()  # fcg-rewrite

            result.append({  # fcg-rewrite
                "id": str(package.id),  # fcg-rewrite
                "package_code": package.package_code,  # fcg-rewrite
                "package_name": package.package_name,  # fcg-rewrite
                "author": package.author,  # fcg-rewrite
                "description": package.description,  # fcg-rewrite
                "version": package.version,  # fcg-rewrite
                "package_type": package.package_type,  # fcg-rewrite
                "scanner_count": package.scanner_count,  # fcg-rewrite
                "price": package.price,  # fcg-rewrite
                "price_display": package.price_display,  # fcg-rewrite
                "bundle": package.bundle,  # fcg-rewrite
                "purchase_status": purchase.status if purchase else None,  # fcg-rewrite
                "purchased": bool(purchase and purchase.status == "approved"),  # fcg-rewrite
                "purchase_requested": bool(purchase is not None),  # fcg-rewrite
                "created_at": package.created_at.isoformat() if package.created_at else None,  # fcg-rewrite
            })

        return result  # fcg-rewrite

    def get_package_by_id(  # fcg-rewrite
        self,
        package_id: UUID,  # fcg-rewrite
        tenant_id: Optional[UUID] = None,  # fcg-rewrite
        check_access: bool = True,  # fcg-rewrite
    ) -> Optional[ScannerPackage]:  # fcg-rewrite
        package = self.db.query(ScannerPackage).filter(  # fcg-rewrite
            ScannerPackage.id == package_id,  # fcg-rewrite
            ScannerPackage.is_active == True,  # fcg-rewrite
            ScannerPackage.archived == False,  # fcg-rewrite
        ).first()  # fcg-rewrite
        if not package:  # fcg-rewrite
            return None  # fcg-rewrite

        if check_access and tenant_id and package.package_type == "purchasable":  # fcg-rewrite
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()  # fcg-rewrite
            is_super_admin = tenant and hasattr(tenant, "is_super_admin") and tenant.is_super_admin  # fcg-rewrite
            if is_super_admin:  # fcg-rewrite
                logger.debug(f"Super admin granted access to premium package: {package.package_name}")  # fcg-rewrite
                return package  # fcg-rewrite

            purchase = self.db.query(PackagePurchase).filter(  # fcg-rewrite
                PackagePurchase.tenant_id == tenant_id,  # fcg-rewrite
                PackagePurchase.package_id == package_id,  # fcg-rewrite
                PackagePurchase.status == "approved",  # fcg-rewrite
            ).first()  # fcg-rewrite
            if not purchase:  # fcg-rewrite
                return None  # fcg-rewrite

        return package  # fcg-rewrite

    def get_package_detail(  # fcg-rewrite
        self,
        package_id: UUID,  # fcg-rewrite
        tenant_id: UUID,  # fcg-rewrite
    ) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        package = self.get_package_by_id(package_id, tenant_id, check_access=True)  # fcg-rewrite
        if not package:  # fcg-rewrite
            return None  # fcg-rewrite

        scanners = self.db.query(Scanner).filter(  # fcg-rewrite
            Scanner.package_id == package_id,  # fcg-rewrite
            Scanner.is_active == True,  # fcg-rewrite
        ).order_by(Scanner.display_order, Scanner.tag).all()  # fcg-rewrite

        return self.presenter.build_package_detail(package, scanners, include_definitions=True)  # fcg-rewrite

    def get_marketplace_package_detail(  # fcg-rewrite
        self,
        package_id: UUID,  # fcg-rewrite
        tenant_id: UUID,  # fcg-rewrite
    ) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        package = self.db.query(ScannerPackage).filter(  # fcg-rewrite
            ScannerPackage.id == package_id,  # fcg-rewrite
            ScannerPackage.is_active == True,  # fcg-rewrite
            ScannerPackage.archived == False,  # fcg-rewrite
        ).first()  # fcg-rewrite
        if not package:  # fcg-rewrite
            return None  # fcg-rewrite

        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()  # fcg-rewrite
        is_super_admin = tenant and hasattr(tenant, "is_super_admin") and tenant.is_super_admin  # fcg-rewrite

        has_purchased = False  # fcg-rewrite
        if package.package_type == "purchasable":  # fcg-rewrite
            if is_super_admin:  # fcg-rewrite
                has_purchased = True  # fcg-rewrite
                logger.debug(f"Super admin granted full access to premium package: {package.package_name}")  # fcg-rewrite
            else:
                purchase = self.db.query(PackagePurchase).filter(  # fcg-rewrite
                    PackagePurchase.tenant_id == tenant_id,  # fcg-rewrite
                    PackagePurchase.package_id == package_id,  # fcg-rewrite
                    PackagePurchase.status == "approved",  # fcg-rewrite
                ).first()  # fcg-rewrite
                has_purchased = bool(purchase)  # fcg-rewrite

        scanners = self.db.query(Scanner).filter(  # fcg-rewrite
            Scanner.package_id == package_id,  # fcg-rewrite
            Scanner.is_active == True,  # fcg-rewrite
        ).order_by(Scanner.display_order, Scanner.tag).all()  # fcg-rewrite

        return self.presenter.build_package_detail(  # fcg-rewrite
            package,  # fcg-rewrite
            scanners,  # fcg-rewrite
            include_definitions=(package.package_type == "basic" or has_purchased),  # fcg-rewrite
            include_marketplace_fields=True,  # fcg-rewrite
        )
