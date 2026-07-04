import json  # fcg-rewrite
from datetime import datetime, timezone  # fcg-rewrite
from typing import List, Optional  # fcg-rewrite

from sqlalchemy.orm import Session  # fcg-rewrite

from models.responses import (  # fcg-rewrite
    ComplianceResult,  # fcg-rewrite
    DataSecurityResult,  # fcg-rewrite
    GuardrailResponse,  # fcg-rewrite
    GuardrailResult,  # fcg-rewrite
    SecurityResult,  # fcg-rewrite
)
from services.async_logger import async_detection_logger  # fcg-rewrite
from services.enhanced_template_service import enhanced_template_service  # fcg-rewrite
from services.guardrail_outcome_service import GuardrailOutcomeService  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite
from utils.validators import clean_null_characters  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


class GuardrailAuditService:  # fcg-rewrite
    def __init__(self, db: Session, outcome_service: GuardrailOutcomeService):  # fcg-rewrite
        self.db = db  # fcg-rewrite
        self.outcome_service = outcome_service  # fcg-rewrite

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
        user_language = self.outcome_service.lookup_tenant_language(tenant_id, default="en")  # fcg-rewrite
        suggest_answer = await enhanced_template_service.get_suggest_answer(  # fcg-rewrite
            categories=[],  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            user_query=content,  # fcg-rewrite
            user_language=user_language,  # fcg-rewrite
            scanner_type="blacklist",  # fcg-rewrite
            scanner_identifier=list_name,  # fcg-rewrite
            scanner_name=list_name,  # fcg-rewrite
        )

        detection_data = {  # fcg-rewrite
            "request_id": request_id,  # fcg-rewrite
            "tenant_id": tenant_id,  # fcg-rewrite
            "application_id": application_id,  # fcg-rewrite
            "content": content,  # fcg-rewrite
            "suggest_action": "reject",  # fcg-rewrite
            "suggest_answer": suggest_answer,  # fcg-rewrite
            "hit_keywords": json.dumps(keywords),  # fcg-rewrite
            "model_response": "blacklist_hit",  # fcg-rewrite
            "ip_address": ip_address,  # fcg-rewrite
            "user_agent": user_agent,  # fcg-rewrite
            "security_risk_level": "no_risk",  # fcg-rewrite
            "security_categories": [],  # fcg-rewrite
            "compliance_risk_level": "high_risk",  # fcg-rewrite
            "compliance_categories": [list_name],  # fcg-rewrite
            "created_at": datetime.now(timezone.utc).isoformat(),  # fcg-rewrite
        }
        await async_detection_logger.log_detection(detection_data)  # fcg-rewrite

        return GuardrailResponse(  # fcg-rewrite
            id=request_id,  # fcg-rewrite
            result=GuardrailResult(  # fcg-rewrite
                compliance=ComplianceResult(risk_level="high_risk", categories=[list_name]),  # fcg-rewrite
                security=SecurityResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
                data=DataSecurityResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
            ),
            overall_risk_level="high_risk",  # fcg-rewrite
            suggest_action="reject",  # fcg-rewrite
            suggest_answer=suggest_answer,  # fcg-rewrite
        )

    async def assemble_whitelist_response(  # fcg-rewrite
        self,
        request_id: str,  # fcg-rewrite
        content: str,  # fcg-rewrite
        keywords: List[str],  # fcg-rewrite
        ip_address: Optional[str],  # fcg-rewrite
        user_agent: Optional[str],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
    ) -> GuardrailResponse:  # fcg-rewrite
        detection_data = {  # fcg-rewrite
            "request_id": request_id,  # fcg-rewrite
            "tenant_id": tenant_id,  # fcg-rewrite
            "application_id": application_id,  # fcg-rewrite
            "content": content,  # fcg-rewrite
            "suggest_action": "pass",  # fcg-rewrite
            "suggest_answer": None,  # fcg-rewrite
            "hit_keywords": json.dumps(keywords),  # fcg-rewrite
            "model_response": "whitelist_hit",  # fcg-rewrite
            "ip_address": ip_address,  # fcg-rewrite
            "user_agent": user_agent,  # fcg-rewrite
            "security_risk_level": "no_risk",  # fcg-rewrite
            "security_categories": [],  # fcg-rewrite
            "compliance_risk_level": "no_risk",  # fcg-rewrite
            "compliance_categories": [],  # fcg-rewrite
            "created_at": datetime.now(timezone.utc).isoformat(),  # fcg-rewrite
        }
        await async_detection_logger.log_detection(detection_data)  # fcg-rewrite

        return GuardrailResponse(  # fcg-rewrite
            id=request_id,  # fcg-rewrite
            result=GuardrailResult(  # fcg-rewrite
                compliance=ComplianceResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
                security=SecurityResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
                data=DataSecurityResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
            ),
            overall_risk_level="no_risk",  # fcg-rewrite
            suggest_action="pass",  # fcg-rewrite
            suggest_answer=None,  # fcg-rewrite
        )

    async def persist_detection_result(  # fcg-rewrite
        self,
        request_id: str,  # fcg-rewrite
        content: str,  # fcg-rewrite
        compliance_result: ComplianceResult,  # fcg-rewrite
        security_result: SecurityResult,  # fcg-rewrite
        suggest_action: str,  # fcg-rewrite
        suggest_answer: Optional[str],  # fcg-rewrite
        model_response: Optional[str],  # fcg-rewrite
        ip_address: Optional[str],  # fcg-rewrite
        user_agent: Optional[str],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        has_image: bool = False,  # fcg-rewrite
        image_count: int = 0,  # fcg-rewrite
        image_paths: Optional[List[str]] = None,  # fcg-rewrite
    ) -> None:  # fcg-rewrite
        detection_data = {  # fcg-rewrite
            "request_id": request_id,  # fcg-rewrite
            "tenant_id": tenant_id,  # fcg-rewrite
            "content": clean_null_characters(content) if content else content,  # fcg-rewrite
            "suggest_action": suggest_action,  # fcg-rewrite
            "suggest_answer": clean_null_characters(suggest_answer) if suggest_answer else suggest_answer,  # fcg-rewrite
            "model_response": clean_null_characters(model_response) if model_response else model_response,  # fcg-rewrite
            "ip_address": ip_address,  # fcg-rewrite
            "user_agent": clean_null_characters(user_agent) if user_agent else user_agent,  # fcg-rewrite
            "security_risk_level": security_result.risk_level,  # fcg-rewrite
            "security_categories": security_result.categories,  # fcg-rewrite
            "compliance_risk_level": compliance_result.risk_level,  # fcg-rewrite
            "compliance_categories": compliance_result.categories,  # fcg-rewrite
            "created_at": datetime.now(timezone.utc).isoformat(),  # fcg-rewrite
            "hit_keywords": None,  # fcg-rewrite
            "has_image": has_image,  # fcg-rewrite
            "image_count": image_count,  # fcg-rewrite
            "image_paths": image_paths or [],  # fcg-rewrite
        }
        await async_detection_logger.log_detection(detection_data)  # fcg-rewrite

    async def assemble_error_response(  # fcg-rewrite
        self,
        request_id: str,  # fcg-rewrite
        content: str,  # fcg-rewrite
        error: str,  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
    ) -> GuardrailResponse:  # fcg-rewrite
        detection_data = {  # fcg-rewrite
            "request_id": request_id,  # fcg-rewrite
            "tenant_id": tenant_id,  # fcg-rewrite
            "content": content,  # fcg-rewrite
            "suggest_action": "pass",  # fcg-rewrite
            "suggest_answer": None,  # fcg-rewrite
            "model_response": f"error: {error}",  # fcg-rewrite
            "security_risk_level": "no_risk",  # fcg-rewrite
            "security_categories": [],  # fcg-rewrite
            "compliance_risk_level": "no_risk",  # fcg-rewrite
            "compliance_categories": [],  # fcg-rewrite
            "created_at": datetime.now(timezone.utc).isoformat(),  # fcg-rewrite
            "hit_keywords": None,  # fcg-rewrite
            "ip_address": None,  # fcg-rewrite
            "user_agent": None,  # fcg-rewrite
        }
        await async_detection_logger.log_detection(detection_data)  # fcg-rewrite

        return GuardrailResponse(  # fcg-rewrite
            id=request_id,  # fcg-rewrite
            result=GuardrailResult(  # fcg-rewrite
                compliance=ComplianceResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
                security=SecurityResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
                data=DataSecurityResult(risk_level="no_risk", categories=[]),  # fcg-rewrite
            ),
            overall_risk_level="no_risk",  # fcg-rewrite
            suggest_action="pass",  # fcg-rewrite
            suggest_answer=None,  # fcg-rewrite
        )
