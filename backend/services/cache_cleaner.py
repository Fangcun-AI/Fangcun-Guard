"""Periodic cleanup and observability for process-local caches."""

import asyncio

from services.keyword_cache import keyword_cache
from services.rate_limiter import rate_limiter
from utils.auth_cache import auth_cache
from utils.logger import setup_logger

logger = setup_logger()


class CacheJanitor:
    def __init__(self, interval: float = 60):
        self._cleanup_task = None
        self._running = False
        self._interval = interval

    async def start(self):
        if not self._running:
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Cache cleaner service started")

    async def stop(self):
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        logger.info("Cache cleaner service stopped")

    async def _cleanup_loop(self):
        while self._running:
            try:
                self._clean_once()
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.error(f"Cache cleanup error: {exc}")
                await asyncio.sleep(self._interval)

    def _clean_once(self):
        auth_cache.clear_expired()
        keyword_info = keyword_cache.get_cache_info()
        auth_count = auth_cache.size()
        rate_count = len(rate_limiter._local_cache)
        if auth_count or rate_count or keyword_info["blacklist_keywords"]:
            logger.debug(
                f"Cache stats: auth={auth_count}, rate={rate_count}, "
                f"blacklist={keyword_info['blacklist_keywords']}, "
                f"whitelist={keyword_info['whitelist_keywords']}"
            )


cache_cleaner = CacheJanitor()
