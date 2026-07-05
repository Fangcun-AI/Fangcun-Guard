from typing import Dict, Optional

from sqlalchemy.orm import Session

from database.models import RiskTypeConfig
from services.risk_policy import (
    DEFAULT_TRIGGER_LEVEL,
    RISK_SWITCH_FIELDS,
    SENSITIVITY_CONFIG_FIELDS,
    SensitivityThresholds,
    normalize_trigger_level,
    risk_switch_dict_from_record,
    risk_switches_from_record,
)
from utils.logger import setup_logger

logger = setup_logger()


class RiskConfigService:
    """Database-backed policy configuration for tenants and applications."""

    def __init__(self, db: Session):
        self.db = db

    def get_user_risk_config(
        self, tenant_id: str = None, application_id: str = None
    ) -> Optional[RiskTypeConfig]:
        try:
            lookup_field, lookup_value = self._lookup(tenant_id, application_id)
            return (
                self.db.query(RiskTypeConfig)
                .filter(lookup_field == lookup_value)
                .first()
            )
        except Exception as exc:
            logger.error(
                "Failed to get risk config for "
                f"tenant_id={tenant_id}, application_id={application_id}: {exc}"
            )
            return None

    def create_default_risk_config(
        self, tenant_id: str = None, application_id: str = None
    ) -> RiskTypeConfig:
        if not tenant_id and not application_id:
            raise ValueError("Either tenant_id or application_id must be provided")

        try:
            config_data = self._config_identity(tenant_id, application_id)
            config = RiskTypeConfig(**config_data)
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
            logger.info(
                "Created default risk config for "
                f"tenant_id={tenant_id}, application_id={application_id}"
            )
            return config
        except Exception as exc:
            logger.error(
                "Failed to create default risk config for "
                f"tenant_id={tenant_id}, application_id={application_id}: {exc}"
            )
            self.db.rollback()
            raise

    def update_risk_config(
        self,
        tenant_id: str = None,
        application_id: str = None,
        config_data: Dict = None,
    ) -> Optional[RiskTypeConfig]:
        return self._update_fields(
            tenant_id,
            application_id,
            config_data or {},
            frozenset(RISK_SWITCH_FIELDS),
            "risk config",
        )

    def get_enabled_risk_types(
        self, tenant_id: str = None, application_id: str = None
    ) -> Dict[str, bool]:
        config = self.get_user_risk_config(
            tenant_id=tenant_id, application_id=application_id
        )
        return risk_switches_from_record(config)

    def is_risk_type_enabled(
        self,
        tenant_id: str = None,
        application_id: str = None,
        risk_type: str = None,
    ) -> bool:
        return self.get_enabled_risk_types(
            tenant_id=tenant_id, application_id=application_id
        ).get(risk_type, True)

    def get_risk_config_dict(
        self, tenant_id: str = None, application_id: str = None
    ) -> Dict:
        config = self.get_user_risk_config(
            tenant_id=tenant_id, application_id=application_id
        )
        return risk_switch_dict_from_record(config)

    def update_sensitivity_thresholds(
        self,
        tenant_id: str = None,
        application_id: str = None,
        threshold_data: Dict = None,
    ) -> Optional[RiskTypeConfig]:
        return self._update_fields(
            tenant_id,
            application_id,
            threshold_data or {},
            SENSITIVITY_CONFIG_FIELDS,
            "sensitivity thresholds",
        )

    def get_sensitivity_threshold_dict(
        self, tenant_id: str = None, application_id: str = None
    ) -> Dict:
        config = self.get_user_risk_config(
            tenant_id=tenant_id, application_id=application_id
        )
        return SensitivityThresholds.from_record(config).as_config_dict(
            getattr(config, "sensitivity_trigger_level", None)
        )

    def get_sensitivity_thresholds(
        self, tenant_id: str = None, application_id: str = None
    ) -> Dict[str, float]:
        config = self.get_user_risk_config(
            tenant_id=tenant_id, application_id=application_id
        )
        return SensitivityThresholds.from_record(config).as_dict()

    def get_sensitivity_trigger_level(
        self, tenant_id: str = None, application_id: str = None
    ) -> str:
        config = self.get_user_risk_config(
            tenant_id=tenant_id, application_id=application_id
        )
        return normalize_trigger_level(
            getattr(config, "sensitivity_trigger_level", DEFAULT_TRIGGER_LEVEL)
        )

    def _update_fields(
        self,
        tenant_id: str,
        application_id: str,
        values: Dict,
        allowed_fields: frozenset,
        description: str,
    ) -> Optional[RiskTypeConfig]:
        try:
            config = self.get_user_risk_config(
                tenant_id=tenant_id, application_id=application_id
            )
            if not config:
                config = self.create_default_risk_config(
                    tenant_id=tenant_id, application_id=application_id
                )

            for field, value in values.items():
                if field in allowed_fields:
                    setattr(config, field, value)

            self.db.commit()
            self.db.refresh(config)
            logger.info(
                f"Updated {description} for tenant_id={tenant_id}, "
                f"application_id={application_id}"
            )
            return config
        except Exception as exc:
            logger.error(
                f"Failed to update {description} for tenant_id={tenant_id}, "
                f"application_id={application_id}: {exc}"
            )
            self.db.rollback()
            return None

    def _config_identity(self, tenant_id: str, application_id: str) -> Dict:
        identity = {}
        if application_id:
            from database.models import Application

            identity["application_id"] = application_id
            application = (
                self.db.query(Application)
                .filter(Application.id == application_id)
                .first()
            )
            if application:
                identity["tenant_id"] = application.tenant_id
        if tenant_id:
            identity["tenant_id"] = tenant_id
        return identity

    @staticmethod
    def _lookup(tenant_id: str, application_id: str):
        if application_id:
            return RiskTypeConfig.application_id, application_id
        if tenant_id:
            return RiskTypeConfig.tenant_id, tenant_id
        raise ValueError("Either tenant_id or application_id must be provided")
