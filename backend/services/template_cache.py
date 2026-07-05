"""Application-scoped cache for legacy response-template lookup."""

import asyncio
import time
from typing import Dict, List, Optional

from database.connection import get_db_session
from database.models import ResponseTemplate
from services.risk_policy import CATEGORY_LABELS, CATEGORY_RISK_LEVELS, RISK_LEVEL_SCORES
from utils.logger import setup_logger

logger = setup_logger()

_CATEGORY_CODES_BY_LABEL = {label: code for code, label in CATEGORY_LABELS.items()}
_FALLBACK_ANSWER = (
    "Sorry, I can't answer this question. Please contact customer service "
    "if you have any questions."
)


class TemplateCache:
    """Keep enabled answer templates in memory between configuration changes."""

    def __init__(self, cache_ttl: int = 600):
        self._template_cache: Dict[str, Dict[str, Dict[bool, str]]] = {}
        self._cache_timestamp = 0.0
        self._cache_ttl = cache_ttl
        self._lock = None

    async def get_suggest_answer(
        self,
        categories: List[str],
        tenant_id: Optional[str] = None,
        application_id: Optional[str] = None,
    ) -> str:
        await self._ensure_cache_fresh()
        cache_key = application_id or tenant_id
        for category_code in self._ordered_codes(categories):
            answer = self._answer_for_category(cache_key, category_code)
            if answer is not None:
                return answer
        return self._get_default_answer(cache_key)

    async def _ensure_cache_fresh(self) -> None:
        if time.time() - self._cache_timestamp <= self._cache_ttl:
            return
        async with self._get_lock():
            if time.time() - self._cache_timestamp > self._cache_ttl:
                await self._refresh_cache()

    async def _refresh_cache(self) -> None:
        try:
            db = get_db_session()
            try:
                templates = db.query(ResponseTemplate).filter_by(is_active=True).all()
                refreshed: Dict[str, Dict[str, Dict[bool, str]]] = {}
                for template in templates:
                    app_key = (
                        str(template.application_id)
                        if template.application_id is not None
                        else "__global__"
                    )
                    category = template.category or template.scanner_identifier
                    if not category:
                        continue
                    refreshed.setdefault(app_key, {}).setdefault(category, {})[
                        bool(template.is_default)
                    ] = template.template_content
                self._template_cache = refreshed
                self._cache_timestamp = time.time()
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Failed to refresh template cache: {exc}")

    async def invalidate_cache(self) -> None:
        async with self._get_lock():
            self._cache_timestamp = 0.0
        logger.info("Template cache invalidated")

    def get_cache_info(self) -> dict:
        template_count = sum(
            len(variants)
            for categories in self._template_cache.values()
            for variants in categories.values()
        )
        return {
            "applications": len(self._template_cache),
            "templates": template_count,
            "last_refresh": self._cache_timestamp,
            "cache_age_seconds": (
                time.time() - self._cache_timestamp if self._cache_timestamp else 0
            ),
        }

    def _get_lock(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _answer_for_category(
        self, cache_key: Optional[str], category_code: str
    ) -> Optional[str]:
        app_templates = self._template_cache.get(str(cache_key or "__none__"), {})
        global_templates = self._template_cache.get("__global__", {})
        return (
            self._preferred_variant(app_templates.get(category_code))
            or self._preferred_variant(global_templates.get(category_code), default_only=True)
        )

    def _get_default_answer(self, cache_key: Optional[str]) -> str:
        app_templates = self._template_cache.get(str(cache_key or "__none__"), {})
        global_templates = self._template_cache.get("__global__", {})
        return (
            self._preferred_variant(app_templates.get("default"), default_only=True)
            or self._preferred_variant(global_templates.get("default"), default_only=True)
            or _FALLBACK_ANSWER
        )

    @staticmethod
    def _preferred_variant(
        variants: Optional[Dict[bool, str]], *, default_only: bool = False
    ) -> Optional[str]:
        if not variants:
            return None
        if not default_only and False in variants:
            return variants[False]
        return variants.get(True)

    @staticmethod
    def _ordered_codes(categories: List[str]) -> List[str]:
        codes = {
            _CATEGORY_CODES_BY_LABEL.get(category, category)
            for category in categories
            if _CATEGORY_CODES_BY_LABEL.get(category, category) in CATEGORY_RISK_LEVELS
        }
        return sorted(
            codes,
            key=lambda code: RISK_LEVEL_SCORES[CATEGORY_RISK_LEVELS[code]],
            reverse=True,
        )


template_cache = TemplateCache(cache_ttl=600)
