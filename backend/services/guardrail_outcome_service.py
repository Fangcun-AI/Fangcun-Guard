from typing import List, Optional, Tuple  # fcg-rewrite

from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import Tenant  # fcg-rewrite
from models.responses import ComplianceResult, DataSecurityResult, SecurityResult  # fcg-rewrite
from services.enhanced_template_service import enhanced_template_service  # fcg-rewrite
from services.risk_config_service import RiskConfigService  # fcg-rewrite
from services.risk_policy import (  # fcg-rewrite
    CATEGORY_LABELS,  # fcg-rewrite
    CATEGORY_RISK_LEVELS,  # fcg-rewrite
    highest_risk_level,  # fcg-rewrite
    parse_verdict_categories,  # fcg-rewrite
    partition_categories,  # fcg-rewrite
)
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

RISK_LEVEL_MAPPING = CATEGORY_RISK_LEVELS  # fcg-rewrite
CATEGORY_NAMES = CATEGORY_LABELS  # fcg-rewrite


class GuardrailOutcomeService:  # fcg-rewrite
    def __init__(self, db: Session, risk_config_service: RiskConfigService):  # fcg-rewrite
        self.db = db  # fcg-rewrite
        self.risk_config_service = risk_config_service  # fcg-rewrite

    def lookup_tenant_language(self, tenant_id: Optional[str], default: str = "en") -> str:  # fcg-rewrite
        if not tenant_id:  # fcg-rewrite
            return default  # fcg-rewrite

        try:
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()  # fcg-rewrite
            if tenant and tenant.language:  # fcg-rewrite
                return tenant.language  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.warning(f"Failed to get user language for tenant {tenant_id}: {exc}")  # fcg-rewrite
        return default  # fcg-rewrite

    def parse_model_verdict(  # fcg-rewrite
        self,
        response: str,  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
    ) -> Tuple[ComplianceResult, SecurityResult]:  # fcg-rewrite
        categories = parse_verdict_categories(response)  # fcg-rewrite
        if not categories:  # fcg-rewrite
            return (  # fcg-rewrite
                ComplianceResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
                SecurityResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
            )

        enabled_categories = []  # fcg-rewrite
        for category in categories:  # fcg-rewrite
            if not tenant_id or self.risk_config_service.is_risk_type_enabled(  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                risk_type=category,  # fcg-rewrite
            ):
                enabled_categories.append(category)  # fcg-rewrite

        if not enabled_categories:  # fcg-rewrite
            logger.info(  # fcg-rewrite
                f"All risk types {categories} are disabled for tenant {tenant_id}, treating as safe"  # fcg-rewrite
            )
            return (  # fcg-rewrite
                ComplianceResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
                SecurityResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
            )

        verdict = partition_categories(enabled_categories)  # fcg-rewrite

        return (  # fcg-rewrite
            ComplianceResult(  # fcg-rewrite
                risk_level=verdict.compliance_level,  # fcg-rewrite
                categories=list(verdict.compliance_categories),  # fcg-rewrite
            ),
            SecurityResult(  # fcg-rewrite
                risk_level=verdict.security_level,  # fcg-rewrite
                categories=list(verdict.security_categories),  # fcg-rewrite
            ),
        )

    async def craft_suggest_answer(  # fcg-rewrite
        self,
        categories: List[str],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        user_query: Optional[str] = None,  # fcg-rewrite
        matched_scanners: Optional[list] = None,  # fcg-rewrite
    ) -> str:  # fcg-rewrite
        user_language = self.lookup_tenant_language(tenant_id)  # fcg-rewrite

        scanner_type = None  # fcg-rewrite
        scanner_identifier = None  # fcg-rewrite
        scanner_name = None  # fcg-rewrite
        match_details = None  # fcg-rewrite

        if matched_scanners:  # fcg-rewrite
            first_scanner = matched_scanners[0]  # fcg-rewrite
            scanner_type = "official_scanner"  # fcg-rewrite
            scanner_identifier = first_scanner.scanner_tag  # fcg-rewrite
            scanner_name = first_scanner.scanner_name  # fcg-rewrite
            match_details = getattr(first_scanner, "match_details", None)  # fcg-rewrite
            logger.info(  # fcg-rewrite
                "Using scanner info for answer matching: "  # fcg-rewrite
                f"type={scanner_type}, identifier={scanner_identifier}, "  # fcg-rewrite
                f"name={scanner_name}, details={match_details}"  # fcg-rewrite
            )
        elif categories:  # fcg-rewrite
            scanner_name = categories[0]  # fcg-rewrite
            logger.debug(  # fcg-rewrite
                f"No matched_scanners provided, using first category as scanner_name: {scanner_name}"  # fcg-rewrite
            )

        return await enhanced_template_service.get_suggest_answer(  # fcg-rewrite
            categories,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            user_query=user_query,  # fcg-rewrite
            user_language=user_language,  # fcg-rewrite
            scanner_type=scanner_type,  # fcg-rewrite
            scanner_identifier=scanner_identifier,  # fcg-rewrite
            scanner_name=scanner_name,  # fcg-rewrite
            match_details=match_details,  # fcg-rewrite
        )

    async def finalize_guardrail_outcome(  # fcg-rewrite
        self,
        compliance_result: ComplianceResult,  # fcg-rewrite
        security_result: SecurityResult,  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        user_query: Optional[str] = None,  # fcg-rewrite
        data_result: Optional[DataSecurityResult] = None,  # fcg-rewrite
        anonymized_text: Optional[str] = None,  # fcg-rewrite
        matched_scanners: Optional[list] = None,  # fcg-rewrite
    ) -> Tuple[str, str, Optional[str]]:  # fcg-rewrite
        overall_risk_level = highest_risk_level(  # fcg-rewrite
            [
                compliance_result.risk_level,  # fcg-rewrite
                security_result.risk_level,  # fcg-rewrite
                data_result.risk_level if data_result else "no_risk",  # fcg-rewrite
            ]
        )

        risk_categories: List[str] = []  # fcg-rewrite
        if compliance_result.risk_level != "no_risk":  # fcg-rewrite
            risk_categories.extend(compliance_result.categories)  # fcg-rewrite
        if security_result.risk_level != "no_risk":  # fcg-rewrite
            risk_categories.extend(security_result.categories)  # fcg-rewrite
        if data_result and data_result.risk_level != "no_risk":  # fcg-rewrite
            risk_categories.extend(data_result.categories)  # fcg-rewrite

        if overall_risk_level == "no_risk":  # fcg-rewrite
            return overall_risk_level, "pass", None  # fcg-rewrite

        if overall_risk_level == "high_risk":  # fcg-rewrite
            suggest_answer = await self.craft_suggest_answer(  # fcg-rewrite
                risk_categories, tenant_id, application_id, user_query, matched_scanners  # fcg-rewrite
            )
            return overall_risk_level, "reject", suggest_answer  # fcg-rewrite

        if anonymized_text and data_result and data_result.risk_level != "no_risk":  # fcg-rewrite
            return overall_risk_level, "replace", anonymized_text  # fcg-rewrite

        suggest_answer = await self.craft_suggest_answer(  # fcg-rewrite
            risk_categories, tenant_id, application_id, user_query, matched_scanners  # fcg-rewrite
        )
        return overall_risk_level, "replace", suggest_answer  # fcg-rewrite
