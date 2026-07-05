"""Service-level concurrent request limiter."""

import asyncio
import time
from typing import Dict, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from utils.logger import setup_logger

logger = setup_logger()


class ConcurrentLimitMiddleware(BaseHTTPMiddleware):
    _semaphores: Dict[str, asyncio.Semaphore] = {}
    _stats: Dict[str, Dict[str, int]] = {}

    def __init__(self, app, service_type: str, max_concurrent: int):
        super().__init__(app)
        self.service_type = service_type
        self.max_concurrent = max_concurrent
        if service_type not in self._semaphores:
            self._semaphores[service_type] = asyncio.Semaphore(max_concurrent)
            self._stats[service_type] = self._empty_stats()
            logger.info(
                f"Concurrent limiter initialized for {service_type}: {max_concurrent}"
            )

    async def dispatch(self, request: Request, call_next):
        semaphore = self._semaphores[self.service_type]
        stats = self._stats[self.service_type]
        stats["total_requests"] += 1
        acquired = await self._try_acquire(semaphore)
        if not acquired:
            stats["rejected_requests"] += 1
            logger.warning(
                f"Concurrent limit reached for {self.service_type}: "
                f"{stats['current_requests']}/{self.max_concurrent} at {request.url.path}"
            )
            return self._overloaded_response()
        stats["current_requests"] += 1
        stats["max_concurrent_reached"] = max(
            stats["max_concurrent_reached"], stats["current_requests"]
        )
        started = time.monotonic()
        try:
            response = await call_next(request)
            response.headers.update(
                {
                    "X-Service-Type": self.service_type,
                    "X-Concurrent-Limit": str(self.max_concurrent),
                    "X-Current-Concurrent": str(stats["current_requests"]),
                    "X-Processing-Time": f"{(time.monotonic() - started) * 1000:.2f}ms",
                }
            )
            return response
        finally:
            stats["current_requests"] -= 1
            semaphore.release()

    async def _try_acquire(
        self, semaphore: asyncio.Semaphore, timeout: float = 0.001
    ) -> bool:
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def _overloaded_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": (
                        "Service temporarily overloaded. Maximum "
                        f"{self.max_concurrent} concurrent requests allowed."
                    ),
                    "type": "service_overloaded",
                    "code": 429,
                    "service": self.service_type,
                    "retry_after": 1,
                }
            },
            headers={"Retry-After": "1"},
        )

    @staticmethod
    def _empty_stats() -> Dict[str, int]:
        return {
            "current_requests": 0,
            "total_requests": 0,
            "rejected_requests": 0,
            "max_concurrent_reached": 0,
        }

    @classmethod
    def get_stats(cls, service_type: str) -> Optional[Dict[str, int]]:
        return cls._stats.get(service_type)

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, int]]:
        return cls._stats.copy()

    @classmethod
    def reset_stats(cls, service_type: str = None):
        services = [service_type] if service_type else list(cls._stats)
        for name in services:
            if name in cls._stats:
                current = cls._stats[name]["current_requests"]
                cls._stats[name] = {**cls._empty_stats(), "current_requests": current}
        logger.info(f"Reset concurrent stats for {service_type or 'all services'}")
