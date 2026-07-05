"""Stripe adapter used by the payment orchestration layer."""

from datetime import datetime  # fcg-rewrite
from typing import Any, Dict, Optional  # fcg-rewrite
from urllib.parse import quote  # fcg-rewrite

import stripe  # fcg-rewrite
from stripe import _error as stripe_error  # fcg-rewrite

from config import settings  # fcg-rewrite
from utils.logger import get_logger  # fcg-rewrite

logger = get_logger(__name__)  # fcg-rewrite
_URL_SAFE = ":/?#[]@!$&'()*+,;="  # fcg-rewrite


class StripeService:  # fcg-rewrite
    def __init__(self):  # fcg-rewrite
        self.secret_key = settings.stripe_secret_key  # fcg-rewrite
        self.publishable_key = settings.stripe_publishable_key  # fcg-rewrite
        self.webhook_secret = settings.stripe_webhook_secret  # fcg-rewrite
        self.price_id_monthly = settings.stripe_price_id_monthly  # fcg-rewrite
        if self.secret_key:  # fcg-rewrite
            stripe.api_key = self.secret_key  # fcg-rewrite

    def _require_key(self) -> None:  # fcg-rewrite
        if not self.secret_key:  # fcg-rewrite
            raise ValueError("Stripe is not configured")  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _url(value: str) -> str:  # fcg-rewrite
        value = value.strip("'\"")  # fcg-rewrite
        try:
            value.encode("ascii")  # fcg-rewrite
            return value  # fcg-rewrite
        except UnicodeEncodeError:  # fcg-rewrite
            return quote(value, safe=_URL_SAFE)  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _checkout_result(session, customer_id: str) -> Dict[str, Any]:  # fcg-rewrite
        return {"session_id": session.id, "checkout_url": session.url, "customer_id": customer_id}  # fcg-rewrite

    async def customer_exists(self, customer_id: str) -> bool:  # fcg-rewrite
        if not self.secret_key:  # fcg-rewrite
            return False  # fcg-rewrite
        try:
            stripe.Customer.retrieve(customer_id)  # fcg-rewrite
            return True  # fcg-rewrite
        except stripe_error.InvalidRequestError as error:  # fcg-rewrite
            if "No such customer" not in str(error):  # fcg-rewrite
                raise
            logger.warning("Stripe customer does not exist: %s", customer_id)  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Stripe customer lookup failed: %s", error)  # fcg-rewrite
        return False  # fcg-rewrite

    async def create_customer(self, email: str, tenant_id: str, name: Optional[str] = None) -> str:  # fcg-rewrite
        self._require_key()  # fcg-rewrite
        customer = stripe.Customer.create(email=email, name=name, metadata={"tenant_id": str(tenant_id)})  # fcg-rewrite
        logger.info("Created Stripe customer %s for tenant %s", customer.id, tenant_id)  # fcg-rewrite
        return customer.id  # fcg-rewrite

    async def create_subscription_checkout(  # fcg-rewrite
        self,
        customer_id: str,  # fcg-rewrite
        success_url: str,  # fcg-rewrite
        cancel_url: str,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        price_id: Optional[str] = None,  # fcg-rewrite
        tier_number: Optional[int] = None,  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        self._require_key()  # fcg-rewrite
        selected_price = price_id or self.price_id_monthly  # fcg-rewrite
        if not selected_price:  # fcg-rewrite
            raise ValueError("Stripe price ID not configured")  # fcg-rewrite
        metadata = {"tenant_id": str(tenant_id), "order_type": "subscription"}  # fcg-rewrite
        if tier_number is not None:  # fcg-rewrite
            metadata["tier_number"] = str(tier_number)  # fcg-rewrite
        session = stripe.checkout.Session.create(  # fcg-rewrite
            customer=customer_id,  # fcg-rewrite
            payment_method_types=["card"],  # fcg-rewrite
            line_items=[{"price": selected_price, "quantity": 1}],  # fcg-rewrite
            mode="subscription",  # fcg-rewrite
            success_url=self._url(success_url),  # fcg-rewrite
            cancel_url=self._url(cancel_url),  # fcg-rewrite
            metadata=metadata,  # fcg-rewrite
        )
        return self._checkout_result(session, customer_id)  # fcg-rewrite

    async def create_package_checkout(  # fcg-rewrite
        self,
        customer_id: str,  # fcg-rewrite
        amount: int,  # fcg-rewrite
        package_id: str,  # fcg-rewrite
        package_name: str,  # fcg-rewrite
        success_url: str,  # fcg-rewrite
        cancel_url: str,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        self._require_key()  # fcg-rewrite
        try:
            package_name.encode("ascii")  # fcg-rewrite
            display_name = package_name  # fcg-rewrite
        except UnicodeEncodeError:  # fcg-rewrite
            display_name = f"Scanner Package (ID: {package_id[:8]})"  # fcg-rewrite
        session = stripe.checkout.Session.create(  # fcg-rewrite
            customer=customer_id,  # fcg-rewrite
            payment_method_types=["card"],  # fcg-rewrite
            line_items=[{  # fcg-rewrite
                "price_data": {  # fcg-rewrite
                    "currency": "usd",  # fcg-rewrite
                    "product_data": {"name": display_name, "description": "FangcunGuard Scanner Package"},  # fcg-rewrite
                    "unit_amount": amount,  # fcg-rewrite
                },
                "quantity": 1,  # fcg-rewrite
            }],
            mode="payment",  # fcg-rewrite
            success_url=self._url(success_url),  # fcg-rewrite
            cancel_url=self._url(cancel_url),  # fcg-rewrite
            metadata={  # fcg-rewrite
                "tenant_id": str(tenant_id),  # fcg-rewrite
                "package_id": str(package_id),  # fcg-rewrite
                "package_name": package_name,  # fcg-rewrite
                "order_type": "package",  # fcg-rewrite
            },
        )
        return self._checkout_result(session, customer_id)  # fcg-rewrite

    async def get_checkout_session(self, session_id: str) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        self._require_key()  # fcg-rewrite
        try:
            session = stripe.checkout.Session.retrieve(session_id)  # fcg-rewrite
        except stripe_error.StripeError as error:  # fcg-rewrite
            logger.error("Unable to retrieve Stripe session %s: %s", session_id, error)  # fcg-rewrite
            return None  # fcg-rewrite
        return {  # fcg-rewrite
            field: getattr(session, field)  # fcg-rewrite
            for field in (  # fcg-rewrite
                "id", "status", "payment_status", "customer", "subscription",  # fcg-rewrite
                "payment_intent", "amount_total", "currency", "metadata",  # fcg-rewrite
            )
        }

    async def create_payment_intent(  # fcg-rewrite
        self,
        amount: int,  # fcg-rewrite
        currency: str = "usd",  # fcg-rewrite
        customer_id: Optional[str] = None,  # fcg-rewrite
        metadata: Optional[Dict[str, str]] = None,  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        self._require_key()  # fcg-rewrite
        params: Dict[str, Any] = {  # fcg-rewrite
            "amount": amount,  # fcg-rewrite
            "currency": currency,  # fcg-rewrite
            "automatic_payment_methods": {"enabled": True},  # fcg-rewrite
        }
        if customer_id:  # fcg-rewrite
            params["customer"] = customer_id  # fcg-rewrite
        if metadata:  # fcg-rewrite
            params["metadata"] = metadata  # fcg-rewrite
        intent = stripe.PaymentIntent.create(**params)  # fcg-rewrite
        return {"client_secret": intent.client_secret, "payment_intent_id": intent.id}  # fcg-rewrite

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:  # fcg-rewrite
        subscription = self._modify_subscription(subscription_id, True)  # fcg-rewrite
        return {  # fcg-rewrite
            "subscription_id": subscription.id,  # fcg-rewrite
            "status": subscription.status,  # fcg-rewrite
            "cancel_at_period_end": subscription.cancel_at_period_end,  # fcg-rewrite
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end),  # fcg-rewrite
        }

    async def reactivate_subscription(self, subscription_id: str) -> Dict[str, Any]:  # fcg-rewrite
        subscription = self._modify_subscription(subscription_id, False)  # fcg-rewrite
        return {  # fcg-rewrite
            "subscription_id": subscription.id,  # fcg-rewrite
            "status": subscription.status,  # fcg-rewrite
            "cancel_at_period_end": subscription.cancel_at_period_end,  # fcg-rewrite
        }

    def _modify_subscription(self, subscription_id: str, cancel: bool):  # fcg-rewrite
        self._require_key()  # fcg-rewrite
        return stripe.Subscription.modify(subscription_id, cancel_at_period_end=cancel)  # fcg-rewrite

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:  # fcg-rewrite
        self._require_key()  # fcg-rewrite
        subscription = stripe.Subscription.retrieve(subscription_id)  # fcg-rewrite
        return {  # fcg-rewrite
            "subscription_id": subscription.id,  # fcg-rewrite
            "status": subscription.status,  # fcg-rewrite
            "current_period_start": datetime.fromtimestamp(subscription.current_period_start),  # fcg-rewrite
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end),  # fcg-rewrite
            "cancel_at_period_end": subscription.cancel_at_period_end,  # fcg-rewrite
            "customer_id": subscription.customer,  # fcg-rewrite
        }

    def verify_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:  # fcg-rewrite
        if not self.webhook_secret:  # fcg-rewrite
            raise ValueError("Stripe webhook secret not configured")  # fcg-rewrite
        return stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)  # fcg-rewrite

    def parse_checkout_completed(self, event: Dict[str, Any]) -> Dict[str, Any]:  # fcg-rewrite
        source = event["data"]["object"]  # fcg-rewrite
        return {  # fcg-rewrite
            target: source.get(origin)  # fcg-rewrite
            for target, origin in {  # fcg-rewrite
                "session_id": "id", "customer_id": "customer", "subscription_id": "subscription",  # fcg-rewrite
                "payment_intent_id": "payment_intent", "amount_total": "amount_total",  # fcg-rewrite
                "currency": "currency", "payment_status": "payment_status", "metadata": "metadata",  # fcg-rewrite
            }.items()  # fcg-rewrite
        }

    def parse_invoice_paid(self, event: Dict[str, Any]) -> Dict[str, Any]:  # fcg-rewrite
        invoice = event["data"]["object"]  # fcg-rewrite
        timestamp = lambda name: datetime.fromtimestamp(invoice[name]) if invoice.get(name) else None  # fcg-rewrite
        return {  # fcg-rewrite
            "invoice_id": invoice.get("id"),  # fcg-rewrite
            "customer_id": invoice.get("customer"),  # fcg-rewrite
            "subscription_id": invoice.get("subscription"),  # fcg-rewrite
            "amount_paid": invoice.get("amount_paid"),  # fcg-rewrite
            "currency": invoice.get("currency"),  # fcg-rewrite
            "period_start": timestamp("period_start"),  # fcg-rewrite
            "period_end": timestamp("period_end"),  # fcg-rewrite
        }

    def get_publishable_key(self) -> str:  # fcg-rewrite
        return self.publishable_key  # fcg-rewrite


stripe_service = StripeService()  # fcg-rewrite
