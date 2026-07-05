"""Tenant request-rate and monthly-usage enforcement."""

import asyncio  # fcg-rewrite
import time  # fcg-rewrite
from datetime import datetime  # fcg-rewrite
from typing import Dict, Optional  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

from sqlalchemy import and_, text  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import Tenant, TenantRateLimit  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


class PostgreSQLRateLimiter:  # fcg-rewrite
    """Cross-process one-second limiter backed by an atomic PostgreSQL upsert."""

    def __init__(self, cache_ttl: float = 30):  # fcg-rewrite
        self._rate_limits: Dict[str, int] = {}  # fcg-rewrite
        self._local_cache: Dict[str, tuple] = {}  # fcg-rewrite
        self._cache_update_time = 0.0  # fcg-rewrite
        self._cache_ttl = cache_ttl  # fcg-rewrite
        self._lock = None  # fcg-rewrite

    async def is_allowed(self, tenant_id: str, db: Session) -> bool:  # fcg-rewrite
        try:
            await self._update_config_cache_if_needed(db)  # fcg-rewrite
            rate_limit = self._rate_limits.get(tenant_id, 10)  # fcg-rewrite
            return True if rate_limit == 0 else await self._db_rate_limit_check(  # fcg-rewrite
                tenant_id, rate_limit, db  # fcg-rewrite
            )
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Rate limit check failed for tenant {tenant_id}: {exc}")  # fcg-rewrite
            return True  # fcg-rewrite

    async def _quick_local_check(self, tenant_id: str, rate_limit: int) -> bool:  # fcg-rewrite
        cached = self._local_cache.get(tenant_id)  # fcg-rewrite
        return bool(cached and cached[0] >= rate_limit)  # fcg-rewrite

    async def _db_rate_limit_check(  # fcg-rewrite
        self, tenant_id: str, rate_limit: int, db: Session  # fcg-rewrite
    ) -> bool:  # fcg-rewrite
        try:
            now = datetime.now()  # fcg-rewrite
            result = db.execute(  # fcg-rewrite
                text(
                    """
                    INSERT INTO tenant_rate_limit_counters
                        (tenant_id, current_count, window_start, last_updated)
                    VALUES (:tenant_id, 1, :now, :now)
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        current_count = CASE
                            WHEN tenant_rate_limit_counters.window_start < :now - INTERVAL '1 second'
                            THEN 1 ELSE tenant_rate_limit_counters.current_count + 1 END,
                        window_start = CASE
                            WHEN tenant_rate_limit_counters.window_start < :now - INTERVAL '1 second'
                            THEN :now ELSE tenant_rate_limit_counters.window_start END,
                        last_updated = :now
                    WHERE tenant_rate_limit_counters.current_count < :limit
                       OR tenant_rate_limit_counters.window_start < :now - INTERVAL '1 second'
                    RETURNING current_count
                    """
                ),
                {"tenant_id": UUID(tenant_id), "now": now, "limit": rate_limit},  # fcg-rewrite
            )
            row = result.fetchone()  # fcg-rewrite
            if not row:  # fcg-rewrite
                db.rollback()  # fcg-rewrite
                return False  # fcg-rewrite
            self._local_cache[tenant_id] = (row[0], time.monotonic())  # fcg-rewrite
            db.commit()  # fcg-rewrite
            return True  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Database rate limit check failed for {tenant_id}: {exc}")  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            return True  # fcg-rewrite

    async def _update_config_cache_if_needed(self, db: Session) -> None:  # fcg-rewrite
        if time.monotonic() - self._cache_update_time <= self._cache_ttl:  # fcg-rewrite
            return
        async with self._get_lock():  # fcg-rewrite
            if time.monotonic() - self._cache_update_time <= self._cache_ttl:  # fcg-rewrite
                return
            try:
                records = (  # fcg-rewrite
                    db.query(TenantRateLimit)  # fcg-rewrite
                    .filter(TenantRateLimit.is_active == True)  # fcg-rewrite
                    .all()
                )
                self._rate_limits = {  # fcg-rewrite
                    str(record.tenant_id): record.requests_per_second  # fcg-rewrite
                    for record in records  # fcg-rewrite
                }
                self._cache_update_time = time.monotonic()  # fcg-rewrite
            except Exception as exc:  # fcg-rewrite
                logger.error(f"Failed to refresh rate limits: {exc}")  # fcg-rewrite

    def clear_user_cache(self, tenant_id: str) -> None:  # fcg-rewrite
        self._local_cache.pop(tenant_id, None)  # fcg-rewrite
        self._cache_update_time = 0.0  # fcg-rewrite

    def _get_lock(self):  # fcg-rewrite
        if self._lock is None:  # fcg-rewrite
            self._lock = asyncio.Lock()  # fcg-rewrite
        return self._lock  # fcg-rewrite


rate_limiter = PostgreSQLRateLimiter()  # fcg-rewrite


