from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from config import settings


class PaymentProviderProfile:
    """Encapsulates provider, currency, and frontend payment config decisions."""

    def __init__(self, billing_service):
        self.billing_service = billing_service

    def get_payment_provider(self) -> str:
        if settings.default_language == "zh":
            return "alipay"
        return "stripe"

    def get_currency(self) -> str:
        if self.get_payment_provider() == "alipay":
            return "CNY"
        return "USD"

    def get_subscription_price(self) -> float:
        if self.get_payment_provider() == "alipay":
            return settings.subscription_price_cny
        return settings.subscription_price_usd

    def get_tier_price(self, tier_number: int, db: Session) -> float:
        tier_config = self.billing_service.get_tier_config(tier_number, db)
        if not tier_config:
            raise ValueError(f"Invalid tier number: {tier_number}")

        if self.get_payment_provider() == "alipay":
            return tier_config["price_cny"]
        return tier_config["price_usd"]

    def build_subscription_urls(self) -> Dict[str, str]:
        if settings.stripe_subscription_success_url:
            success_url = settings.stripe_subscription_success_url
        else:
            success_url = (
                f"{settings.frontend_url}/platform/subscription"
                "?payment=success&session_id={CHECKOUT_SESSION_ID}"
            )

        if settings.stripe_subscription_cancel_url:
            cancel_url = settings.stripe_subscription_cancel_url
        else:
            cancel_url = f"{settings.frontend_url}/platform/subscription?payment=cancelled"

        return {"success_url": success_url, "cancel_url": cancel_url}

    def build_package_urls(self) -> Dict[str, str]:
        if settings.stripe_package_success_url:
            success_url = settings.stripe_package_success_url
        else:
            success_url = (
                f"{settings.frontend_url}/platform/config/scanner-packages"
                "?payment=success&session_id={CHECKOUT_SESSION_ID}"
            )

        if settings.stripe_package_cancel_url:
            cancel_url = settings.stripe_package_cancel_url
        else:
            cancel_url = (
                f"{settings.frontend_url}/platform/config/scanner-packages?payment=cancelled"
            )

        return {"success_url": success_url, "cancel_url": cancel_url}

    def build_frontend_config(
        self,
        db: Optional[Session],
        stripe_publishable_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        provider = self.get_payment_provider()
        config: Dict[str, Any] = {
            "provider": provider,
            "currency": self.get_currency(),
            "subscription_price": self.get_subscription_price(),
            "tiers": [],
        }

        if provider == "stripe" and stripe_publishable_key:
            config["stripe_publishable_key"] = stripe_publishable_key

        if provider == "alipay":
            config["quota_purchase"] = {
                "price_per_unit": settings.quota_price_cny,
                "calls_per_unit": settings.quota_calls_per_unit,
                "min_units": 1,
                "validity_days": settings.quota_validity_days,
                "currency": "CNY",
            }

        if db:
            tiers = self.billing_service.get_all_tiers(db)
            price_key = "price_cny" if provider == "alipay" else "price_usd"
            config["tiers"] = [
                {
                    "tier_number": tier["tier_number"],
                    "tier_name": tier["tier_name"],
                    "monthly_quota": tier["monthly_quota"],
                    "price": tier[price_key],
                    "display_order": tier["display_order"],
                }
                for tier in tiers
            ]

        return config
