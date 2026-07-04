import json  # fcg-rewrite
from datetime import datetime, timezone  # fcg-rewrite
from typing import List, Optional, Tuple  # fcg-rewrite

from database.connection import get_db_session  # fcg-rewrite
from models.responses import (  # fcg-rewrite
    ComplianceResult,  # fcg-rewrite
    DataSecurityResult,  # fcg-rewrite
    GuardrailResponse,  # fcg-rewrite
    GuardrailResult,  # fcg-rewrite
    HallucinationResult,  # fcg-rewrite
    SecurityResult,  # fcg-rewrite
)
from services.async_logger import async_detection_logger  # fcg-rewrite
from services.risk_config_cache import risk_config_cache  # fcg-rewrite
from services.risk_policy import (  # fcg-rewrite
    CATEGORY_LABELS,  # fcg-rewrite
    CATEGORY_RISK_LEVELS,  # fcg-rewrite
    SensitivityThresholds,  # fcg-rewrite
    highest_risk_level,  # fcg-rewrite
    parse_verdict_categories,  # fcg-rewrite
    partition_categories,  # fcg-rewrite
)
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

RISK_LEVEL_MAPPING = CATEGORY_RISK_LEVELS  # fcg-rewrite
CATEGORY_NAMES = CATEGORY_LABELS  # fcg-rewrite


