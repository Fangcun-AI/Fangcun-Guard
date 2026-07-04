"""Persistence helpers for proxy model and upstream gateway configs."""

import uuid  # fcg-rewrite
from typing import Any, Callable, Dict, List, Optional  # fcg-rewrite

from database.models import OnlineTestModelSelection, ProxyModelConfig, ProxyRequestLog, UpstreamApiConfig  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite


logger = setup_logger()  # fcg-rewrite


class ProxyConfigStore:  # fcg-rewrite
    """Owns database access for proxy model and upstream gateway configs."""

    def __init__(self, session_factory: Callable[[], object], credential_cipher) -> None:  # fcg-rewrite
        self._session_factory = session_factory  # fcg-rewrite
        self._credential_cipher = credential_cipher  # fcg-rewrite

    async def list_tenant_models(self, tenant_id: str) -> List[ProxyModelConfig]:  # fcg-rewrite
        tenant_uuid = self._as_uuid(tenant_id)  # fcg-rewrite
        db = self._session_factory()  # fcg-rewrite
        try:
            models = (  # fcg-rewrite
                db.query(ProxyModelConfig)  # fcg-rewrite
                .filter(  # fcg-rewrite
                    ProxyModelConfig.tenant_id == tenant_uuid,  # fcg-rewrite
                    ProxyModelConfig.enabled == True,  # fcg-rewrite
                )
                .order_by(ProxyModelConfig.created_at)  # fcg-rewrite
                .all()
            )
            for model in models:  # fcg-rewrite
                self._hydrate_proxy_model(db, model)  # fcg-rewrite
            return models  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    async def load_upstream_api_config(  # fcg-rewrite
        self,
        upstream_api_id: str,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
    ) -> Optional[UpstreamApiConfig]:  # fcg-rewrite
        upstream_uuid = self._as_uuid(upstream_api_id)  # fcg-rewrite
        tenant_uuid = self._as_uuid(tenant_id)  # fcg-rewrite
        db = self._session_factory()  # fcg-rewrite
        try:
            config = (  # fcg-rewrite
                db.query(UpstreamApiConfig)  # fcg-rewrite
                .filter(  # fcg-rewrite
                    UpstreamApiConfig.id == upstream_uuid,  # fcg-rewrite
                    UpstreamApiConfig.tenant_id == tenant_uuid,  # fcg-rewrite
                    UpstreamApiConfig.is_active == True,  # fcg-rewrite
                )
                .first()  # fcg-rewrite
            )
            if config:  # fcg-rewrite
                self._hydrate_upstream_config(db, config)  # fcg-rewrite
                logger.info(  # fcg-rewrite
                    "Retrieved upstream API config: id=%s, config_name=%s, api_base_url=%s",  # fcg-rewrite
                    config.id,  # fcg-rewrite
                    config.config_name,  # fcg-rewrite
                    config.api_base_url,  # fcg-rewrite
                )
            return config  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    async def load_tenant_model_config(  # fcg-rewrite
        self,
        tenant_id: str,  # fcg-rewrite
        model_name: str,  # fcg-rewrite
    ) -> Optional[ProxyModelConfig]:  # fcg-rewrite
        tenant_uuid = self._as_uuid(tenant_id)  # fcg-rewrite
        db = self._session_factory()  # fcg-rewrite
        try:
            model = (  # fcg-rewrite
                db.query(ProxyModelConfig)  # fcg-rewrite
                .filter(  # fcg-rewrite
                    ProxyModelConfig.tenant_id == tenant_uuid,  # fcg-rewrite
                    ProxyModelConfig.config_name == model_name,  # fcg-rewrite
                    ProxyModelConfig.enabled == True,  # fcg-rewrite
                )
                .first()  # fcg-rewrite
            )
            if not model:  # fcg-rewrite
                model = (  # fcg-rewrite
                    db.query(ProxyModelConfig)  # fcg-rewrite
                    .filter(  # fcg-rewrite
                        ProxyModelConfig.tenant_id == tenant_uuid,  # fcg-rewrite
                        ProxyModelConfig.enabled == True,  # fcg-rewrite
                    )
                    .first()  # fcg-rewrite
                )

            if model:  # fcg-rewrite
                self._hydrate_proxy_model(db, model)  # fcg-rewrite
            return model  # fcg-rewrite
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    async def create_user_model(self, tenant_id: str, model_data: Dict[str, Any]) -> ProxyModelConfig:  # fcg-rewrite
        tenant_uuid = self._as_uuid(tenant_id)  # fcg-rewrite
        db = self._session_factory()  # fcg-rewrite
        try:
            self._validate_required_model_fields(model_data)  # fcg-rewrite
            existing = (  # fcg-rewrite
                db.query(ProxyModelConfig)  # fcg-rewrite
                .filter(  # fcg-rewrite
                    ProxyModelConfig.tenant_id == tenant_uuid,  # fcg-rewrite
                    ProxyModelConfig.config_name == model_data["config_name"],  # fcg-rewrite
                )
                .first()  # fcg-rewrite
            )
            if existing:  # fcg-rewrite
                raise ValueError(f"Model configuration '{model_data['config_name']}' already exists")  # fcg-rewrite

            model_config = ProxyModelConfig(  # fcg-rewrite
                tenant_id=tenant_uuid,  # fcg-rewrite
                config_name=model_data["config_name"],  # fcg-rewrite
                api_base_url=model_data["api_base_url"].rstrip("/"),  # fcg-rewrite
                api_key_encrypted=self._credential_cipher.encrypt(model_data["api_key"]),  # fcg-rewrite
                model_name=model_data["model_name"],  # fcg-rewrite
                enabled=model_data.get("enabled", True),  # fcg-rewrite
                enable_reasoning_detection=model_data.get("enable_reasoning_detection", True),  # fcg-rewrite
            )
            db.add(model_config)  # fcg-rewrite
            db.commit()  # fcg-rewrite
            db.refresh(model_config)  # fcg-rewrite
            logger.info("Created proxy model config '%s' for user %s", model_config.config_name, tenant_uuid)  # fcg-rewrite
            return model_config  # fcg-rewrite
        except Exception:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            raise
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    async def update_user_model(  # fcg-rewrite
        self,
        tenant_id: str,  # fcg-rewrite
        model_id: str,  # fcg-rewrite
        model_data: Dict[str, Any],  # fcg-rewrite
    ) -> ProxyModelConfig:  # fcg-rewrite
        tenant_uuid = self._as_uuid(tenant_id)  # fcg-rewrite
        db = self._session_factory()  # fcg-rewrite
        try:
            model_config = (  # fcg-rewrite
                db.query(ProxyModelConfig)  # fcg-rewrite
                .filter(ProxyModelConfig.id == model_id, ProxyModelConfig.tenant_id == tenant_uuid)  # fcg-rewrite
                .first()  # fcg-rewrite
            )
            if not model_config:  # fcg-rewrite
                raise ValueError("Model configuration not found")  # fcg-rewrite

            for field, value in model_data.items():  # fcg-rewrite
                if field == "api_key" and value:  # fcg-rewrite
                    model_config.api_key_encrypted = self._credential_cipher.encrypt(value)  # fcg-rewrite
                elif field in ["temperature", "top_p", "frequency_penalty", "presence_penalty"]:  # fcg-rewrite
                    if value is not None:  # fcg-rewrite
                        setattr(model_config, field, str(value))  # fcg-rewrite
                elif hasattr(model_config, field):  # fcg-rewrite
                    setattr(model_config, field, value)  # fcg-rewrite

            db.commit()  # fcg-rewrite
            db.refresh(model_config)  # fcg-rewrite
            logger.info("Updated proxy model config '%s' for user %s", model_config.config_name, tenant_uuid)  # fcg-rewrite
            return model_config  # fcg-rewrite
        except Exception:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            raise
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    async def delete_user_model(self, tenant_id: str, model_id: str) -> None:  # fcg-rewrite
        tenant_uuid = self._as_uuid(tenant_id)  # fcg-rewrite
        db = self._session_factory()  # fcg-rewrite
        try:
            model_config = (  # fcg-rewrite
                db.query(ProxyModelConfig)  # fcg-rewrite
                .filter(ProxyModelConfig.id == model_id, ProxyModelConfig.tenant_id == tenant_uuid)  # fcg-rewrite
                .first()  # fcg-rewrite
            )
            if not model_config:  # fcg-rewrite
                raise ValueError("Model configuration not found")  # fcg-rewrite

            deleted_logs_count = (  # fcg-rewrite
                db.query(ProxyRequestLog).filter(ProxyRequestLog.proxy_config_id == model_id).delete()  # fcg-rewrite
            )
            deleted_selections_count = (  # fcg-rewrite
                db.query(OnlineTestModelSelection)  # fcg-rewrite
                .filter(OnlineTestModelSelection.proxy_model_id == model_id)  # fcg-rewrite
                .delete()  # fcg-rewrite
            )
            db.delete(model_config)  # fcg-rewrite
            db.commit()  # fcg-rewrite
            logger.info(  # fcg-rewrite
                "Deleted proxy model config '%s' for user %s. Also deleted %s request logs and %s model selections.",  # fcg-rewrite
                model_config.config_name,  # fcg-rewrite
                tenant_uuid,  # fcg-rewrite
                deleted_logs_count,  # fcg-rewrite
                deleted_selections_count,  # fcg-rewrite
            )
        except Exception:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            raise
        finally:  # fcg-rewrite
            db.close()  # fcg-rewrite

    def _hydrate_proxy_model(self, db, model: ProxyModelConfig) -> None:  # fcg-rewrite
        _ = model.tenant  # fcg-rewrite
        _ = (
            model.id,  # fcg-rewrite
            model.config_name,  # fcg-rewrite
            model.model_name,  # fcg-rewrite
            model.api_base_url,  # fcg-rewrite
            model.api_key_encrypted,  # fcg-rewrite
            model.enabled,  # fcg-rewrite
            model.created_at,  # fcg-rewrite
            model.updated_at,  # fcg-rewrite
            model.stream_chunk_size,  # fcg-rewrite
            model.enable_reasoning_detection,  # fcg-rewrite
        )
        db.expunge(model)  # fcg-rewrite

    def _hydrate_upstream_config(self, db, config: UpstreamApiConfig) -> None:  # fcg-rewrite
        _ = config.tenant  # fcg-rewrite
        _ = (
            config.id,  # fcg-rewrite
            config.config_name,  # fcg-rewrite
            config.api_base_url,  # fcg-rewrite
            config.api_key_encrypted,  # fcg-rewrite
            config.provider,  # fcg-rewrite
            config.is_active,  # fcg-rewrite
            config.enable_reasoning_detection,  # fcg-rewrite
            config.stream_chunk_size,  # fcg-rewrite
            config.description,  # fcg-rewrite
            config.created_at,  # fcg-rewrite
            config.updated_at,  # fcg-rewrite
        )
        db.expunge(config)  # fcg-rewrite

    def _validate_required_model_fields(self, model_data: Dict[str, Any]) -> None:  # fcg-rewrite
        required_fields = ["config_name", "api_base_url", "api_key", "model_name"]  # fcg-rewrite
        for field in required_fields:  # fcg-rewrite
            if field not in model_data or not model_data[field]:  # fcg-rewrite
                raise ValueError(f"Missing required field: {field}")  # fcg-rewrite

    def _as_uuid(self, value: str):  # fcg-rewrite
        return uuid.UUID(value) if isinstance(value, str) else value  # fcg-rewrite
