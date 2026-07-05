import time  # fcg-rewrite
from datetime import datetime, timezone  # fcg-rewrite
from typing import Dict, Optional, Tuple  # fcg-rewrite

from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import TenantSubscription  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


def get_current_utc_time() -> datetime:  # fcg-rewrite
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)  # fcg-rewrite


class BillingSubscriptionSupport:  # fcg-rewrite
    """Shared subscription cache and lifecycle helpers."""

    def __init__(self, subscription_configs: Dict, cache_ttl: int = 60):  # fcg-rewrite
        self.subscription_configs = subscription_configs  # fcg-rewrite
        self.cache_ttl = cache_ttl  # fcg-rewrite
        self._subscription_cache: Dict[str, Tuple[TenantSubscription, float]] = {}  # fcg-rewrite

    def get_cached_subscription(self, tenant_id: str) -> Optional[TenantSubscription]:  # fcg-rewrite
        cache_entry = self._subscription_cache.get(tenant_id)  # fcg-rewrite
        if not cache_entry:  # fcg-rewrite
            return None  # fcg-rewrite

        subscription, cached_time = cache_entry  # fcg-rewrite
        if time.time() - cached_time < self.cache_ttl:  # fcg-rewrite
            return subscription  # fcg-rewrite
        return None  # fcg-rewrite

    def cache_subscription(self, tenant_id: str, subscription: TenantSubscription) -> None:  # fcg-rewrite
        self._subscription_cache[tenant_id] = (subscription, time.time())  # fcg-rewrite

    def clear_cache(self, tenant_id: Optional[str] = None) -> None:  # fcg-rewrite
        if tenant_id:  # fcg-rewrite
            self._subscription_cache.pop(tenant_id, None)  # fcg-rewrite
            logger.debug(f"Cleared billing cache for tenant {tenant_id}")  # fcg-rewrite
        else:
            self._subscription_cache.clear()  # fcg-rewrite
            logger.debug("Cleared all billing cache")  # fcg-rewrite

    def check_and_handle_expiry(self, subscription: TenantSubscription, db: Session) -> bool:  # fcg-rewrite
        if subscription.subscription_type != "subscribed":  # fcg-rewrite
            return False  # fcg-rewrite
        if subscription.subscription_expires_at is None:  # fcg-rewrite
            return False  # fcg-rewrite

        current_time = get_current_utc_time()  # fcg-rewrite
        if current_time <= subscription.subscription_expires_at:  # fcg-rewrite
            return False  # fcg-rewrite

        tenant_id = str(subscription.tenant_id)  # fcg-rewrite
        old_quota = subscription.monthly_quota  # fcg-rewrite
        free_config = self.subscription_configs.get("free", {})  # fcg-rewrite
        free_quota = free_config.get("monthly_quota", 1000)  # fcg-rewrite

        subscription.subscription_type = "free"  # fcg-rewrite
        subscription.monthly_quota = free_quota  # fcg-rewrite
        if hasattr(subscription, "subscription_tier"):  # fcg-rewrite
            subscription.subscription_tier = 0  # fcg-rewrite
        subscription.updated_at = current_time  # fcg-rewrite

        try:
            db.commit()  # fcg-rewrite
            self.clear_cache(tenant_id)  # fcg-rewrite
            logger.warning(  # fcg-rewrite
                f"Subscription expired for tenant {tenant_id}: "  # fcg-rewrite
                f"auto-downgraded to free (quota {old_quota} -> {free_quota})"  # fcg-rewrite
            )
            return True  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            logger.error(f"Failed to downgrade expired subscription for tenant {tenant_id}: {exc}")  # fcg-rewrite
            return False  # fcg-rewrite

    def calculate_next_reset_date(  # fcg-rewrite
        self,
        current_time: datetime,  # fcg-rewrite
        from_date: datetime = None,  # fcg-rewrite
    ) -> datetime:  # fcg-rewrite
        if from_date is None:  # fcg-rewrite
            from_date = current_time  # fcg-rewrite

        reset_day = from_date.day  # fcg-rewrite
        year = current_time.year  # fcg-rewrite
        month = current_time.month  # fcg-rewrite

        try:
            next_reset = datetime(year, month, reset_day, 0, 0, 0, tzinfo=timezone.utc)  # fcg-rewrite
            if next_reset <= current_time:  # fcg-rewrite
                if month == 12:  # fcg-rewrite
                    month = 1  # fcg-rewrite
                    year += 1  # fcg-rewrite
                else:
                    month += 1  # fcg-rewrite

                while True:  # fcg-rewrite
                    try:
                        next_reset = datetime(year, month, reset_day, 0, 0, 0, tzinfo=timezone.utc)  # fcg-rewrite
                        break
                    except ValueError:  # fcg-rewrite
                        if month == 2:  # fcg-rewrite
                            if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):  # fcg-rewrite
                                reset_day = 29  # fcg-rewrite
                            else:
                                reset_day = 28  # fcg-rewrite
                        elif month in [4, 6, 9, 11]:  # fcg-rewrite
                            reset_day = 30  # fcg-rewrite
                        else:
                            reset_day = 31  # fcg-rewrite
        except ValueError:  # fcg-rewrite
            if month == 12:  # fcg-rewrite
                month = 1  # fcg-rewrite
                year += 1  # fcg-rewrite
            else:
                month += 1  # fcg-rewrite
            next_reset = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)  # fcg-rewrite

        return next_reset  # fcg-rewrite
