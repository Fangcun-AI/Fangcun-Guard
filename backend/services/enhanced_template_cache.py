import asyncio  # fcg-rewrite
import time  # fcg-rewrite
from typing import Dict, List, Optional  # fcg-rewrite

from database.connection import get_db_session  # fcg-rewrite
from database.models import ApplicationSettings, KnowledgeBase, TenantKnowledgeBaseDisable  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


class EnhancedTemplateCache:  # fcg-rewrite
    """Cache store for KB mappings and application answer templates."""

    def __init__(self, cache_ttl: int = 600):  # fcg-rewrite
        self._knowledge_base_cache: Dict[str, Dict[str, List[int]]] = {}  # fcg-rewrite
        self._global_knowledge_base_cache: Dict[str, List[int]] = {}  # fcg-rewrite
        self._tenant_disabled_kb_cache: Dict[str, set] = {}  # fcg-rewrite
        self._application_settings_cache: Dict[str, dict] = {}  # fcg-rewrite
        self._cache_timestamp = 0.0  # fcg-rewrite
        self._cache_ttl = cache_ttl  # fcg-rewrite
        self._lock = asyncio.Lock()  # fcg-rewrite

    async def ensure_fresh(self) -> None:  # fcg-rewrite
        current_time = time.time()  # fcg-rewrite
        if current_time - self._cache_timestamp > self._cache_ttl:  # fcg-rewrite
            async with self._lock:  # fcg-rewrite
                if current_time - self._cache_timestamp > self._cache_ttl:  # fcg-rewrite
                    await self.refresh()  # fcg-rewrite

    async def refresh(self) -> None:  # fcg-rewrite
        try:
            db = get_db_session()  # fcg-rewrite
            try:
                knowledge_bases = db.query(KnowledgeBase).filter_by(is_active=True).all()  # fcg-rewrite
                new_kb_cache: Dict[str, Dict[str, List[int]]] = {}  # fcg-rewrite
                global_kb_cache: Dict[str, List[int]] = {}  # fcg-rewrite

                for kb in knowledge_bases:  # fcg-rewrite
                    app_key = str(kb.application_id) if kb.application_id else None  # fcg-rewrite
                    if not app_key:  # fcg-rewrite
                        continue  # fcg-rewrite

                    cache_key = None  # fcg-rewrite
                    if kb.scanner_type and kb.scanner_identifier:  # fcg-rewrite
                        cache_key = f"{kb.scanner_type}:{kb.scanner_identifier}"  # fcg-rewrite
                    elif kb.category:  # fcg-rewrite
                        cache_key = kb.category  # fcg-rewrite

                    if not cache_key:  # fcg-rewrite
                        continue  # fcg-rewrite

                    new_kb_cache.setdefault(app_key, {}).setdefault(cache_key, []).append(kb.id)  # fcg-rewrite

                    if kb.is_global:  # fcg-rewrite
                        global_kb_cache.setdefault(cache_key, []).append(kb.id)  # fcg-rewrite

                tenant_disabled_kb_cache: Dict[str, set] = {}  # fcg-rewrite
                disabled_records = db.query(TenantKnowledgeBaseDisable).all()  # fcg-rewrite
                for record in disabled_records:  # fcg-rewrite
                    tenant_key = str(record.tenant_id)  # fcg-rewrite
                    tenant_disabled_kb_cache.setdefault(tenant_key, set()).add(record.kb_id)  # fcg-rewrite

                application_settings_cache: Dict[str, dict] = {}  # fcg-rewrite
                app_settings_records = db.query(ApplicationSettings).all()  # fcg-rewrite
                for settings in app_settings_records:  # fcg-rewrite
                    app_key = str(settings.application_id)  # fcg-rewrite
                    application_settings_cache[app_key] = {  # fcg-rewrite
                        "security_risk_template": settings.security_risk_template,  # fcg-rewrite
                        "data_leakage_template": settings.data_leakage_template,  # fcg-rewrite
                    }

                self._knowledge_base_cache = new_kb_cache  # fcg-rewrite
                self._global_knowledge_base_cache = global_kb_cache  # fcg-rewrite
                self._tenant_disabled_kb_cache = tenant_disabled_kb_cache  # fcg-rewrite
                self._application_settings_cache = application_settings_cache  # fcg-rewrite
                self._cache_timestamp = time.time()  # fcg-rewrite

                kb_count = sum(  # fcg-rewrite
                    sum(len(kb_ids) for kb_ids in app_kbs.values())  # fcg-rewrite
                    for app_kbs in new_kb_cache.values()  # fcg-rewrite
                )
                logger.debug(  # fcg-rewrite
                    f"KB cache refreshed: {kb_count} knowledge bases, "  # fcg-rewrite
                    f"{len(application_settings_cache)} app settings"  # fcg-rewrite
                )
            finally:  # fcg-rewrite
                db.close()  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to refresh KB cache: {exc}", exc_info=True)  # fcg-rewrite

    async def invalidate(self) -> None:  # fcg-rewrite
        async with self._lock:  # fcg-rewrite
            try:
                db = get_db_session()  # fcg-rewrite
                try:
                    application_settings_cache: Dict[str, dict] = {}  # fcg-rewrite
                    app_settings_records = db.query(ApplicationSettings).all()  # fcg-rewrite
                    for settings in app_settings_records:  # fcg-rewrite
                        app_key = str(settings.application_id)  # fcg-rewrite
                        application_settings_cache[app_key] = {  # fcg-rewrite
                            "security_risk_template": settings.security_risk_template,  # fcg-rewrite
                            "data_leakage_template": settings.data_leakage_template,  # fcg-rewrite
                        }
                    self._application_settings_cache = application_settings_cache  # fcg-rewrite
                    logger.info(  # fcg-rewrite
                        f"Application settings cache refreshed: {len(application_settings_cache)} settings"  # fcg-rewrite
                    )
                finally:  # fcg-rewrite
                    db.close()  # fcg-rewrite
            except Exception as exc:  # fcg-rewrite
                logger.error(f"Failed to refresh application settings cache: {exc}", exc_info=True)  # fcg-rewrite

            self._cache_timestamp = 0  # fcg-rewrite
            logger.info("Enhanced template cache invalidated")  # fcg-rewrite

    def get_kb_ids_for_key(  # fcg-rewrite
        self,
        application_id: str,  # fcg-rewrite
        cache_key: str,  # fcg-rewrite
        tenant_id: Optional[str],  # fcg-rewrite
    ) -> List[int]:  # fcg-rewrite
        app_cache = self._knowledge_base_cache.get(str(application_id), {})  # fcg-rewrite
        kb_ids = app_cache.get(cache_key, []).copy()  # fcg-rewrite
        global_kb_ids = self._global_knowledge_base_cache.get(cache_key, [])  # fcg-rewrite
        disabled_kb_ids = self._tenant_disabled_kb_cache.get(str(tenant_id), set()) if tenant_id else set()  # fcg-rewrite
        filtered_global_kb_ids = [kb_id for kb_id in global_kb_ids if kb_id not in disabled_kb_ids]  # fcg-rewrite
        kb_ids.extend(filtered_global_kb_ids)  # fcg-rewrite
        return list(set(kb_ids))  # fcg-rewrite

    def get_application_settings(self, application_id: Optional[str]) -> Optional[dict]:  # fcg-rewrite
        if not application_id:  # fcg-rewrite
            return None  # fcg-rewrite
        return self._application_settings_cache.get(str(application_id))  # fcg-rewrite

    def get_cache_info(self) -> dict:  # fcg-rewrite
        kb_count = sum(  # fcg-rewrite
            sum(len(kb_ids) for kb_ids in app_kbs.values())  # fcg-rewrite
            for app_kbs in self._knowledge_base_cache.values()  # fcg-rewrite
        )
        global_kb_count = sum(len(kb_ids) for kb_ids in self._global_knowledge_base_cache.values())  # fcg-rewrite
        return {  # fcg-rewrite
            "applications": len(self._knowledge_base_cache),  # fcg-rewrite
            "application_settings": len(self._application_settings_cache),  # fcg-rewrite
            "templates": 0,  # fcg-rewrite
            "knowledge_bases": kb_count,  # fcg-rewrite
            "global_knowledge_bases": global_kb_count,  # fcg-rewrite
            "last_refresh": self._cache_timestamp,  # fcg-rewrite
            "cache_age_seconds": time.time() - self._cache_timestamp if self._cache_timestamp > 0 else 0,  # fcg-rewrite
        }
