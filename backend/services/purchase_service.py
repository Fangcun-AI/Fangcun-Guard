"""Scanner-package purchase requests, approvals, and free-package activation."""

from datetime import datetime  # fcg-rewrite
from typing import Any, Dict, List, Optional  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import (  # fcg-rewrite
    Application,  # fcg-rewrite
    PackagePurchase,  # fcg-rewrite
    ScannerPackage,  # fcg-rewrite
    Tenant,
    TenantSubscription,  # fcg-rewrite
)
from services.response_template_service import ResponseTemplateService  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


class PurchaseService:  # fcg-rewrite
    def __init__(self, db: Session):  # fcg-rewrite
        self.db = db  # fcg-rewrite

    def request_purchase(  # fcg-rewrite
        self,
        tenant_id: UUID,  # fcg-rewrite
        package_id: UUID,  # fcg-rewrite
        email: str,  # fcg-rewrite
        message: Optional[str] = None,  # fcg-rewrite
    ) -> PackagePurchase:  # fcg-rewrite
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()  # fcg-rewrite
        if tenant and getattr(tenant, "is_super_admin", False):  # fcg-rewrite
            raise ValueError("Super admins have automatic access to all packages and do not need to purchase them.")  # fcg-rewrite
        package = self._package(package_id)  # fcg-rewrite
        if not package.requires_purchase:  # fcg-rewrite
            raise ValueError("Package does not require purchase (it's free)")  # fcg-rewrite

        purchase = self._purchase(tenant_id, package_id)  # fcg-rewrite
        if purchase:  # fcg-rewrite
            if purchase.status == "approved":  # fcg-rewrite
                raise ValueError("Package already purchased")  # fcg-rewrite
            if purchase.status == "pending":  # fcg-rewrite
                raise ValueError("Purchase request already pending")  # fcg-rewrite
            purchase.status = "pending"  # fcg-rewrite
            purchase.request_email = email  # fcg-rewrite
            purchase.request_message = message  # fcg-rewrite
            purchase.rejection_reason = None  # fcg-rewrite
            return self._save(purchase)  # fcg-rewrite

        plan = self.db.query(TenantSubscription).filter(  # fcg-rewrite
            TenantSubscription.tenant_id == tenant_id  # fcg-rewrite
        ).first()  # fcg-rewrite
        if not plan or plan.subscription_type != "subscribed":  # fcg-rewrite
            raise ValueError(  # fcg-rewrite
                "Only subscribed users can purchase packages. "  # fcg-rewrite
                "Please upgrade to subscribed plan first."  # fcg-rewrite
            )
        return self._save(  # fcg-rewrite
            PackagePurchase(  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                package_id=package_id,  # fcg-rewrite
                status="pending",  # fcg-rewrite
                request_email=email,  # fcg-rewrite
                request_message=message,  # fcg-rewrite
            ),
            add=True,  # fcg-rewrite
        )

    def get_user_purchases(  # fcg-rewrite
        self, tenant_id: UUID, status: Optional[str] = None  # fcg-rewrite
    ) -> List[Dict[str, Any]]:  # fcg-rewrite
        query = self.db.query(PackagePurchase).filter(  # fcg-rewrite
            PackagePurchase.tenant_id == tenant_id  # fcg-rewrite
        )
        if status:  # fcg-rewrite
            query = query.filter(PackagePurchase.status == status)  # fcg-rewrite
        return [  # fcg-rewrite
            self._serialize(purchase)  # fcg-rewrite
            for purchase in query.order_by(PackagePurchase.created_at.desc()).all()  # fcg-rewrite
        ]

    def get_pending_purchases(self) -> List[Dict[str, Any]]:  # fcg-rewrite
        purchases = self.db.query(PackagePurchase).filter(  # fcg-rewrite
            PackagePurchase.status == "pending"  # fcg-rewrite
        ).order_by(PackagePurchase.created_at.asc()).all()  # fcg-rewrite
        return [self._serialize(purchase, include_tenant=True) for purchase in purchases]  # fcg-rewrite

    def approve_purchase(  # fcg-rewrite
        self, purchase_id: UUID, approved_by: UUID  # fcg-rewrite
    ) -> Optional[PackagePurchase]:  # fcg-rewrite
        purchase = self._purchase_by_id(purchase_id)  # fcg-rewrite
        if not purchase:  # fcg-rewrite
            return None  # fcg-rewrite
        self._require_pending(purchase)  # fcg-rewrite
        purchase.status = "approved"  # fcg-rewrite
        purchase.approved_by = approved_by  # fcg-rewrite
        purchase.approved_at = datetime.utcnow()  # fcg-rewrite
        purchase.rejection_reason = None  # fcg-rewrite
        self._save(purchase)  # fcg-rewrite
        self._try_create_templates(purchase)  # fcg-rewrite
        return purchase  # fcg-rewrite

    def reject_purchase(  # fcg-rewrite
        self,
        purchase_id: UUID,  # fcg-rewrite
        rejection_reason: str,  # fcg-rewrite
        rejected_by: UUID,  # fcg-rewrite
    ) -> Optional[PackagePurchase]:  # fcg-rewrite
        purchase = self._purchase_by_id(purchase_id)  # fcg-rewrite
        if not purchase:  # fcg-rewrite
            return None  # fcg-rewrite
        self._require_pending(purchase)  # fcg-rewrite
        purchase.status = "rejected"  # fcg-rewrite
        purchase.rejection_reason = rejection_reason  # fcg-rewrite
        purchase.approved_by = rejected_by  # fcg-rewrite
        purchase.approved_at = datetime.utcnow()  # fcg-rewrite
        return self._save(purchase)  # fcg-rewrite

    def cancel_purchase_request(self, purchase_id: UUID, tenant_id: UUID) -> bool:  # fcg-rewrite
        purchase = self.db.query(PackagePurchase).filter(  # fcg-rewrite
            PackagePurchase.id == purchase_id,  # fcg-rewrite
            PackagePurchase.tenant_id == tenant_id,  # fcg-rewrite
            PackagePurchase.status == "pending",  # fcg-rewrite
        ).first()  # fcg-rewrite
        if not purchase:  # fcg-rewrite
            return False  # fcg-rewrite
        self.db.delete(purchase)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        return True  # fcg-rewrite

    def direct_purchase_free_package(  # fcg-rewrite
        self, tenant_id: UUID, package_id: UUID, email: str  # fcg-rewrite
    ) -> PackagePurchase:  # fcg-rewrite
        package = self._package(package_id)  # fcg-rewrite
        if package.price and package.price > 0:  # fcg-rewrite
            raise ValueError("Package is not free. Please use payment flow.")  # fcg-rewrite
        purchase = self._purchase(tenant_id, package_id)  # fcg-rewrite
        is_new = purchase is None  # fcg-rewrite
        if purchase and purchase.status == "approved":  # fcg-rewrite
            raise ValueError("Package already purchased")  # fcg-rewrite
        if purchase:  # fcg-rewrite
            purchase.status = "approved"  # fcg-rewrite
            purchase.request_email = email  # fcg-rewrite
            purchase.approved_at = datetime.utcnow()  # fcg-rewrite
        else:
            purchase = PackagePurchase(  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                package_id=package_id,  # fcg-rewrite
                status="approved",  # fcg-rewrite
                request_email=email,  # fcg-rewrite
                approved_at=datetime.utcnow(),  # fcg-rewrite
            )
        self._save(purchase, add=is_new)  # fcg-rewrite
        self._try_create_templates(purchase)  # fcg-rewrite
        return purchase  # fcg-rewrite

    def get_purchase_statistics(  # fcg-rewrite
        self, package_id: Optional[UUID] = None  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        query = self.db.query(PackagePurchase)  # fcg-rewrite
        if package_id:  # fcg-rewrite
            query = query.filter(PackagePurchase.package_id == package_id)  # fcg-rewrite
        purchases = query.all()  # fcg-rewrite
        counts = {  # fcg-rewrite
            status: sum(purchase.status == status for purchase in purchases)  # fcg-rewrite
            for status in ("pending", "approved", "rejected")  # fcg-rewrite
        }
        stats = {  # fcg-rewrite
            "total_requests": len(purchases),  # fcg-rewrite
            **counts,  # fcg-rewrite
            "approval_rate": round(counts["approved"] / len(purchases) * 100, 2)  # fcg-rewrite
            if purchases  # fcg-rewrite
            else 0,
        }
        if package_id:  # fcg-rewrite
            package = self.db.query(ScannerPackage).filter(  # fcg-rewrite
                ScannerPackage.id == package_id  # fcg-rewrite
            ).first()  # fcg-rewrite
            if package:  # fcg-rewrite
                stats.update(  # fcg-rewrite
                    package_name=package.package_name,  # fcg-rewrite
                    package_code=package.package_code,  # fcg-rewrite
                )
        return stats  # fcg-rewrite

    def _package(self, package_id: UUID) -> ScannerPackage:  # fcg-rewrite
        package = self.db.query(ScannerPackage).filter(  # fcg-rewrite
            ScannerPackage.id == package_id,  # fcg-rewrite
            ScannerPackage.is_active == True,  # fcg-rewrite
        ).first()  # fcg-rewrite
        if not package:  # fcg-rewrite
            raise ValueError("Package not found")  # fcg-rewrite
        return package  # fcg-rewrite

    def _purchase(self, tenant_id: UUID, package_id: UUID):  # fcg-rewrite
        return self.db.query(PackagePurchase).filter(  # fcg-rewrite
            PackagePurchase.tenant_id == tenant_id,  # fcg-rewrite
            PackagePurchase.package_id == package_id,  # fcg-rewrite
        ).first()  # fcg-rewrite

    def _purchase_by_id(self, purchase_id: UUID):  # fcg-rewrite
        return self.db.query(PackagePurchase).filter(  # fcg-rewrite
            PackagePurchase.id == purchase_id  # fcg-rewrite
        ).first()  # fcg-rewrite

    def _save(self, purchase: PackagePurchase, *, add: bool = False):  # fcg-rewrite
        if add:
            self.db.add(purchase)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        self.db.refresh(purchase)  # fcg-rewrite
        return purchase  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _require_pending(purchase: PackagePurchase):  # fcg-rewrite
        if purchase.status != "pending":  # fcg-rewrite
            raise ValueError(f"Purchase is not pending (status: {purchase.status})")  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _serialize(purchase: PackagePurchase, *, include_tenant: bool = False) -> dict:  # fcg-rewrite
        package = purchase.package  # fcg-rewrite
        result = {  # fcg-rewrite
            "id": str(purchase.id),  # fcg-rewrite
            "package_id": str(purchase.package_id),  # fcg-rewrite
            "package_name": package.package_name if package else None,  # fcg-rewrite
            "package_code": package.package_code if package else None,  # fcg-rewrite
            "status": purchase.status,  # fcg-rewrite
            "request_email": purchase.request_email,  # fcg-rewrite
            "request_message": purchase.request_message,  # fcg-rewrite
            "rejection_reason": purchase.rejection_reason,  # fcg-rewrite
            "approved_at": purchase.approved_at.isoformat() if purchase.approved_at else None,  # fcg-rewrite
            "created_at": purchase.created_at.isoformat() if purchase.created_at else None,  # fcg-rewrite
        }
        if include_tenant:  # fcg-rewrite
            result.update(  # fcg-rewrite
                tenant_id=str(purchase.tenant_id),  # fcg-rewrite
                tenant_email=purchase.tenant.email if purchase.tenant else None,  # fcg-rewrite
            )
            result.pop("status")  # fcg-rewrite
            result.pop("rejection_reason")  # fcg-rewrite
            result.pop("approved_at")  # fcg-rewrite
        return result  # fcg-rewrite

    def _try_create_templates(self, purchase: PackagePurchase):  # fcg-rewrite
        try:
            self._create_templates_for_purchased_scanners(purchase, purchase.tenant_id)  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to create response templates for purchase {purchase.id}: {exc}")  # fcg-rewrite

    def _create_templates_for_purchased_scanners(  # fcg-rewrite
        self, purchase: PackagePurchase, tenant_id: UUID  # fcg-rewrite
    ):
        applications = self.db.query(Application).filter(  # fcg-rewrite
            Application.tenant_id == tenant_id,  # fcg-rewrite
            Application.is_active == True,  # fcg-rewrite
        ).all()
        scanners = purchase.package.scanners if purchase.package else []  # fcg-rewrite
        if not applications or not scanners:  # fcg-rewrite
            return
        templates = ResponseTemplateService(self.db)  # fcg-rewrite
        for application in applications:  # fcg-rewrite
            for scanner in scanners:  # fcg-rewrite
                if scanner.is_active:  # fcg-rewrite
                    try:
                        templates.create_template_for_marketplace_scanner(  # fcg-rewrite
                            scanner=scanner,  # fcg-rewrite
                            application_id=application.id,  # fcg-rewrite
                            tenant_id=tenant_id,  # fcg-rewrite
                        )
                    except Exception as exc:  # fcg-rewrite
                        logger.error(f"Failed to create scanner template {scanner.tag}: {exc}")  # fcg-rewrite
