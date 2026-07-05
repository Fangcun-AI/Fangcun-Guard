"""Application-scoped in-memory keyword catalogs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from typing import List, Optional, Tuple

from database.connection import get_db_session
from database.models import Blacklist, Whitelist
from services.keyword_matching import KeywordCatalog
from utils.logger import setup_logger


logger = setup_logger()


@dataclass(frozen=True)
class KeywordSnapshot:
    blacklists: KeywordCatalog
    whitelists: KeywordCatalog
    refreshed_at: float

    @classmethod
    def empty(cls) -> "KeywordSnapshot":
        return cls(
            blacklists=KeywordCatalog.empty(),
            whitelists=KeywordCatalog.empty(),
            refreshed_at=0.0,
        )


class KeywordStore:
    """Refresh keyword lists lazily and expose a small async lookup API."""

    def __init__(self, cache_ttl: int = 300):
        self._ttl_seconds = cache_ttl
        self._snapshot = KeywordSnapshot.empty()
        self._refresh_after = 0.0
        self._refresh_lock = asyncio.Lock()

    async def check_blacklist(
        self,
        content: str,
        tenant_id: Optional[str] = None,
        application_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], List[str]]:
        return await self._check("blacklists", content, tenant_id, application_id)

    async def check_whitelist(
        self,
        content: str,
        tenant_id: Optional[str] = None,
        application_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], List[str]]:
        return await self._check("whitelists", content, tenant_id, application_id)

    async def _check(
        self,
        catalog_name: str,
        content: str,
        tenant_id: Optional[str],
        application_id: Optional[str],
    ) -> Tuple[bool, Optional[str], List[str]]:
        await self._ensure_current()
        catalog = getattr(self._snapshot, catalog_name)
        scope_id = application_id or tenant_id
        match = catalog.search(scope_id, content)
        if match is None:
            return False, None, []

        logger.info(
            "%s hit: %s, keywords: %s, scope_id: %s",
            catalog_name[:-1].capitalize(),
            match.list_name,
            match.keywords,
            scope_id,
        )
        return True, match.list_name, list(match.keywords)

    async def _ensure_current(self) -> None:
        if time.monotonic() < self._refresh_after:
            return

        async with self._refresh_lock:
            if time.monotonic() >= self._refresh_after:
                self._reload()

    def _reload(self) -> None:
        db = None
        try:
            db = get_db_session()
            blacklists = db.query(Blacklist).filter_by(is_active=True).all()
            whitelists = db.query(Whitelist).filter_by(is_active=True).all()
            refreshed_at = time.time()
            snapshot = KeywordSnapshot(
                blacklists=KeywordCatalog.from_records(blacklists),
                whitelists=KeywordCatalog.from_records(whitelists),
                refreshed_at=refreshed_at,
            )
            self._snapshot = snapshot
            self._refresh_after = time.monotonic() + self._ttl_seconds
            logger.debug(
                "Keyword catalogs refreshed: blacklist=%s lists/%s keywords, "
                "whitelist=%s lists/%s keywords",
                snapshot.blacklists.list_count,
                snapshot.blacklists.keyword_count,
                snapshot.whitelists.list_count,
                snapshot.whitelists.keyword_count,
            )
        except Exception as exc:
            logger.error("Failed to refresh keyword catalogs: %s", exc)
        finally:
            if db is not None:
                db.close()

    async def invalidate_cache(self) -> None:
        async with self._refresh_lock:
            self._refresh_after = 0.0
        logger.info("Keyword cache invalidated")

    def get_cache_info(self) -> dict:
        snapshot = self._snapshot
        age = time.time() - snapshot.refreshed_at if snapshot.refreshed_at else 0
        return {
            "applications_with_blacklists": len(snapshot.blacklists.scopes),
            "applications_with_whitelists": len(snapshot.whitelists.scopes),
            "blacklist_lists": snapshot.blacklists.list_count,
            "blacklist_keywords": snapshot.blacklists.keyword_count,
            "whitelist_lists": snapshot.whitelists.list_count,
            "whitelist_keywords": snapshot.whitelists.keyword_count,
            "last_refresh": snapshot.refreshed_at,
            "cache_age_seconds": age,
        }

keyword_cache = KeywordStore(cache_ttl=300)
