"""Runtime configuration helpers for config_api."""

from database.models import ApplicationSettings
from services.enhanced_template_service import enhanced_template_service
from services.keyword_cache import keyword_cache
from services.template_cache import template_cache


DEFAULT_FIXED_TEMPLATES = {
    "security_risk_template": {
        "en": "Request blocked by FangcunGuard due to possible violation of policy related to {scanner_name}.",
        "zh": "请求已被FangcunGuard拦截，原因：可能违反了与{scanner_name}有关的策略要求。",
    },
    "data_leakage_template": {
        "en": "Request blocked by FangcunGuard due to possible sensitive data ({entity_type_names}).",
        "zh": "请求已被FangcunGuard拦截，原因：可能包含敏感数据（{entity_type_names}）。",
    },
}


class ConfigRuntimeService:
    """Own cache inspection and fixed-answer template persistence."""

    def __init__(self, db) -> None:
        self.db = db

    def get_cache_info(self):
        return {
            "status": "success",
            "data": {
                "keyword_cache": keyword_cache.get_cache_info(),
                "template_cache": template_cache.get_cache_info(),
                "enhanced_template_cache": enhanced_template_service.get_cache_info(),
            },
        }

    async def refresh_all_caches(self):
        await keyword_cache.invalidate_cache()
        await template_cache.invalidate_cache()
        await enhanced_template_service.invalidate_cache()
        return {
            "status": "success",
            "message": "All caches refreshed successfully",
        }

    def get_fixed_answer_templates(self, application_id):
        app_settings = self.db.query(ApplicationSettings).filter(
            ApplicationSettings.application_id == application_id
        ).first()
        if not app_settings:
            return DEFAULT_FIXED_TEMPLATES
        return {
            "security_risk_template": app_settings.security_risk_template or DEFAULT_FIXED_TEMPLATES["security_risk_template"],
            "data_leakage_template": app_settings.data_leakage_template or DEFAULT_FIXED_TEMPLATES["data_leakage_template"],
        }

    async def update_fixed_answer_templates(self, tenant, application_id, body):
        app_settings = self.db.query(ApplicationSettings).filter(
            ApplicationSettings.application_id == application_id
        ).first()
        if not app_settings:
            app_settings = ApplicationSettings(
                tenant_id=tenant.id,
                application_id=application_id,
                security_risk_template=DEFAULT_FIXED_TEMPLATES["security_risk_template"],
                data_leakage_template=DEFAULT_FIXED_TEMPLATES["data_leakage_template"],
            )
            self.db.add(app_settings)

        if "security_risk_template" in body:
            existing = dict(app_settings.security_risk_template or DEFAULT_FIXED_TEMPLATES["security_risk_template"])
            if isinstance(body["security_risk_template"], dict):
                existing.update(body["security_risk_template"])
            else:
                existing = body["security_risk_template"]
            app_settings.security_risk_template = existing

        if "data_leakage_template" in body:
            existing = dict(app_settings.data_leakage_template or DEFAULT_FIXED_TEMPLATES["data_leakage_template"])
            if isinstance(body["data_leakage_template"], dict):
                existing.update(body["data_leakage_template"])
            else:
                existing = body["data_leakage_template"]
            app_settings.data_leakage_template = existing

        self.db.commit()
        await enhanced_template_service.invalidate_cache()