class DetectionOutcomeCoordinator:  # fcg-rewrite
    """Encapsulates verdict parsing, answer selection, and response assembly."""

    @staticmethod  # fcg-rewrite
    def _tenant_language(tenant_id: Optional[str], default: Optional[str] = "en") -> Optional[str]:  # fcg-rewrite
        if not tenant_id:  # fcg-rewrite
            return default  # fcg-rewrite
        try:
            from database.models import Tenant  # fcg-rewrite

            db = get_db_session()  # fcg-rewrite
            try:
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()  # fcg-rewrite
                return tenant.language if tenant and tenant.language else default  # fcg-rewrite
            finally:  # fcg-rewrite
                db.close()  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.warning(f"Failed to get user language for tenant {tenant_id}: {exc}")  # fcg-rewrite
            return default  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _list_hit_data(  # fcg-rewrite
        request_id: str,  # fcg-rewrite
        content: str,  # fcg-rewrite
        keywords: List[str],  # fcg-rewrite
        ip_address: Optional[str],  # fcg-rewrite
        user_agent: Optional[str],  # fcg-rewrite
        tenant_id: Optional[str],  # fcg-rewrite
        application_id: Optional[str],  # fcg-rewrite
        *,
        list_name: Optional[str] = None,  # fcg-rewrite
        suggest_answer: Optional[str] = None,  # fcg-rewrite
    ) -> dict:  # fcg-rewrite
        blocked = list_name is not None  # fcg-rewrite
        return {  # fcg-rewrite
            "request_id": request_id,  # fcg-rewrite
            "tenant_id": tenant_id,  # fcg-rewrite
            "application_id": application_id,  # fcg-rewrite
            "content": content,  # fcg-rewrite
            "suggest_action": "reject" if blocked else "pass",  # fcg-rewrite
            "suggest_answer": suggest_answer,  # fcg-rewrite
            "hit_keywords": json.dumps(keywords),  # fcg-rewrite
            "model_response": "blacklist_hit" if blocked else "whitelist_hit",  # fcg-rewrite
            "ip_address": ip_address,  # fcg-rewrite
            "user_agent": user_agent,  # fcg-rewrite
            "security_risk_level": "no_risk",  # fcg-rewrite
            "security_categories": [],  # fcg-rewrite
            "compliance_risk_level": "high_risk" if blocked else "no_risk",  # fcg-rewrite
            "compliance_categories": [list_name] if blocked else [],  # fcg-rewrite
            "data_risk_level": "no_risk",  # fcg-rewrite
            "data_categories": [],  # fcg-rewrite
            "created_at": datetime.now(timezone.utc).isoformat(),  # fcg-rewrite
        }

    @staticmethod  # fcg-rewrite
    def _list_hit_response(request_id: str, *, list_name: Optional[str] = None, suggest_answer: Optional[str] = None):  # fcg-rewrite
        blocked = list_name is not None  # fcg-rewrite
        return GuardrailResponse(  # fcg-rewrite
            id=request_id,  # fcg-rewrite
            result=GuardrailResult(  # fcg-rewrite
                compliance=ComplianceResult(risk_level="high_risk" if blocked else "no_risk", categories=[list_name] if blocked else []),  # fcg-rewrite
                security=SecurityResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
                data=DataSecurityResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
            ),
            overall_risk_level="high_risk" if blocked else "no_risk",  # fcg-rewrite
            suggest_action="reject" if blocked else "pass",  # fcg-rewrite
            suggest_answer=suggest_answer,  # fcg-rewrite
        )

    async def parse_model_verdict(  # fcg-rewrite
        self, response: str, tenant_id: Optional[str] = None  # fcg-rewrite
    ) -> Tuple[ComplianceResult, SecurityResult]:  # fcg-rewrite
        categories = parse_verdict_categories(response)  # fcg-rewrite
        enabled_categories = []  # fcg-rewrite
        for category in categories:  # fcg-rewrite
            if not tenant_id or await risk_config_cache.is_risk_type_enabled(  # fcg-rewrite
                tenant_id=tenant_id, risk_type=category  # fcg-rewrite
            ):
                enabled_categories.append(category)  # fcg-rewrite

        if categories and not enabled_categories:  # fcg-rewrite
            logger.info(f"All risk types {categories} are disabled for user {tenant_id}")  # fcg-rewrite
        return self._results_for_categories(enabled_categories)  # fcg-rewrite

    async def parse_model_verdict_with_sensitivity(  # fcg-rewrite
        self,
        response: str,  # fcg-rewrite
        sensitivity_score: Optional[float],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        model_sensitivity_trigger_level: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
    ) -> Tuple[ComplianceResult, SecurityResult]:  # fcg-rewrite
        categories = parse_verdict_categories(response)  # fcg-rewrite
        if not categories:  # fcg-rewrite
            return self._safe_results()  # fcg-rewrite

        enabled_categories = []  # fcg-rewrite
        for category in categories:  # fcg-rewrite
            is_enabled = await risk_config_cache.is_risk_type_enabled(  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                application_id=application_id,  # fcg-rewrite
                risk_type=category,  # fcg-rewrite
            )
            if is_enabled:  # fcg-rewrite
                enabled_categories.append(category)  # fcg-rewrite

        if not enabled_categories:  # fcg-rewrite
            cache_key = application_id if application_id else tenant_id  # fcg-rewrite
            logger.info(  # fcg-rewrite
                f"All risk types {categories} are disabled for application/user {cache_key}, treating as safe"  # fcg-rewrite
            )
            return self._safe_results()  # fcg-rewrite

        if sensitivity_score is not None and (tenant_id or application_id):  # fcg-rewrite
            if not await self.meets_sensitivity_threshold(  # fcg-rewrite
                sensitivity_score, tenant_id, application_id  # fcg-rewrite
            ):
                logger.info(  # fcg-rewrite
                    f"Sensitivity score {sensitivity_score} below current threshold for {enabled_categories}, treating as safe"  # fcg-rewrite
                )
                return self._safe_results()  # fcg-rewrite

        return self._results_for_categories(enabled_categories)  # fcg-rewrite

    async def execute_data_security_check(  # fcg-rewrite
        self,
        text: str,  # fcg-rewrite
        tenant_id: Optional[str],  # fcg-rewrite
        direction: str = "input",  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
    ) -> Tuple[DataSecurityResult, Optional[str]]:  # fcg-rewrite
        logger.info(  # fcg-rewrite
            f"_execute_data_security_check called for user {tenant_id}, application {application_id}, direction {direction}"  # fcg-rewrite
        )
        if not tenant_id:  # fcg-rewrite
            logger.info("No tenant_id, returning safe")  # fcg-rewrite
            return DataSecurityResult(risk_level="no_risk", categories=[]), None  # fcg-rewrite

        try:
            db = get_db_session()  # fcg-rewrite
            try:
                from services.data_security_service import PrivacyEngine  # fcg-rewrite

                service = PrivacyEngine(db)  # fcg-rewrite
                logger.info(f"Calling detect_sensitive_data for text: {text[:50]}...")  # fcg-rewrite
                result = await service.detect_sensitive_data(  # fcg-rewrite
                    text, tenant_id, direction, application_id=application_id  # fcg-rewrite
                )
                logger.info(f"Data security detection result: {result}")  # fcg-rewrite

                anonymized_text = (  # fcg-rewrite
                    result.get("anonymized_text") if result["risk_level"] != "no_risk" else None  # fcg-rewrite
                )
                detected_entities = (  # fcg-rewrite
                    result.get("detected_entities", []) if result["risk_level"] != "no_risk" else []  # fcg-rewrite
                )
                restore_mapping = (  # fcg-rewrite
                    result.get("restore_mapping") if result["risk_level"] != "no_risk" else None  # fcg-rewrite
                )
                data_result = DataSecurityResult(  # fcg-rewrite
                    risk_level=result["risk_level"],  # fcg-rewrite
                    categories=result["categories"],  # fcg-rewrite
                    detected_entities=detected_entities,  # fcg-rewrite
                    anonymized_text=anonymized_text,  # fcg-rewrite
                    restore_mapping=restore_mapping,  # fcg-rewrite
                )
                return data_result, anonymized_text  # fcg-rewrite
            finally:  # fcg-rewrite
                db.close()  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Data security check error: {exc}", exc_info=True)  # fcg-rewrite
            return DataSecurityResult(risk_level="no_risk", categories=[]), None  # fcg-rewrite

    async def finalize_guardrail_outcome_with_data(  # fcg-rewrite
        self,
        compliance_result: ComplianceResult,  # fcg-rewrite
        security_result: SecurityResult,  # fcg-rewrite
        data_result: DataSecurityResult,  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        user_query: Optional[str] = None,  # fcg-rewrite
        data_anonymized_text: Optional[str] = None,  # fcg-rewrite
        matched_scanners: Optional[list] = None,  # fcg-rewrite
    ) -> Tuple[str, str, Optional[str]]:  # fcg-rewrite
        all_categories = []  # fcg-rewrite
        if compliance_result.risk_level != "no_risk":  # fcg-rewrite
            all_categories.extend(compliance_result.categories)  # fcg-rewrite
        if security_result.risk_level != "no_risk":  # fcg-rewrite
            all_categories.extend(security_result.categories)  # fcg-rewrite

        general_risk_level = highest_risk_level(  # fcg-rewrite
            [compliance_result.risk_level, security_result.risk_level]  # fcg-rewrite
        )
        overall_risk_level = highest_risk_level(  # fcg-rewrite
            [general_risk_level, data_result.risk_level]  # fcg-rewrite
        )

        if overall_risk_level == "no_risk":  # fcg-rewrite
            return overall_risk_level, "pass", None  # fcg-rewrite

        suggest_answer = None  # fcg-rewrite
        if general_risk_level != "no_risk":  # fcg-rewrite
            suggest_answer = await self.craft_suggest_answer(  # fcg-rewrite
                all_categories, tenant_id, application_id, user_query, matched_scanners  # fcg-rewrite
            )
            logger.info(f"Using template answer for general risk: {general_risk_level}")  # fcg-rewrite
        elif data_result.risk_level != "no_risk":  # fcg-rewrite
            from services.enhanced_template_service import enhanced_template_service  # fcg-rewrite

            entity_type_names = []  # fcg-rewrite
            if data_result.detected_entities:  # fcg-rewrite
                seen_names = set()  # fcg-rewrite
                for entity in data_result.detected_entities:  # fcg-rewrite
                    name = entity.get("entity_type_name") or entity.get("entity_type", "")  # fcg-rewrite
                    if name and name not in seen_names:  # fcg-rewrite
                        entity_type_names.append(name)  # fcg-rewrite
                        seen_names.add(name)  # fcg-rewrite
            if not entity_type_names:  # fcg-rewrite
                entity_type_names = data_result.categories if data_result.categories else []  # fcg-rewrite

            suggest_answer = await enhanced_template_service.get_data_leakage_answer(  # fcg-rewrite
                entity_type_names, self._tenant_language(tenant_id), application_id  # fcg-rewrite
            )
            logger.info(  # fcg-rewrite
                f"Using data leakage template for DLP risk: {data_result.risk_level}, entity_type_names={entity_type_names}"  # fcg-rewrite
            )

        if general_risk_level == "high_risk":  # fcg-rewrite
            return overall_risk_level, "reject", suggest_answer  # fcg-rewrite
        if general_risk_level == "medium_risk":  # fcg-rewrite
            return overall_risk_level, "replace", suggest_answer  # fcg-rewrite
        if general_risk_level == "low_risk":  # fcg-rewrite
            return overall_risk_level, "pass", None  # fcg-rewrite
        return overall_risk_level, "pass", suggest_answer  # fcg-rewrite

    async def finalize_guardrail_outcome(  # fcg-rewrite
        self,
        compliance_result: ComplianceResult,  # fcg-rewrite
        security_result: SecurityResult,  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        user_query: Optional[str] = None,  # fcg-rewrite
        matched_scanners: Optional[list] = None,  # fcg-rewrite
    ) -> Tuple[str, str, Optional[str]]:  # fcg-rewrite
        risk_levels = []  # fcg-rewrite
        risk_categories = []  # fcg-rewrite

        if compliance_result.risk_level != "no_risk":  # fcg-rewrite
            risk_levels.append(compliance_result.risk_level)  # fcg-rewrite
            risk_categories.extend(compliance_result.categories)  # fcg-rewrite
        if security_result.risk_level != "no_risk":  # fcg-rewrite
            risk_levels.append(security_result.risk_level)  # fcg-rewrite
            risk_categories.extend(security_result.categories)  # fcg-rewrite

        overall_risk_level = highest_risk_level(risk_levels)  # fcg-rewrite
        if overall_risk_level == "no_risk":  # fcg-rewrite
            return overall_risk_level, "pass", None  # fcg-rewrite

        suggest_answer = await self.craft_suggest_answer(  # fcg-rewrite
            risk_categories, tenant_id, application_id, user_query, matched_scanners  # fcg-rewrite
        )
        if overall_risk_level == "high_risk":  # fcg-rewrite
            return overall_risk_level, "reject", suggest_answer  # fcg-rewrite
        if overall_risk_level == "medium_risk":  # fcg-rewrite
            return overall_risk_level, "replace", suggest_answer  # fcg-rewrite
        return overall_risk_level, "replace", suggest_answer  # fcg-rewrite

    async def craft_suggest_answer(  # fcg-rewrite
        self,
        categories: List[str],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        user_query: Optional[str] = None,  # fcg-rewrite
        matched_scanners: Optional[list] = None,  # fcg-rewrite
    ) -> str:  # fcg-rewrite
        from services.enhanced_template_service import enhanced_template_service  # fcg-rewrite
        scanner_type = None  # fcg-rewrite
        scanner_identifier = None  # fcg-rewrite
        scanner_name = None  # fcg-rewrite
        if matched_scanners and len(matched_scanners) > 0:  # fcg-rewrite
            first_scanner = matched_scanners[0]  # fcg-rewrite
            scanner_type = "official_scanner"  # fcg-rewrite
            scanner_identifier = first_scanner.scanner_tag  # fcg-rewrite
            scanner_name = first_scanner.scanner_name  # fcg-rewrite
            logger.info(  # fcg-rewrite
                f"Using scanner info for answer matching: type={scanner_type}, identifier={scanner_identifier}, name={scanner_name}"  # fcg-rewrite
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
            user_language=self._tenant_language(tenant_id, default=None),  # fcg-rewrite
            scanner_type=scanner_type,  # fcg-rewrite
            scanner_identifier=scanner_identifier,  # fcg-rewrite
            scanner_name=scanner_name,  # fcg-rewrite
        )

    async def load_sensitivity_trigger_level(  # fcg-rewrite
        self, tenant_id: str = None, application_id: str = None  # fcg-rewrite
    ) -> str:  # fcg-rewrite
        try:
            trigger_level = await risk_config_cache.get_sensitivity_trigger_level(  # fcg-rewrite
                tenant_id=tenant_id, application_id=application_id  # fcg-rewrite
            )
            return trigger_level if trigger_level else "medium"  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            cache_key = application_id if application_id else tenant_id  # fcg-rewrite
            logger.warning(  # fcg-rewrite
                f"Failed to get sensitivity trigger level for {cache_key}: {exc}"  # fcg-rewrite
            )
            return "medium"  # fcg-rewrite

    async def meets_sensitivity_threshold(  # fcg-rewrite
        self, sensitivity_score: float, tenant_id: str = None, application_id: str = None  # fcg-rewrite
    ) -> bool:  # fcg-rewrite
        try:
            current_level = await self.load_sensitivity_trigger_level(tenant_id, application_id)  # fcg-rewrite
            thresholds = await risk_config_cache.get_sensitivity_thresholds(  # fcg-rewrite
                tenant_id=tenant_id, application_id=application_id  # fcg-rewrite
            )
            threshold = SensitivityThresholds.from_mapping(thresholds).threshold_for(  # fcg-rewrite
                current_level  # fcg-rewrite
            )
            return sensitivity_score >= threshold  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            cache_key = application_id if application_id else tenant_id  # fcg-rewrite
            logger.warning(f"Failed to check sensitivity trigger for {cache_key}: {exc}")  # fcg-rewrite
            return sensitivity_score >= 0.60  # fcg-rewrite

    async def assemble_blacklist_response(  # fcg-rewrite
        self,
        request_id: str,  # fcg-rewrite
        content: str,  # fcg-rewrite
        list_name: str,  # fcg-rewrite
        keywords: List[str],  # fcg-rewrite
        ip_address: Optional[str],  # fcg-rewrite
        user_agent: Optional[str],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
    ) -> GuardrailResponse:  # fcg-rewrite
        from services.enhanced_template_service import enhanced_template_service  # fcg-rewrite

        suggest_answer = await enhanced_template_service.get_suggest_answer(  # fcg-rewrite
            categories=[],  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            user_query=content,  # fcg-rewrite
            user_language=self._tenant_language(tenant_id),  # fcg-rewrite
            scanner_type="blacklist",  # fcg-rewrite
            scanner_identifier=list_name,  # fcg-rewrite
            scanner_name=list_name,  # fcg-rewrite
        )
        await async_detection_logger.log_detection(  # fcg-rewrite
            self._list_hit_data(  # fcg-rewrite
                request_id,  # fcg-rewrite
                content,  # fcg-rewrite
                keywords,  # fcg-rewrite
                ip_address,  # fcg-rewrite
                user_agent,  # fcg-rewrite
                tenant_id,  # fcg-rewrite
                application_id,  # fcg-rewrite
                list_name=list_name,  # fcg-rewrite
                suggest_answer=suggest_answer,  # fcg-rewrite
            )
        )
        return self._list_hit_response(request_id, list_name=list_name, suggest_answer=suggest_answer)  # fcg-rewrite

    async def assemble_whitelist_response(  # fcg-rewrite
        self,
        request_id: str,  # fcg-rewrite
        content: str,  # fcg-rewrite
        list_name: str,  # fcg-rewrite
        keywords: List[str],  # fcg-rewrite
        ip_address: Optional[str],  # fcg-rewrite
        user_agent: Optional[str],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
    ) -> GuardrailResponse:  # fcg-rewrite
        await async_detection_logger.log_detection(  # fcg-rewrite
            self._list_hit_data(request_id, content, keywords, ip_address, user_agent, tenant_id, application_id)  # fcg-rewrite
        )
        return self._list_hit_response(request_id)  # fcg-rewrite

    async def persist_detection_result(  # fcg-rewrite
        self,
        request_id: str,  # fcg-rewrite
        content: str,  # fcg-rewrite
        compliance_result: ComplianceResult,  # fcg-rewrite
        security_result: SecurityResult,  # fcg-rewrite
        data_result: DataSecurityResult,  # fcg-rewrite
        suggest_action: str,  # fcg-rewrite
        suggest_answer: Optional[str],  # fcg-rewrite
        model_response: str,  # fcg-rewrite
        ip_address: Optional[str],  # fcg-rewrite
        user_agent: Optional[str],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        sensitivity_score: Optional[float] = None,  # fcg-rewrite
        has_image: bool = False,  # fcg-rewrite
        image_count: int = 0,  # fcg-rewrite
        image_paths: List[str] = None,  # fcg-rewrite
        matched_scanner_tags: List[str] = None,  # fcg-rewrite
        agent_safety_result=None,  # fcg-rewrite
        hallucination_result: Optional[HallucinationResult] = None,  # fcg-rewrite
    ):
        from utils.validators import clean_null_characters  # fcg-rewrite

        detection_data = {  # fcg-rewrite
            "request_id": request_id,  # fcg-rewrite
            "tenant_id": tenant_id,  # fcg-rewrite
            "application_id": application_id,  # fcg-rewrite
            "content": clean_null_characters(content) if content else content,  # fcg-rewrite
            "suggest_action": suggest_action,  # fcg-rewrite
            "suggest_answer": clean_null_characters(suggest_answer)  # fcg-rewrite
            if suggest_answer  # fcg-rewrite
            else suggest_answer,  # fcg-rewrite
            "model_response": clean_null_characters(model_response)  # fcg-rewrite
            if model_response  # fcg-rewrite
            else model_response,  # fcg-rewrite
            "ip_address": ip_address,  # fcg-rewrite
            "user_agent": clean_null_characters(user_agent) if user_agent else user_agent,  # fcg-rewrite
            "security_risk_level": security_result.risk_level,  # fcg-rewrite
            "security_categories": security_result.categories,  # fcg-rewrite
            "compliance_risk_level": compliance_result.risk_level,  # fcg-rewrite
            "compliance_categories": compliance_result.categories,  # fcg-rewrite
            "data_risk_level": data_result.risk_level,  # fcg-rewrite
            "data_categories": data_result.categories,  # fcg-rewrite
            "sensitivity_score": sensitivity_score,  # fcg-rewrite
            "created_at": datetime.now(timezone.utc).isoformat(),  # fcg-rewrite
            "hit_keywords": None,  # fcg-rewrite
            "has_image": has_image,  # fcg-rewrite
            "image_count": image_count,  # fcg-rewrite
            "image_paths": image_paths or [],  # fcg-rewrite
            "matched_scanner_tags": matched_scanner_tags or [],  # fcg-rewrite
            "agent_safety_risk_level": agent_safety_result.risk_level  # fcg-rewrite
            if agent_safety_result  # fcg-rewrite
            else "no_risk",  # fcg-rewrite
            "agent_safety_categories": agent_safety_result.categories  # fcg-rewrite
            if agent_safety_result  # fcg-rewrite
            else [],  # fcg-rewrite
            "hallucination_risk_level": hallucination_result.risk_level  # fcg-rewrite
            if hallucination_result  # fcg-rewrite
            else "no_risk",  # fcg-rewrite
            "hallucination_categories": hallucination_result.categories  # fcg-rewrite
            if hallucination_result  # fcg-rewrite
            else [],  # fcg-rewrite
            "groundedness_score": hallucination_result.groundedness_score  # fcg-rewrite
            if hallucination_result  # fcg-rewrite
            else None,  # fcg-rewrite
            "consistency_score": hallucination_result.consistency_score  # fcg-rewrite
            if hallucination_result  # fcg-rewrite
            else None,  # fcg-rewrite
        }
        await async_detection_logger.log_detection(detection_data)  # fcg-rewrite

    async def assemble_error_response(  # fcg-rewrite
        self,
        request_id: str,  # fcg-rewrite
        content: str,  # fcg-rewrite
        error: str,  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
    ) -> GuardrailResponse:  # fcg-rewrite
        detection_data = {  # fcg-rewrite
            "request_id": request_id,  # fcg-rewrite
            "tenant_id": tenant_id,  # fcg-rewrite
            "application_id": application_id,  # fcg-rewrite
            "content": content,  # fcg-rewrite
            "suggest_action": "block",  # fcg-rewrite
            "suggest_answer": None,  # fcg-rewrite
            "model_response": f"error: {error}",  # fcg-rewrite
            "security_risk_level": "error",  # fcg-rewrite
            "security_categories": ["detection_system_error"],  # fcg-rewrite
            "compliance_risk_level": "error",  # fcg-rewrite
            "compliance_categories": [],  # fcg-rewrite
            "data_risk_level": "error",  # fcg-rewrite
            "data_categories": [],  # fcg-rewrite
            "created_at": datetime.now(timezone.utc).isoformat(),  # fcg-rewrite
            "hit_keywords": None,  # fcg-rewrite
            "ip_address": None,  # fcg-rewrite
            "user_agent": None,  # fcg-rewrite
        }
        await async_detection_logger.log_detection(detection_data)  # fcg-rewrite

        logger.warning(  # fcg-rewrite
            f"Fail-close: blocking request {request_id} due to detection error: {error}"  # fcg-rewrite
        )
        return GuardrailResponse(  # fcg-rewrite
            id=request_id,  # fcg-rewrite
            result=GuardrailResult(  # fcg-rewrite
                compliance=ComplianceResult(risk_level="error", categories=[]),  # fcg-rewrite
                security=SecurityResult(  # fcg-rewrite
                    risk_level="error", categories=["detection_system_error"]  # fcg-rewrite
                ),
                data=DataSecurityResult(risk_level="error", categories=[]),  # fcg-rewrite
            ),
            overall_risk_level="error",  # fcg-rewrite
            suggest_action="block",  # fcg-rewrite
            suggest_answer="Security detection system temporarily unavailable. Request blocked for safety.",  # fcg-rewrite
        )

    def _safe_results(self) -> Tuple[ComplianceResult, SecurityResult]:  # fcg-rewrite
        return (  # fcg-rewrite
            ComplianceResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
            SecurityResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
        )

    def _results_for_categories(  # fcg-rewrite
        self, categories: List[str]  # fcg-rewrite
    ) -> Tuple[ComplianceResult, SecurityResult]:  # fcg-rewrite
        verdict = partition_categories(categories)  # fcg-rewrite
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
