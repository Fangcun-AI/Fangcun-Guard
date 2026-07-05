import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from services.risk_policy import (
    DEFAULT_TRIGGER_LEVEL,
    SensitivityThresholds,
    normalize_trigger_level,
    risk_switches_from_record,
)
from utils.logger import setup_logger

logger = setup_logger()


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class RiskConfigCache:
    """Short-lived application policy cache with database-failure defaults."""

    def __init__(self, cache_ttl: float = 300):
        self._risk_entries: Dict[str, _CacheEntry] = {}
        self._sensitivity_entries: Dict[str, _CacheEntry] = {}
        self._trigger_entries: Dict[str, _CacheEntry] = {}
        self._cache_ttl = cache_ttl
        self._lock = asyncio.Lock()

    async def get_user_risk_config(
        self, tenant_id: str = None, application_id: str = None
    ) -> Dict[str, bool]:
        cache_key = self._select_key(tenant_id, application_id)
        if not cache_key:
            return self._get_default_config()

        return await self._read_through(
            self._risk_entries,
            cache_key,
            lambda: self._load_from_db(cache_key, use_application_id=bool(application_id)),
            self._get_default_config,
            "risk config",
        )

    async def is_risk_type_enabled(
        self,
        tenant_id: str = None,
        application_id: str = None,
        risk_type: str = None,
    ) -> bool:
        config = await self.get_user_risk_config(
            tenant_id=tenant_id, application_id=application_id
        )
        return config.get(risk_type, True)

    async def get_sensitivity_thresholds(
        self, tenant_id: str = None, application_id: str = None
    ) -> Dict[str, float]:
        cache_key = self._select_key(tenant_id, application_id)
        if not cache_key:
            return self._get_default_sensitivity_thresholds()

        return await self._read_through(
            self._sensitivity_entries,
            cache_key,
            lambda: self._load_sensitivity_thresholds_from_db(
                cache_key, use_application_id=bool(application_id)
            ),
            self._get_default_sensitivity_thresholds,
            "sensitivity thresholds",
        )

    async def get_sensitivity_trigger_level(
        self, tenant_id: str = None, application_id: str = None
    ) -> str:
        cache_key = self._select_key(tenant_id, application_id)
        if not cache_key:
            return DEFAULT_TRIGGER_LEVEL

        return await self._read_through(
            self._trigger_entries,
            cache_key,
            lambda: self._load_trigger_level_from_db(
                cache_key, use_application_id=bool(application_id)
            ),
            lambda: DEFAULT_TRIGGER_LEVEL,
            "sensitivity trigger",
        )

    async def invalidate_user_cache(
        self, tenant_id: str = None, application_id: str = None
    ) -> None:
        cache_key = self._select_key(tenant_id, application_id)
        if not cache_key:
            return
        async with self._lock:
            self._risk_entries.pop(cache_key, None)
        logger.info(f"Invalidated risk config cache for {cache_key}")

    async def invalidate_sensitivity_cache(
        self, tenant_id: str = None, application_id: str = None
    ) -> None:
        cache_key = self._select_key(tenant_id, application_id)
        if not cache_key:
            return
        async with self._lock:
            self._sensitivity_entries.pop(cache_key, None)
            self._trigger_entries.pop(cache_key, None)
        logger.info(f"Invalidated sensitivity config cache for {cache_key}")

    async def clear_cache(self) -> None:
        async with self._lock:
            self._risk_entries.clear()
            self._sensitivity_entries.clear()
            self._trigger_entries.clear()
        logger.info("Cleared all risk config cache")

    async def _read_through(
        self,
        entries: Dict[str, _CacheEntry],
        cache_key: str,
        loader: Callable[[], Awaitable[Any]],
        fallback: Callable[[], Any],
        description: str,
    ) -> Any:
        async with self._lock:
            entry = entries.get(cache_key)
            if entry and time.monotonic() < entry.expires_at:
                return self._copy_value(entry.value)

            try:
                value = await loader()
            except Exception as exc:
                logger.error(f"Failed to load {description} for {cache_key}: {exc}")
                value = fallback()

            entries[cache_key] = _CacheEntry(
                value=self._copy_value(value),
                expires_at=time.monotonic() + self._cache_ttl,
            )
            return self._copy_value(value)

    async def _load_from_db(
        self, cache_key: str, use_application_id: bool = True
    ) -> Dict[str, bool]:
        return risk_switches_from_record(self._find_record(cache_key, use_application_id))

    async def _load_sensitivity_thresholds_from_db(
        self, cache_key: str, use_application_id: bool = True
    ) -> Dict[str, float]:
        record = self._find_record(cache_key, use_application_id)
        return SensitivityThresholds.from_record(record).as_dict()

    async def _load_trigger_level_from_db(
        self, cache_key: str, use_application_id: bool = True
    ) -> str:
        record = self._find_record(cache_key, use_application_id)
        return normalize_trigger_level(getattr(record, "sensitivity_trigger_level", None))

    def _find_record(self, cache_key: str, use_application_id: bool) -> Optional[object]:
        from database.connection import get_db
        from database.models import RiskTypeConfig

        db = next(get_db())
        try:
            lookup_field = (
                RiskTypeConfig.application_id if use_application_id else RiskTypeConfig.tenant_id
            )
            return db.query(RiskTypeConfig).filter(lookup_field == cache_key).first()
        finally:
            db.close()

    def _get_default_config(self) -> Dict[str, bool]:
        return risk_switches_from_record()

    def _get_default_sensitivity_thresholds(self) -> Dict[str, float]:
        return SensitivityThresholds().as_dict()

    @staticmethod
    def _select_key(tenant_id: str, application_id: str) -> Optional[str]:
        return application_id or tenant_id

    @staticmethod
    def _copy_value(value: Any) -> Any:
        return value.copy() if isinstance(value, dict) else value


risk_config_cache = RiskConfigCache()
