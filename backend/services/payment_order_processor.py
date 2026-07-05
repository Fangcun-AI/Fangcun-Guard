from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from config import settings
from database.models import (
    PackagePurchase,
    PaymentOrder,
    SubscriptionPayment,
    TenantSubscription,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class PaymentOrderProcessor:
    """Applies paid order effects to subscriptions, packages, and purchased quota."""

    def __init__(self, billing_service):
        self.billing_service = billing_service

    def load_order(self, db: Session, order_id: str) -> Optional[PaymentOrder]:
        return db.query(PaymentOrder).filter(PaymentOrder.provider_order_id == order_id).first()

    def mark_order_paid(
        self,
        payment_order: PaymentOrder,
        transaction_id: str,
        paid_at: Optional[datetime] = None,
    ) -> None:
        payment_order.status = "paid"
        payment_order.provider_transaction_id = transaction_id
        payment_order.paid_at = paid_at or datetime.utcnow()

    def apply_subscription_payment(self, db: Session, payment_order: PaymentOrder) -> Dict[str, Any]:
        subscription = db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == payment_order.tenant_id
        ).first()

        if subscription:
            self._activate_subscription(db, payment_order, subscription)

        billing_start = datetime.utcnow()
        billing_end = billing_start + timedelta(days=30)
        sub_payment = SubscriptionPayment(
            tenant_id=payment_order.tenant_id,
            payment_order_id=payment_order.id,
            billing_cycle_start=billing_start,
            billing_cycle_end=billing_end,
            status="active",
            next_payment_date=billing_end,
            next_payment_amount=payment_order.amount,
        )
        db.add(sub_payment)
        db.commit()

        logger.info(f"Subscription activated for tenant: {payment_order.tenant_id}")
        return {
            "success": True,
            "tenant_id": str(payment_order.tenant_id),
            "subscription_type": "subscribed",
        }

    def apply_package_payment(self, db: Session, payment_order: PaymentOrder) -> Dict[str, Any]:
        existing_purchase = db.query(PackagePurchase).filter(
            and_(
                PackagePurchase.tenant_id == payment_order.tenant_id,
                PackagePurchase.package_id == payment_order.package_id,
            )
        ).first()

        if existing_purchase:
            existing_purchase.status = "approved"
            existing_purchase.approved_at = datetime.utcnow()
        else:
            purchase = PackagePurchase(
                tenant_id=payment_order.tenant_id,
                package_id=payment_order.package_id,
                status="approved",
                request_email=payment_order.order_metadata.get("email", "")
                if payment_order.order_metadata
                else "",
                approved_at=datetime.utcnow(),
            )
            db.add(purchase)

        db.commit()
        logger.info(
            "Package purchase completed for tenant: "
            f"{payment_order.tenant_id}, package: {payment_order.package_id}"
        )
        return {
            "success": True,
            "tenant_id": str(payment_order.tenant_id),
            "package_id": str(payment_order.package_id),
        }

    def apply_quota_purchase(self, db: Session, payment_order: PaymentOrder) -> Dict[str, Any]:
        units = payment_order.order_metadata.get("units", 1) if payment_order.order_metadata else 1
        self.billing_service.add_purchased_quota(str(payment_order.tenant_id), units, db)

        logger.info(f"Quota purchase completed for tenant: {payment_order.tenant_id}, units: {units}")
        return {
            "success": True,
            "tenant_id": str(payment_order.tenant_id),
            "units": units,
            "calls_added": units * settings.quota_calls_per_unit,
        }

    def _activate_subscription(
        self,
        db: Session,
        payment_order: PaymentOrder,
        subscription: TenantSubscription,
    ) -> None:
        now = datetime.utcnow()
        subscription.subscription_type = "subscribed"

        tier_number = None
        if payment_order.order_metadata and "tier_number" in payment_order.order_metadata:
            tier_number = payment_order.order_metadata["tier_number"]

        if tier_number is not None:
            tier_config = self.billing_service.get_tier_config(tier_number, db)
            if tier_config:
                subscription.monthly_quota = tier_config["monthly_quota"]
                subscription.subscription_tier = tier_number
            else:
                logger.error(f"Invalid tier_number {tier_number} for payment order {payment_order.provider_order_id}")
                self._apply_legacy_subscription_defaults(db, subscription)
        else:
            logger.info(
                "Payment order "
                f"{payment_order.provider_order_id} has no tier_number, treating as legacy subscription"
            )
            self._apply_legacy_subscription_defaults(db, subscription)

        subscription.subscription_started_at = now
        subscription.subscription_expires_at = now + timedelta(days=30)

    def _apply_legacy_subscription_defaults(
        self,
        db: Session,
        subscription: TenantSubscription,
    ) -> None:
        tier_config = self.billing_service.get_tier_config(0, db)
        if tier_config:
            subscription.monthly_quota = tier_config["monthly_quota"]
            subscription.subscription_tier = 0
            return

        subscription.monthly_quota = self.billing_service.SUBSCRIPTION_CONFIGS["subscribed"]["monthly_quota"]
        subscription.subscription_tier = 0
