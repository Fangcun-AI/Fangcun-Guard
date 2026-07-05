"""Resolve application data-safety policies and private-model fallbacks."""

from typing import Optional, Tuple  # fcg-rewrite

from sqlalchemy import and_  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import (  # fcg-rewrite
    Application,  # fcg-rewrite
    ApplicationDataLeakagePolicy,  # fcg-rewrite
    TenantDataLeakagePolicy,  # fcg-rewrite
    UpstreamApiConfig,  # fcg-rewrite
)
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


class LeakageMitigator:  # fcg-rewrite
    """Policy reader used by gateway input, output, and streaming paths."""

    VALID_ACTIONS = {  # fcg-rewrite
        "block",  # fcg-rewrite
        "switch_private_model",  # fcg-rewrite
        "anonymize",  # fcg-rewrite
        "anonymize_restore",  # fcg-rewrite
        "pass",
    }
    RISK_LEVELS = {"high_risk", "medium_risk", "low_risk", "no_risk"}  # fcg-rewrite
    DATA_DEFAULTS = {  # fcg-rewrite
        "input": {  # fcg-rewrite
            "high_risk": "block",  # fcg-rewrite
            "medium_risk": "switch_private_model",  # fcg-rewrite
            "low_risk": "anonymize",  # fcg-rewrite
        },
        "output": {  # fcg-rewrite
            "high_risk": "block",  # fcg-rewrite
            "medium_risk": "anonymize",  # fcg-rewrite
            "low_risk": "pass",  # fcg-rewrite
        },
    }
    GENERAL_DEFAULTS = {  # fcg-rewrite
        "high_risk": "block",  # fcg-rewrite
        "medium_risk": "replace",  # fcg-rewrite
        "low_risk": "pass",  # fcg-rewrite
    }

    def __init__(self, db: Session):  # fcg-rewrite
        self.db = db  # fcg-rewrite

    def get_tenant_policy(self, tenant_id: str) -> Optional[TenantDataLeakagePolicy]:  # fcg-rewrite
        return self._load_or_create(  # fcg-rewrite
            TenantDataLeakagePolicy,  # fcg-rewrite
            TenantDataLeakagePolicy.tenant_id,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            {"tenant_id": tenant_id},  # fcg-rewrite
        )

    def get_disposal_policy(  # fcg-rewrite
        self, application_id: str  # fcg-rewrite
    ) -> Optional[ApplicationDataLeakagePolicy]:  # fcg-rewrite
        policy = self._find(  # fcg-rewrite
            ApplicationDataLeakagePolicy,  # fcg-rewrite
            ApplicationDataLeakagePolicy.application_id,  # fcg-rewrite
            application_id,  # fcg-rewrite
        )
        if policy:  # fcg-rewrite
            return policy  # fcg-rewrite
        try:
            application = self._find(Application, Application.id, application_id)  # fcg-rewrite
            if not application:  # fcg-rewrite
                logger.error(f"Application {application_id} not found")  # fcg-rewrite
                return None  # fcg-rewrite
            policy = ApplicationDataLeakagePolicy(  # fcg-rewrite
                tenant_id=application.tenant_id, application_id=application_id  # fcg-rewrite
            )
            self.db.add(policy)  # fcg-rewrite
            self.db.commit()  # fcg-rewrite
            self.db.refresh(policy)  # fcg-rewrite
            return policy  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to create application policy: {exc}", exc_info=True)  # fcg-rewrite
            self.db.rollback()  # fcg-rewrite
            return None  # fcg-rewrite

    def get_disposal_action(  # fcg-rewrite
        self, application_id: str, risk_level: str, direction: str = "input"  # fcg-rewrite
    ) -> str:  # fcg-rewrite
        if risk_level == "no_risk":  # fcg-rewrite
            return "pass"  # fcg-rewrite
        direction = "input" if direction == "input" else "output"  # fcg-rewrite
        fallback = self.DATA_DEFAULTS[direction].get(risk_level, "block")  # fcg-rewrite
        app_policy, tenant_policy = self._policy_pair(application_id)  # fcg-rewrite
        if not app_policy or not tenant_policy:  # fcg-rewrite
            return fallback  # fcg-rewrite
        return self._inherit(  # fcg-rewrite
            app_policy,  # fcg-rewrite
            tenant_policy,  # fcg-rewrite
            f"{direction}_{risk_level}_action",  # fcg-rewrite
            f"default_{direction}_{risk_level}_action",  # fcg-rewrite
            fallback,  # fcg-rewrite
        )

    def get_general_risk_action(  # fcg-rewrite
        self, application_id: str, risk_level: str, direction: str = "input"  # fcg-rewrite
    ) -> str:  # fcg-rewrite
        if risk_level == "no_risk":  # fcg-rewrite
            return "pass"  # fcg-rewrite
        direction = "input" if direction == "input" else "output"  # fcg-rewrite
        fallback = self.GENERAL_DEFAULTS.get(risk_level, "block")  # fcg-rewrite
        app_policy, tenant_policy = self._policy_pair(application_id)  # fcg-rewrite
        if not app_policy or not tenant_policy:  # fcg-rewrite
            return fallback  # fcg-rewrite
        return (  # fcg-rewrite
            getattr(app_policy, f"general_{direction}_{risk_level}_action", None)  # fcg-rewrite
            or getattr(tenant_policy, f"default_general_{direction}_{risk_level}_action", None)  # fcg-rewrite
            or getattr(tenant_policy, f"default_general_{risk_level}_action", None)  # fcg-rewrite
            or fallback  # fcg-rewrite
        )

    def get_private_model(  # fcg-rewrite
        self, application_id: str, tenant_id: str  # fcg-rewrite
    ) -> Optional[UpstreamApiConfig]:  # fcg-rewrite
        try:
            app_policy = self.get_disposal_policy(application_id)  # fcg-rewrite
            if app_policy and app_policy.private_model_id:  # fcg-rewrite
                configured = (  # fcg-rewrite
                    self.db.query(UpstreamApiConfig)  # fcg-rewrite
                    .filter(  # fcg-rewrite
                        and_(
                            UpstreamApiConfig.id == app_policy.private_model_id,  # fcg-rewrite
                            UpstreamApiConfig.is_private_model == True,  # fcg-rewrite
                            UpstreamApiConfig.is_active == True,  # fcg-rewrite
                        )
                    )
                    .first()  # fcg-rewrite
                )
                if configured:  # fcg-rewrite
                    return configured  # fcg-rewrite

            available = self._private_models_for(tenant_id)  # fcg-rewrite
            return (  # fcg-rewrite
                available.filter(UpstreamApiConfig.is_default_private_model == True).first()  # fcg-rewrite
                or available.order_by(UpstreamApiConfig.created_at.asc()).first()  # fcg-rewrite
            )
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to resolve private model: {exc}", exc_info=True)  # fcg-rewrite
            return None  # fcg-rewrite

    def validate_disposal_action(  # fcg-rewrite
        self, action: str, tenant_id: str, application_id: str  # fcg-rewrite
    ) -> Tuple[bool, str]:  # fcg-rewrite
        if action not in self.VALID_ACTIONS:  # fcg-rewrite
            choices = ", ".join(sorted(self.VALID_ACTIONS))  # fcg-rewrite
            return False, f"Invalid action '{action}'. Must be one of: {choices}"  # fcg-rewrite
        if action == "switch_private_model" and not self.get_private_model(  # fcg-rewrite
            application_id, tenant_id  # fcg-rewrite
        ):
            return False, "No private model configured. Please configure a data-private model first."  # fcg-rewrite
        return True, ""  # fcg-rewrite

    def get_policy_settings(self, application_id: str) -> dict:  # fcg-rewrite
        app_policy, tenant_policy = self._policy_pair(application_id)  # fcg-rewrite
        return {  # fcg-rewrite
            "enable_format_detection": self._inherit(  # fcg-rewrite
                app_policy,  # fcg-rewrite
                tenant_policy,  # fcg-rewrite
                "enable_format_detection",  # fcg-rewrite
                "default_enable_format_detection",  # fcg-rewrite
                True,
            ),
            "enable_smart_segmentation": self._inherit(  # fcg-rewrite
                app_policy,  # fcg-rewrite
                tenant_policy,  # fcg-rewrite
                "enable_smart_segmentation",  # fcg-rewrite
                "default_enable_smart_segmentation",  # fcg-rewrite
                True,
            ),
        }

    def update_disposal_policy(  # fcg-rewrite
        self,
        application_id: str,  # fcg-rewrite
        input_high_risk_action: Optional[str] = None,  # fcg-rewrite
        input_medium_risk_action: Optional[str] = None,  # fcg-rewrite
        input_low_risk_action: Optional[str] = None,  # fcg-rewrite
        output_high_risk_anonymize: Optional[bool] = None,  # fcg-rewrite
        output_medium_risk_anonymize: Optional[bool] = None,  # fcg-rewrite
        output_low_risk_anonymize: Optional[bool] = None,  # fcg-rewrite
        private_model_id: Optional[str] = None,  # fcg-rewrite
        enable_format_detection: Optional[bool] = None,  # fcg-rewrite
        enable_smart_segmentation: Optional[bool] = None,  # fcg-rewrite
    ) -> Tuple[bool, str, Optional[ApplicationDataLeakagePolicy]]:  # fcg-rewrite
        values = locals().copy()  # fcg-rewrite
        values.pop("self")  # fcg-rewrite
        values.pop("application_id")  # fcg-rewrite
        try:
            policy = self.get_disposal_policy(application_id)  # fcg-rewrite
            if not policy:  # fcg-rewrite
                return False, "Failed to retrieve or create policy", None  # fcg-rewrite
            for field, value in values.items():  # fcg-rewrite
                if field.startswith("input_") and field.endswith("_action"):  # fcg-rewrite
                    if value is not None and value not in self.VALID_ACTIONS:  # fcg-rewrite
                        return False, f"Invalid {field}: {value}", None  # fcg-rewrite
                if value is not None:  # fcg-rewrite
                    setattr(policy, field, value)  # fcg-rewrite
            self.db.commit()  # fcg-rewrite
            self.db.refresh(policy)  # fcg-rewrite
            return True, "Policy updated successfully", policy  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to update policy: {exc}", exc_info=True)  # fcg-rewrite
            self.db.rollback()  # fcg-rewrite
            return False, f"Error updating policy: {exc}", None  # fcg-rewrite

    def list_available_private_models(self, tenant_id: str) -> list:  # fcg-rewrite
        try:
            return (  # fcg-rewrite
                self._private_models_for(tenant_id)  # fcg-rewrite
                .order_by(  # fcg-rewrite
                    UpstreamApiConfig.is_default_private_model.desc(),  # fcg-rewrite
                    UpstreamApiConfig.created_at.asc(),  # fcg-rewrite
                )
                .all()
            )
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to list private models: {exc}", exc_info=True)  # fcg-rewrite
            return []  # fcg-rewrite

    def _policy_pair(self, application_id: str):  # fcg-rewrite
        app_policy = self.get_disposal_policy(application_id)  # fcg-rewrite
        tenant_policy = (  # fcg-rewrite
            self.get_tenant_policy(str(app_policy.tenant_id)) if app_policy else None  # fcg-rewrite
        )
        return app_policy, tenant_policy  # fcg-rewrite

    def _private_models_for(self, tenant_id: str):  # fcg-rewrite
        return self.db.query(UpstreamApiConfig).filter(  # fcg-rewrite
            and_(
                UpstreamApiConfig.tenant_id == tenant_id,  # fcg-rewrite
                UpstreamApiConfig.is_private_model == True,  # fcg-rewrite
                UpstreamApiConfig.is_active == True,  # fcg-rewrite
            )
        )

    def _find(self, model, field, value):  # fcg-rewrite
        return self.db.query(model).filter(field == value).first()  # fcg-rewrite

    def _load_or_create(self, model, field, value, create_values):  # fcg-rewrite
        existing = self._find(model, field, value)  # fcg-rewrite
        if existing:  # fcg-rewrite
            return existing  # fcg-rewrite
        try:
            record = model(**create_values)  # fcg-rewrite
            self.db.add(record)  # fcg-rewrite
            self.db.commit()  # fcg-rewrite
            self.db.refresh(record)  # fcg-rewrite
            return record  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to create {model.__name__}: {exc}", exc_info=True)  # fcg-rewrite
            self.db.rollback()  # fcg-rewrite
            return None  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _inherit(app_policy, tenant_policy, app_field: str, tenant_field: str, fallback):  # fcg-rewrite
        app_value = getattr(app_policy, app_field, None) if app_policy else None  # fcg-rewrite
        if app_value is not None:  # fcg-rewrite
            return app_value  # fcg-rewrite
        tenant_value = getattr(tenant_policy, tenant_field, None) if tenant_policy else None  # fcg-rewrite
        return fallback if tenant_value is None else tenant_value  # fcg-rewrite
