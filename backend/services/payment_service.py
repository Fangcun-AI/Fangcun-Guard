"""Payment orchestration across provider adapters and local order persistence."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from config import settings
from database.models import PaymentOrder, ScannerPackage, SubscriptionPayment, TenantSubscription
from services.alipay_service import alipay_service
from services.billing_service import billing_service
from services.payment_order_processor import PaymentOrderProcessor
from services.payment_provider_profile import PaymentProviderProfile
from services.stripe_service import stripe_service
from utils.logger import get_logger

logger = get_logger(__name__)


class PaymentHub:
    def __init__(self):
        self.provider_profile = PaymentProviderProfile(billing_service)
        self.order_processor = PaymentOrderProcessor(billing_service)

    def get_payment_provider(self) -> str:
        return self.provider_profile.get_payment_provider()

    def get_currency(self) -> str:
        return self.provider_profile.get_currency()

    def get_subscription_price(self) -> float:
        return self.provider_profile.get_subscription_price()

    def get_tier_price(self, tier_number: int, db: Session) -> float:
        return self.provider_profile.get_tier_price(tier_number, db)

    @staticmethod
    def _persist(db: Session, order: PaymentOrder) -> PaymentOrder:
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def _result(order: PaymentOrder, **provider_fields) -> Dict[str, Any]:
        return {
            "success": True,
            "payment_id": str(order.id),
            "order_id": order.provider_order_id,
            "provider": order.payment_provider,
            "amount": order.amount,
            "currency": order.currency,
        } | provider_fields

    @staticmethod
    def _mark_failed(db: Session, order: PaymentOrder, error: Exception) -> None:
        order.status = "failed"
        db.commit()
        logger.error("Unable to create payment %s: %s", order.provider_order_id, error)

    async def _stripe_customer(self, db: Session, tenant_id: str, email: str) -> str:
        subscription = db.query(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_id).first()
        customer_id = getattr(subscription, "stripe_customer_id", None)
        if customer_id and not await stripe_service.customer_exists(customer_id):
            customer_id = None
        if not customer_id:
            customer_id = await stripe_service.create_customer(email=email, tenant_id=tenant_id)
            if subscription:
                subscription.stripe_customer_id = customer_id
                db.commit()
        return customer_id

    @staticmethod
    def _remember_session(db: Session, order: PaymentOrder, session_id: str) -> None:
        order.order_metadata = {**(order.order_metadata or {}), "stripe_session_id": session_id}
        db.commit()

    async def create_subscription_payment(
        self, db: Session, tenant_id: str, email: str, tier_number: Optional[int] = None
    ) -> Dict[str, Any]:
        provider, currency = self.get_payment_provider(), self.get_currency()
        tier = billing_service.get_tier_config(tier_number, db) if tier_number is not None else None
        if tier_number is not None and not tier:
            raise ValueError(f"Invalid tier number: {tier_number}")
        amount = tier["price_cny" if provider == "alipay" else "price_usd"] if tier else self.get_subscription_price()
        metadata = {"email": email}
        if tier:
            metadata.update(tier_number=tier_number, tier_name=tier["tier_name"])
        order = self._persist(db, PaymentOrder(
            tenant_id=tenant_id, order_type="subscription", amount=amount, currency=currency,
            payment_provider=provider, status="pending", provider_order_id=f"sub_{uuid.uuid4().hex[:16]}",
            order_metadata=metadata,
        ))
        try:
            if provider == "alipay":
                checkout = await alipay_service.create_subscription_order(order.provider_order_id, amount)
                return self._result(order, payment_url=checkout["payment_url"])
            customer = await self._stripe_customer(db, tenant_id, email)
            urls = self.provider_profile.build_subscription_urls()
            checkout = await stripe_service.create_subscription_checkout(
                customer, urls["success_url"], urls["cancel_url"], tenant_id,
                price_id=tier.get("stripe_price_id") if tier else None, tier_number=tier_number,
            )
            self._remember_session(db, order, checkout["session_id"])
            return self._result(order, checkout_url=checkout["checkout_url"], session_id=checkout["session_id"])
        except Exception as error:
            self._mark_failed(db, order, error)
            raise

    async def create_package_payment(
        self, db: Session, tenant_id: str, email: str, package_id: str
    ) -> Dict[str, Any]:
        package = db.query(ScannerPackage).filter(ScannerPackage.id == package_id).first()
        if not package:
            raise ValueError("Package not found")
        if not package.price:
            raise ValueError("Package price not set")
        provider, currency = self.get_payment_provider(), self.get_currency()
        order = self._persist(db, PaymentOrder(
            tenant_id=tenant_id, order_type="package", amount=package.price, currency=currency,
            payment_provider=provider, status="pending", provider_order_id=f"pkg_{uuid.uuid4().hex[:16]}",
            package_id=package_id, order_metadata={"email": email, "package_name": package.package_name},
        ))
        try:
            if provider == "alipay":
                checkout = await alipay_service.create_package_order(order.provider_order_id, package.price, package.package_name)
                return self._result(order, payment_url=checkout["payment_url"], package_name=package.package_name)
            customer = await self._stripe_customer(db, tenant_id, email)
            urls = self.provider_profile.build_package_urls()
            checkout = await stripe_service.create_package_checkout(
                customer, int(package.price * 100), package_id, package.package_name,
                urls["success_url"], urls["cancel_url"], tenant_id,
            )
            self._remember_session(db, order, checkout["session_id"])
            return self._result(
                order, checkout_url=checkout["checkout_url"], session_id=checkout["session_id"],
                package_name=package.package_name,
            )
        except Exception as error:
            self._mark_failed(db, order, error)
            raise

    async def create_quota_purchase_payment(
        self, db: Session, tenant_id: str, email: str, units: int
    ) -> Dict[str, Any]:
        if units < 1:
            raise ValueError("Minimum purchase is 1 unit")
        calls = units * settings.quota_calls_per_unit
        order = self._persist(db, PaymentOrder(
            tenant_id=tenant_id, order_type="quota_purchase", amount=units * settings.quota_price_cny,
            currency="CNY", payment_provider="alipay", status="pending",
            provider_order_id=f"quota_{uuid.uuid4().hex[:16]}",
            order_metadata={
                "email": email, "units": units, "calls": calls,
                "price_per_unit": settings.quota_price_cny, "validity_days": settings.quota_validity_days,
            },
        ))
        try:
            checkout = await alipay_service.create_subscription_order(
                order.provider_order_id, order.amount,
                subject=f"象信AI安全护栏额度充值 - {calls}次调用",
                body=f"购买API调用额度 {calls} 次，有效期{settings.quota_validity_days}天",
            )
            return self._result(order, payment_url=checkout["payment_url"])
        except Exception as error:
            self._mark_failed(db, order, error)
            raise

    def _settle(self, db: Session, order_id: str, transaction_id: str, paid_at, apply):
        order = self.order_processor.load_order(db, order_id)
        if not order:
            return {"success": False, "error": "Order not found"}
        if order.status == "paid":
            return {"success": True, "message": "Already processed"}
        self.order_processor.mark_order_paid(order, transaction_id, paid_at)
        return apply(db, order)

    async def handle_subscription_paid(self, db: Session, order_id: str, transaction_id: str, paid_at: Optional[datetime] = None):
        return self._settle(db, order_id, transaction_id, paid_at, self.order_processor.apply_subscription_payment)

    async def handle_package_paid(self, db: Session, order_id: str, transaction_id: str, paid_at: Optional[datetime] = None):
        return self._settle(db, order_id, transaction_id, paid_at, self.order_processor.apply_package_payment)

    async def handle_quota_purchase_paid(self, db: Session, order_id: str, transaction_id: str, paid_at: Optional[datetime] = None):
        return self._settle(db, order_id, transaction_id, paid_at, self.order_processor.apply_quota_purchase)

    async def cancel_subscription(self, db: Session, tenant_id: str) -> Dict[str, Any]:
        payment = db.query(SubscriptionPayment).filter(and_(
            SubscriptionPayment.tenant_id == tenant_id, SubscriptionPayment.status == "active"
        )).first()
        if not payment:
            return {"success": False, "error": "No active subscription found"}
        if self.get_payment_provider() == "stripe" and payment.stripe_subscription_id:
            await stripe_service.cancel_subscription(payment.stripe_subscription_id)
        payment.cancel_at_period_end = True
        db.commit()
        return {"success": True, "cancel_at": payment.billing_cycle_end.isoformat() if payment.billing_cycle_end else None}

    def get_payment_orders(
        self, db: Session, tenant_id: str, order_type: Optional[str] = None,
        status: Optional[str] = None, limit: int = 50,
    ) -> list:
        query = db.query(PaymentOrder).filter(PaymentOrder.tenant_id == tenant_id)
        if order_type:
            query = query.filter(PaymentOrder.order_type == order_type)
        if status:
            query = query.filter(PaymentOrder.status == status)
        return [{
            "id": str(order.id), "order_type": order.order_type, "amount": order.amount,
            "currency": order.currency, "payment_provider": order.payment_provider, "status": order.status,
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "package_id": str(order.package_id) if order.package_id else None,
        } for order in query.order_by(PaymentOrder.created_at.desc()).limit(limit).all()]

    def get_payment_config(self, db: Session = None) -> Dict[str, Any]:
        try:
            key = stripe_service.get_publishable_key() if self.get_payment_provider() == "stripe" else None
            return self.provider_profile.build_frontend_config(db, key)
        except Exception as error:
            logger.warning("Unable to build payment config: %s", error)
            return self.provider_profile.build_frontend_config(None)


payment_service = PaymentHub()