class RateLimitService:  # fcg-rewrite
    """Administrative rate-limit configuration and monthly accounting."""

    def __init__(self, db: Session):  # fcg-rewrite
        self.db = db  # fcg-rewrite

    def check_and_increment_monthly_usage(  # fcg-rewrite
        self, tenant_id: str  # fcg-rewrite
    ) -> tuple[bool, Optional[int], Optional[int]]:  # fcg-rewrite
        try:
            config = self._find(UUID(tenant_id), active_only=True)  # fcg-rewrite
            if not config:  # fcg-rewrite
                return True, None, None  # fcg-rewrite
            if config.monthly_scan_limit == 0:  # fcg-rewrite
                return True, None, 0  # fcg-rewrite

            now = datetime.now()  # fcg-rewrite
            month = lambda value: value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)  # fcg-rewrite
            if config.usage_reset_at and month(now) > month(config.usage_reset_at):  # fcg-rewrite
                config.current_month_usage = 0  # fcg-rewrite
                config.usage_reset_at = now  # fcg-rewrite
            if config.current_month_usage >= config.monthly_scan_limit:  # fcg-rewrite
                self.db.commit()  # fcg-rewrite
                return False, config.current_month_usage, config.monthly_scan_limit  # fcg-rewrite
            config.current_month_usage += 1  # fcg-rewrite
            config.updated_at = now  # fcg-rewrite
            self.db.commit()  # fcg-rewrite
            return True, config.current_month_usage, config.monthly_scan_limit  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            self.db.rollback()  # fcg-rewrite
            logger.error(f"Failed to update monthly usage for {tenant_id}: {exc}")  # fcg-rewrite
            return True, None, None  # fcg-rewrite

    def get_user_rate_limit(self, tenant_id: str) -> Optional[TenantRateLimit]:  # fcg-rewrite
        try:
            return self._find(UUID(tenant_id))  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to get rate limit for {tenant_id}: {exc}")  # fcg-rewrite
            return None  # fcg-rewrite

    def set_user_rate_limit(  # fcg-rewrite
        self,
        tenant_id: str,  # fcg-rewrite
        requests_per_second: int,  # fcg-rewrite
        monthly_scan_limit: int = None,  # fcg-rewrite
    ) -> TenantRateLimit:  # fcg-rewrite
        try:
            from config import settings  # fcg-rewrite

            tenant_uuid = UUID(tenant_id)  # fcg-rewrite
            if not self.db.query(Tenant).filter(Tenant.id == tenant_uuid).first():  # fcg-rewrite
                raise ValueError(f"Tenant {tenant_id} not found")  # fcg-rewrite
            if monthly_scan_limit is None:  # fcg-rewrite
                monthly_scan_limit = (  # fcg-rewrite
                    settings.default_monthly_scan_limit  # fcg-rewrite
                    if settings.default_monthly_scan_limit is not None  # fcg-rewrite
                    else settings.free_user_monthly_quota  # fcg-rewrite
                )
            config = self._find(tenant_uuid)  # fcg-rewrite
            if not config:  # fcg-rewrite
                config = TenantRateLimit(  # fcg-rewrite
                    tenant_id=tenant_uuid,  # fcg-rewrite
                    current_month_usage=0,  # fcg-rewrite
                    usage_reset_at=datetime.now(),  # fcg-rewrite
                )
                self.db.add(config)  # fcg-rewrite
            config.requests_per_second = requests_per_second  # fcg-rewrite
            config.monthly_scan_limit = monthly_scan_limit  # fcg-rewrite
            config.is_active = True  # fcg-rewrite
            config.updated_at = datetime.now()  # fcg-rewrite
            self.db.commit()  # fcg-rewrite
            rate_limiter.clear_user_cache(tenant_id)  # fcg-rewrite
            return config  # fcg-rewrite
        except Exception:  # fcg-rewrite
            self.db.rollback()  # fcg-rewrite
            raise

    def disable_user_rate_limit(self, tenant_id: str) -> None:  # fcg-rewrite
        try:
            config = self._find(UUID(tenant_id))  # fcg-rewrite
            if config:  # fcg-rewrite
                config.is_active = False  # fcg-rewrite
                config.updated_at = datetime.now()  # fcg-rewrite
                self.db.commit()  # fcg-rewrite
                rate_limiter.clear_user_cache(tenant_id)  # fcg-rewrite
        except Exception:  # fcg-rewrite
            self.db.rollback()  # fcg-rewrite
            raise

    def list_user_rate_limits(  # fcg-rewrite
        self,
        skip: int = 0,  # fcg-rewrite
        limit: int = 100,  # fcg-rewrite
        search: str = None,  # fcg-rewrite
        sort_by: str = "requests_per_second",  # fcg-rewrite
        sort_order: str = "desc",  # fcg-rewrite
    ):
        query = self.db.query(Tenant, TenantRateLimit).outerjoin(  # fcg-rewrite
            TenantRateLimit,  # fcg-rewrite
            and_(
                TenantRateLimit.tenant_id == Tenant.id,  # fcg-rewrite
                TenantRateLimit.is_active == True,  # fcg-rewrite
                TenantRateLimit.application_id.is_(None),  # fcg-rewrite
            ),
        )
        if search:  # fcg-rewrite
            query = query.filter(Tenant.email.ilike(f"%{search}%"))  # fcg-rewrite
        total = query.count()  # fcg-rewrite
        if sort_by == "email":  # fcg-rewrite
            order = Tenant.email.asc() if sort_order.lower() == "asc" else Tenant.email.desc()  # fcg-rewrite
            query = query.order_by(order)  # fcg-rewrite
        else:
            rate = TenantRateLimit.requests_per_second  # fcg-rewrite
            order = rate.asc().nullsfirst() if sort_order.lower() == "asc" else rate.desc().nullslast()  # fcg-rewrite
            query = query.order_by(order, Tenant.email.asc())  # fcg-rewrite
        return query.offset(skip).limit(limit).all(), total  # fcg-rewrite

    def _find(self, tenant_uuid: UUID, active_only: bool = False):  # fcg-rewrite
        query = self.db.query(TenantRateLimit).filter(  # fcg-rewrite
            TenantRateLimit.tenant_id == tenant_uuid  # fcg-rewrite
        )
        if active_only:  # fcg-rewrite
            query = query.filter(TenantRateLimit.is_active == True)  # fcg-rewrite
        return query.first()  # fcg-rewrite
