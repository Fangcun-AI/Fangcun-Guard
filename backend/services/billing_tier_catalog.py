import json
import time
from typing import Dict, Optional

from sqlalchemy.orm import Session

from config import settings
from utils.logger import setup_logger

logger = setup_logger()


class BillingTierCatalog:
    """Tier config loader with short-lived caching."""

    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl
        self._tier_cache: Dict = {}
        self._tier_cache_time: float = 0

    def _load_stripe_price_ids_from_env(self) -> Dict[int, str]:
        raw = settings.stripe_price_ids
        if not raw:
            return {}
        try:
            mapping = json.loads(raw)
            return {int(key): value for key, value in mapping.items() if value}
        except Exception as exc:
            logger.warning(f"Failed to parse STRIPE_PRICE_IDS env var: {exc}")
            return {}

    def get_all_tiers(self, db: Session) -> list:
        from database.models import SubscriptionTier

        current_time = time.time()
        if self._tier_cache and (current_time - self._tier_cache_time < self.cache_ttl):
            return list(self._tier_cache.values())

        tiers = (
            db.query(SubscriptionTier)
            .filter(SubscriptionTier.is_active == True)
            .order_by(SubscriptionTier.display_order)
            .all()
        )

        env_price_ids = self._load_stripe_price_ids_from_env()
        self._tier_cache = {}
        for tier in tiers:
            self._tier_cache[tier.tier_number] = {
                "tier_number": tier.tier_number,
                "tier_name": tier.tier_name,
                "monthly_quota": tier.monthly_quota,
                "price_usd": float(tier.price_usd),
                "price_cny": float(tier.price_cny),
                "stripe_price_id": env_price_ids.get(tier.tier_number),
                "display_order": tier.display_order,
            }
        self._tier_cache_time = current_time

        return list(self._tier_cache.values())

    def get_tier_config(self, tier_number: int, db: Session) -> Optional[dict]:
        self.get_all_tiers(db)
        return self._tier_cache.get(tier_number)
