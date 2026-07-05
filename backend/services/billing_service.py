"""Subscription ledger and quota accounting."""

from datetime import datetime, timedelta, timezone  # fcg-rewrite
from typing import Dict, Optional, Tuple  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

from sqlalchemy import and_, func, text  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from config import settings  # fcg-rewrite
from database.models import DetectionResult, Tenant, TenantSubscription  # fcg-rewrite
from services.billing_subscription_support import BillingSubscriptionSupport, get_current_utc_time  # fcg-rewrite
from services.billing_tier_catalog import BillingTierCatalog  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


class BillingLedger:  # fcg-rewrite
    SUBSCRIPTION_CONFIGS: Dict = {}  # fcg-rewrite

    def __init__(self):  # fcg-rewrite
        self.subscription_support = BillingSubscriptionSupport(self.SUBSCRIPTION_CONFIGS)  # fcg-rewrite
        self.tier_catalog = BillingTierCatalog()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _tenant_uuid(tenant_id: str):  # fcg-rewrite
        return UUID(tenant_id)  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _find(db: Session, tenant_uuid):  # fcg-rewrite
        return db.query(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_uuid).first()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _is_admin(db: Session, tenant_uuid) -> bool:  # fcg-rewrite
        tenant = db.query(Tenant).filter(Tenant.id == tenant_uuid).first()  # fcg-rewrite
        return bool(tenant and getattr(tenant, "is_super_admin", False))  # fcg-rewrite

    def get_subscription(self, tenant_id: str, db: Session) -> Optional[TenantSubscription]:  # fcg-rewrite
        try:
            tenant_uuid = self._tenant_uuid(tenant_id)  # fcg-rewrite
            if self._is_admin(db, tenant_uuid):  # fcg-rewrite
                return TenantSubscription(  # fcg-rewrite
                    id=tenant_uuid, tenant_id=tenant_uuid, subscription_type="subscribed",  # fcg-rewrite
                    monthly_quota=999999999, current_month_usage=0,  # fcg-rewrite
                    usage_reset_at=datetime(2099, 12, 31, tzinfo=timezone.utc),  # fcg-rewrite
                )
            cached = self.subscription_support.get_cached_subscription(tenant_id)  # fcg-rewrite
            if cached:  # fcg-rewrite
                return cached  # fcg-rewrite
            subscription = self._find(db, tenant_uuid)  # fcg-rewrite
            if subscription:  # fcg-rewrite
                self.subscription_support.check_and_handle_expiry(subscription, db)  # fcg-rewrite
                self.subscription_support.cache_subscription(tenant_id, subscription)  # fcg-rewrite
            return subscription  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Unable to load subscription for %s: %s", tenant_id, error)  # fcg-rewrite
            return None  # fcg-rewrite

    def _reset_if_due(self, db: Session, tenant_id: str, subscription, now: datetime) -> None:  # fcg-rewrite
        if now < subscription.usage_reset_at:  # fcg-rewrite
            return
        subscription.current_month_usage = 0  # fcg-rewrite
        subscription.usage_reset_at = self._calculate_next_reset_date(now, subscription.created_at)  # fcg-rewrite
        subscription.updated_at = now  # fcg-rewrite
        db.commit()  # fcg-rewrite
        self.clear_cache(tenant_id)  # fcg-rewrite

    def check_and_increment_usage(self, tenant_id: str, db: Session) -> Tuple[bool, Optional[str]]:  # fcg-rewrite
        try:
            tenant_uuid, now = self._tenant_uuid(tenant_id), get_current_utc_time()  # fcg-rewrite
            if self._is_admin(db, tenant_uuid):  # fcg-rewrite
                return True, None  # fcg-rewrite
            subscription = self._find(db, tenant_uuid)  # fcg-rewrite
            if not subscription:  # fcg-rewrite
                try:
                    subscription = self.create_subscription(tenant_id, "free", db)  # fcg-rewrite
                except Exception:  # fcg-rewrite
                    return False, "Subscription not found. Please contact support."  # fcg-rewrite
            self.subscription_support.check_and_handle_expiry(subscription, db)  # fcg-rewrite
            self._reset_if_due(db, tenant_id, subscription, now)  # fcg-rewrite
            if getattr(subscription, "purchased_quota", 0) > 0:  # fcg-rewrite
                expiry = getattr(subscription, "purchased_quota_expires_at", None)  # fcg-rewrite
                if expiry and now > expiry:  # fcg-rewrite
                    subscription.purchased_quota = 0  # fcg-rewrite
                    subscription.purchased_quota_expires_at = None  # fcg-rewrite
                else:
                    subscription.purchased_quota -= 1  # fcg-rewrite
                    subscription.updated_at = now  # fcg-rewrite
                    db.commit()  # fcg-rewrite
                    self.clear_cache(tenant_id)  # fcg-rewrite
                    return True, None  # fcg-rewrite
            if subscription.current_month_usage >= subscription.monthly_quota:  # fcg-rewrite
                reset = subscription.usage_reset_at.strftime("%Y-%m-%d")  # fcg-rewrite
                return False, (  # fcg-rewrite
                    f"Monthly quota exceeded. Current usage: {subscription.current_month_usage}/"  # fcg-rewrite
                    f"{subscription.monthly_quota}. Quota resets on {reset}."  # fcg-rewrite
                )
            subscription.current_month_usage += 1  # fcg-rewrite
            subscription.updated_at = now  # fcg-rewrite
            db.commit()  # fcg-rewrite
            self.clear_cache(tenant_id)  # fcg-rewrite
            return True, None  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Quota accounting failed for %s: %s", tenant_id, error)  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            return True, None  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _period_start(period_end: datetime) -> datetime:  # fcg-rewrite
        previous_month = 12 if period_end.month == 1 else period_end.month - 1  # fcg-rewrite
        previous_year = period_end.year - 1 if period_end.month == 1 else period_end.year  # fcg-rewrite
        try:
            return period_end.replace(year=previous_year, month=previous_month)  # fcg-rewrite
        except ValueError:  # fcg-rewrite
            return period_end.replace(year=previous_year, month=previous_month, day=28)  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _usage_breakdown(db: Session, tenant_uuid, start: datetime, end: datetime) -> dict:  # fcg-rewrite
        direct = db.query(func.count(DetectionResult.id)).filter(and_(  # fcg-rewrite
            DetectionResult.tenant_id == tenant_uuid, DetectionResult.is_direct_model_access == True,  # fcg-rewrite
            DetectionResult.created_at >= start, DetectionResult.created_at < end,  # fcg-rewrite
        )).scalar() or 0  # fcg-rewrite
        total = db.query(func.count(DetectionResult.id)).filter(and_(  # fcg-rewrite
            DetectionResult.tenant_id == tenant_uuid, DetectionResult.created_at >= start,  # fcg-rewrite
            DetectionResult.created_at < end,  # fcg-rewrite
        )).scalar() or 0  # fcg-rewrite
        return {"guardrails_proxy": total - direct, "direct_model_access": direct}  # fcg-rewrite

    def get_subscription_with_usage(self, tenant_id: str, db: Session) -> Optional[dict]:  # fcg-rewrite
        try:
            tenant_uuid, now = self._tenant_uuid(tenant_id), get_current_utc_time()  # fcg-rewrite
            subscription = self._find(db, tenant_uuid) or self.create_subscription(tenant_id, "free", db)  # fcg-rewrite
            self.subscription_support.check_and_handle_expiry(subscription, db)  # fcg-rewrite
            self._reset_if_due(db, tenant_id, subscription, now)  # fcg-rewrite
            end, start = subscription.usage_reset_at, self._period_start(subscription.usage_reset_at)  # fcg-rewrite
            try:
                breakdown = self._usage_breakdown(db, tenant_uuid, start, end)  # fcg-rewrite
            except Exception as error:  # fcg-rewrite
                logger.warning("Unable to calculate usage breakdown for %s: %s", tenant_id, error)  # fcg-rewrite
                breakdown = {"guardrails_proxy": 0, "direct_model_access": 0}  # fcg-rewrite
            purchased = getattr(subscription, "purchased_quota", 0) or 0  # fcg-rewrite
            purchased_expiry = getattr(subscription, "purchased_quota_expires_at", None)  # fcg-rewrite
            if purchased_expiry and now > purchased_expiry:  # fcg-rewrite
                purchased, purchased_expiry = 0, None  # fcg-rewrite
            quota = subscription.monthly_quota  # fcg-rewrite
            return {  # fcg-rewrite
                "id": str(subscription.id), "tenant_id": str(subscription.tenant_id),  # fcg-rewrite
                "subscription_type": subscription.subscription_type,  # fcg-rewrite
                "subscription_tier": getattr(subscription, "subscription_tier", 0) or 0,  # fcg-rewrite
                "monthly_quota": quota, "current_month_usage": subscription.current_month_usage,  # fcg-rewrite
                "usage_reset_at": end.isoformat(),  # fcg-rewrite
                "usage_percentage": round(subscription.current_month_usage / quota * 100, 2) if quota else 0,  # fcg-rewrite
                "plan_name": self.SUBSCRIPTION_CONFIGS.get(subscription.subscription_type, {}).get("name", "Unknown"),  # fcg-rewrite
                "usage_breakdown": breakdown, "billing_period_start": start.isoformat(),  # fcg-rewrite
                "billing_period_end": end.isoformat(), "purchased_quota": purchased,  # fcg-rewrite
                "purchased_quota_expires_at": purchased_expiry.isoformat() if purchased_expiry else None,  # fcg-rewrite
            }
        except Exception as error:  # fcg-rewrite
            logger.error("Unable to summarize subscription for %s: %s", tenant_id, error)  # fcg-rewrite
            return None  # fcg-rewrite

    def create_subscription(self, tenant_id: str, subscription_type: str, db: Session) -> TenantSubscription:  # fcg-rewrite
        tenant_uuid = self._tenant_uuid(tenant_id)  # fcg-rewrite
        if self._find(db, tenant_uuid):  # fcg-rewrite
            raise ValueError(f"Subscription already exists for tenant {tenant_id}")  # fcg-rewrite
        if subscription_type not in self.SUBSCRIPTION_CONFIGS:  # fcg-rewrite
            raise ValueError(f"Invalid subscription type: {subscription_type}")  # fcg-rewrite
        subscription = TenantSubscription(  # fcg-rewrite
            tenant_id=tenant_uuid, subscription_type=subscription_type,  # fcg-rewrite
            monthly_quota=self.SUBSCRIPTION_CONFIGS[subscription_type]["monthly_quota"],  # fcg-rewrite
            current_month_usage=0, usage_reset_at=self._calculate_next_reset_date(get_current_utc_time()),  # fcg-rewrite
        )
        db.add(subscription)  # fcg-rewrite
        db.commit()  # fcg-rewrite
        db.refresh(subscription)  # fcg-rewrite
        return subscription  # fcg-rewrite

    def _load_required(self, tenant_id: str, db: Session):  # fcg-rewrite
        subscription = self._find(db, self._tenant_uuid(tenant_id))  # fcg-rewrite
        if not subscription:  # fcg-rewrite
            raise ValueError(f"Subscription not found for tenant {tenant_id}")  # fcg-rewrite
        return subscription  # fcg-rewrite

    def update_subscription_type(self, tenant_id: str, new_subscription_type: str, db: Session) -> TenantSubscription:  # fcg-rewrite
        if new_subscription_type not in self.SUBSCRIPTION_CONFIGS:  # fcg-rewrite
            raise ValueError(f"Invalid subscription type: {new_subscription_type}")  # fcg-rewrite
        subscription = self._load_required(tenant_id, db)  # fcg-rewrite
        subscription.subscription_type = new_subscription_type  # fcg-rewrite
        subscription.monthly_quota = self.SUBSCRIPTION_CONFIGS[new_subscription_type]["monthly_quota"]  # fcg-rewrite
        subscription.updated_at = get_current_utc_time()  # fcg-rewrite
        return self._commit(db, tenant_id, subscription)  # fcg-rewrite

    def reset_monthly_quota(self, tenant_id: str, db: Session) -> TenantSubscription:  # fcg-rewrite
        subscription, now = self._load_required(tenant_id, db), get_current_utc_time()  # fcg-rewrite
        subscription.current_month_usage = 0  # fcg-rewrite
        subscription.usage_reset_at = self._calculate_next_reset_date(now, subscription.created_at)  # fcg-rewrite
        subscription.updated_at = now  # fcg-rewrite
        return self._commit(db, tenant_id, subscription)  # fcg-rewrite

    def _commit(self, db: Session, tenant_id: str, subscription):  # fcg-rewrite
        db.commit()  # fcg-rewrite
        db.refresh(subscription)  # fcg-rewrite
        self.clear_cache(tenant_id)  # fcg-rewrite
        return subscription  # fcg-rewrite

    def reset_all_quotas(self, db: Session) -> int:  # fcg-rewrite
        now = get_current_utc_time()  # fcg-rewrite
        result = db.execute(text(  # fcg-rewrite
            "UPDATE tenant_subscriptions SET current_month_usage = 0, usage_reset_at = :next_reset, "  # fcg-rewrite
            "updated_at = :now WHERE usage_reset_at <= :now RETURNING tenant_id"  # fcg-rewrite
        ), {"next_reset": self._calculate_next_reset_date(now), "now": now})  # fcg-rewrite
        count = len(result.fetchall())  # fcg-rewrite
        db.commit()  # fcg-rewrite
        self.clear_cache()  # fcg-rewrite
        return count  # fcg-rewrite

    def list_subscriptions(  # fcg-rewrite
        self, db: Session, skip: int = 0, limit: int = 100, search: str = None,  # fcg-rewrite
        subscription_type: str = None, sort_by: str = "current_month_usage", sort_order: str = "desc",  # fcg-rewrite
    ):
        query = db.query(TenantSubscription).join(Tenant, TenantSubscription.tenant_id == Tenant.id)  # fcg-rewrite
        if search:  # fcg-rewrite
            query = query.filter(Tenant.email.ilike(f"%{search}%"))  # fcg-rewrite
        if subscription_type in self.SUBSCRIPTION_CONFIGS:  # fcg-rewrite
            query = query.filter(TenantSubscription.subscription_type == subscription_type)  # fcg-rewrite
        column = getattr(TenantSubscription, sort_by, TenantSubscription.current_month_usage)  # fcg-rewrite
        query = query.order_by(column.asc() if sort_order.lower() == "asc" else column.desc())  # fcg-rewrite
        total = query.count()  # fcg-rewrite
        return [{  # fcg-rewrite
            "id": str(item.id), "tenant_id": str(item.tenant_id), "email": item.tenant.email,  # fcg-rewrite
            "subscription_type": item.subscription_type, "monthly_quota": item.monthly_quota,  # fcg-rewrite
            "current_month_usage": item.current_month_usage, "usage_reset_at": item.usage_reset_at.isoformat(),  # fcg-rewrite
            "usage_percentage": round(item.current_month_usage / item.monthly_quota * 100, 2) if item.monthly_quota else 0,  # fcg-rewrite
            "plan_name": self.SUBSCRIPTION_CONFIGS.get(item.subscription_type, {}).get("name", "Unknown"),  # fcg-rewrite
        } for item in query.offset(skip).limit(limit).all()], total  # fcg-rewrite

    def get_all_tiers(self, db: Session) -> list:  # fcg-rewrite
        return self.tier_catalog.get_all_tiers(db)  # fcg-rewrite

    def get_tier_config(self, tier_number: int, db: Session) -> Optional[dict]:  # fcg-rewrite
        return self.tier_catalog.get_tier_config(tier_number, db)  # fcg-rewrite

    def update_subscription_tier(self, tenant_id: str, tier_number: int, db: Session) -> TenantSubscription:  # fcg-rewrite
        tier = self.get_tier_config(tier_number, db)  # fcg-rewrite
        if not tier:  # fcg-rewrite
            raise ValueError(f"Invalid tier number: {tier_number}")  # fcg-rewrite
        subscription = self._load_required(tenant_id, db)  # fcg-rewrite
        subscription.subscription_type = "subscribed"  # fcg-rewrite
        subscription.subscription_tier = tier_number  # fcg-rewrite
        subscription.monthly_quota = tier["monthly_quota"]  # fcg-rewrite
        subscription.updated_at = get_current_utc_time()  # fcg-rewrite
        return self._commit(db, tenant_id, subscription)  # fcg-rewrite

    def add_purchased_quota(self, tenant_id: str, units: int, db: Session) -> TenantSubscription:  # fcg-rewrite
        subscription, now = self._load_required(tenant_id, db), get_current_utc_time()  # fcg-rewrite
        if subscription.purchased_quota_expires_at and now > subscription.purchased_quota_expires_at:  # fcg-rewrite
            subscription.purchased_quota = 0  # fcg-rewrite
        subscription.purchased_quota = (subscription.purchased_quota or 0) + units * settings.quota_calls_per_unit  # fcg-rewrite
        subscription.purchased_quota_expires_at = now + timedelta(days=settings.quota_validity_days)  # fcg-rewrite
        subscription.updated_at = now  # fcg-rewrite
        return self._commit(db, tenant_id, subscription)  # fcg-rewrite

    def _calculate_next_reset_date(self, current_time: datetime, from_date: datetime = None) -> datetime:  # fcg-rewrite
        return self.subscription_support.calculate_next_reset_date(current_time, from_date)  # fcg-rewrite

    def clear_cache(self, tenant_id: str = None):  # fcg-rewrite
        self.subscription_support.clear_cache(tenant_id)  # fcg-rewrite


BillingLedger.SUBSCRIPTION_CONFIGS = {  # fcg-rewrite
    "free": {"monthly_quota": settings.free_user_monthly_quota, "name": "Free Plan"},  # fcg-rewrite
    "subscribed": {"monthly_quota": settings.paid_user_monthly_quota, "name": "Subscribed Plan"},  # fcg-rewrite
}
billing_service = BillingLedger()  # fcg-rewrite
