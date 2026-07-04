import uuid  # fcg-rewrite
from typing import List, Tuple, Optional  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite
from services.model_service import model_service  # fcg-rewrite
from services.keyword_cache import keyword_cache  # fcg-rewrite
from services.guardrail_audit_service import GuardrailAuditService  # fcg-rewrite
from services.guardrail_message_utils import (  # fcg-rewrite
    ensure_image_detection_subscription,  # fcg-rewrite
    extract_assistant_text,  # fcg-rewrite
    prepare_detection_messages,  # fcg-rewrite
    render_conversation_text,  # fcg-rewrite
    resolve_default_application_id,  # fcg-rewrite
)
from services.guardrail_outcome_service import GuardrailOutcomeService  # fcg-rewrite
from services.risk_config_service import RiskConfigService  # fcg-rewrite
from services.data_security_service import PrivacyEngine  # fcg-rewrite

from models.requests import GuardrailRequest, Message  # fcg-rewrite
from models.responses import GuardrailResponse, GuardrailResult, ComplianceResult, SecurityResult, DataSecurityResult  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

class GuardrailPipeline:  # fcg-rewrite
    """Guardrail Detection Service"""

    def __init__(self, db: Session):  # fcg-rewrite
        self.db = db  # fcg-rewrite
        self.risk_config_service = RiskConfigService(db)  # fcg-rewrite
        self.outcome_service = GuardrailOutcomeService(db, self.risk_config_service)  # fcg-rewrite
        self.audit_service = GuardrailAuditService(db, self.outcome_service)  # fcg-rewrite

    async def run_guardrail_check(  # fcg-rewrite
        self,
        request: GuardrailRequest,  # fcg-rewrite
        ip_address: Optional[str] = None,  # fcg-rewrite
        user_agent: Optional[str] = None,  # fcg-rewrite
        tenant_id: Optional[str] = None,  # tenant_id for backward compatibility  # fcg-rewrite
        application_id: Optional[str] = None  # application_id for new multi-application support  # fcg-rewrite
    ) -> GuardrailResponse:  # fcg-rewrite
        """Execute guardrail detection"""

        # Generate request ID
        request_id = f"guardrails-{uuid.uuid4().hex}"  # fcg-rewrite

        # If application_id is not provided but tenant_id is, find default application
        if not application_id and tenant_id:  # fcg-rewrite
            application_id = resolve_default_application_id(self.db, tenant_id)  # fcg-rewrite
            if application_id:  # fcg-rewrite
                logger.debug(f"Using default application {application_id} for tenant {tenant_id}")  # fcg-rewrite

        prepared_messages = prepare_detection_messages(request.messages, tenant_id)  # fcg-rewrite
        user_content = prepared_messages.user_content  # fcg-rewrite
        try:
            # 1. Blacklist/whitelist pre-check (using high-performance memory cache, application-scoped)
            blacklist_hit, blacklist_name, blacklist_keywords = await keyword_cache.check_blacklist(  # fcg-rewrite
                user_content, tenant_id=tenant_id, application_id=application_id  # fcg-rewrite
            )
            if blacklist_hit:  # fcg-rewrite
                return await self.audit_service.assemble_blacklist_response(  # fcg-rewrite
                    request_id, user_content, blacklist_name, blacklist_keywords,  # fcg-rewrite
                    ip_address, user_agent, tenant_id, application_id  # fcg-rewrite
                )

            whitelist_hit, whitelist_name, whitelist_keywords = await keyword_cache.check_whitelist(  # fcg-rewrite
                user_content, tenant_id=tenant_id, application_id=application_id  # fcg-rewrite
            )
            if whitelist_hit:  # fcg-rewrite
                return await self.audit_service.assemble_whitelist_response(  # fcg-rewrite
                    request_id, user_content, whitelist_keywords,  # fcg-rewrite
                    ip_address, user_agent, tenant_id, application_id  # fcg-rewrite
                )

            # 3. Data leak detection for INPUT (before sending to model)
            # Note: Data leak detection logic differs from compliance/security detection
            # - Input detection: Detects user input for sensitive data, returns desensitized text
            #   The desensitized text should be the suggested answer for "replace" action
            # - Output detection: Detects LLM output for sensitive data, returns desensitized text
            #   The desensitized text should be the suggested answer for "replace" action
            data_security_service = PrivacyEngine(self.db)  # fcg-rewrite
            data_result = DataSecurityResult(risk_level="no_risk", categories=[])  # fcg-rewrite
            anonymized_text = None  # fcg-rewrite

            # Check if this is input or output detection

            if not prepared_messages.has_assistant_message:  # fcg-rewrite
                # This is INPUT detection - check user input for sensitive data before sending to model
                logger.info(f"Starting input data leak detection for tenant {tenant_id}, application {application_id}")  # fcg-rewrite
                data_detection_result = await data_security_service.detect_sensitive_data(  # fcg-rewrite
                    text=user_content,  # fcg-rewrite
                    tenant_id=tenant_id,  # fcg-rewrite
                    direction='input',  # fcg-rewrite
                    application_id=application_id  # fcg-rewrite
                )
                logger.info(f"Input data leak detection result: {data_detection_result}")  # fcg-rewrite

                # Construct data security result with detected entities for anonymization
                detected_entities = data_detection_result.get('detected_entities', []) if data_detection_result.get('risk_level', 'no_risk') != 'no_risk' else []  # fcg-rewrite
                anonymized_text_result = data_detection_result.get('anonymized_text') if data_detection_result.get('risk_level', 'no_risk') != 'no_risk' else None  # fcg-rewrite

                data_result = DataSecurityResult(  # fcg-rewrite
                    risk_level=data_detection_result.get('risk_level', 'no_risk'),  # fcg-rewrite
                    categories=data_detection_result.get('categories', []),  # fcg-rewrite
                    detected_entities=detected_entities,  # fcg-rewrite
                    anonymized_text=anonymized_text_result  # fcg-rewrite
                )

                # If sensitive data found in input, store the desensitized text
                # This will be used as the suggested answer to send to upstream LLM
                if data_result.risk_level != 'no_risk':  # fcg-rewrite
                    anonymized_text = data_detection_result.get('anonymized_text')  # fcg-rewrite

            # Check subscription for image detection if images are present
            ensure_image_detection_subscription(  # fcg-rewrite
                self.db, tenant_id, prepared_messages.has_image  # fcg-rewrite
            )

            # 4. Execute scanner-based detection (new system) or fall back to legacy detection
            matched_scanners = []  # Initialize for answer matching  # fcg-rewrite
            model_response = "scanner_detection"  # fcg-rewrite

            if application_id:  # fcg-rewrite
                # Use new scanner detection system
                try:
                    from services.scanner_detection_service import ScannerDetectionService  # fcg-rewrite
                    from uuid import UUID  # fcg-rewrite

                    logger.info(f"Using scanner detection for application {application_id}")  # fcg-rewrite

                    # Determine scan type based on message structure
                    scan_type = 'response' if prepared_messages.has_assistant_message else 'prompt'  # fcg-rewrite

                    # Execute scanner detection
                    scanner_service = ScannerDetectionService(self.db)  # fcg-rewrite
                    detection_result = await scanner_service.execute_detection(  # fcg-rewrite
                        content=user_content,  # fcg-rewrite
                        application_id=UUID(application_id),  # fcg-rewrite
                        tenant_id=tenant_id,  # fcg-rewrite
                        scan_type=scan_type,  # fcg-rewrite
                        messages_for_genai=prepared_messages.messages_dict  # fcg-rewrite
                    )

                    # Convert scanner detection result to compliance/security results
                    if detection_result.overall_risk_level == "no_risk":  # fcg-rewrite
                        compliance_result = ComplianceResult(risk_level="no_risk", categories=[])  # fcg-rewrite
                        security_result = SecurityResult(risk_level="no_risk", categories=[])  # fcg-rewrite
                    else:
                        # Determine risk levels for compliance and security
                        compliance_risk = detection_result.overall_risk_level if detection_result.compliance_categories else "no_risk"  # fcg-rewrite
                        security_risk = detection_result.overall_risk_level if detection_result.security_categories else "no_risk"  # fcg-rewrite

                        compliance_result = ComplianceResult(  # fcg-rewrite
                            risk_level=compliance_risk,  # fcg-rewrite
                            categories=detection_result.compliance_categories  # fcg-rewrite
                        )
                        security_result = SecurityResult(  # fcg-rewrite
                            risk_level=security_risk,  # fcg-rewrite
                            categories=detection_result.security_categories  # fcg-rewrite
                        )

                    # Store matched scanners for answer matching
                    matched_scanners = detection_result.matched_scanners  # fcg-rewrite
                    logger.info(f"Scanner detection complete: risk={detection_result.overall_risk_level}, matched_scanners={[s.scanner_tag for s in matched_scanners]}")  # fcg-rewrite

                except Exception as scanner_error:  # fcg-rewrite
                    logger.error(f"Scanner detection failed, falling back to legacy detection: {scanner_error}")  # fcg-rewrite
                    # Fall back to legacy detection
                    use_vl_model = prepared_messages.has_image  # fcg-rewrite
                    model_response, _ = await model_service.check_messages_with_sensitivity(  # fcg-rewrite
                        prepared_messages.messages_dict,  # fcg-rewrite
                        use_vl_model=use_vl_model,  # fcg-rewrite
                    )
                    compliance_result, security_result = self._parse_model_verdict(model_response, tenant_id)  # fcg-rewrite
            else:
                # No application_id: use legacy detection for backward compatibility
                logger.warning(f"No application_id provided, using legacy detection for tenant {tenant_id}")  # fcg-rewrite
                use_vl_model = prepared_messages.has_image  # fcg-rewrite
                model_response, _ = await model_service.check_messages_with_sensitivity(  # fcg-rewrite
                    prepared_messages.messages_dict,  # fcg-rewrite
                    use_vl_model=use_vl_model,  # fcg-rewrite
                )
                compliance_result, security_result = self._parse_model_verdict(model_response, tenant_id)  # fcg-rewrite

            # 5. Data leak detection for OUTPUT (after getting LLM response)
            if prepared_messages.has_assistant_message:  # fcg-rewrite
                # This is OUTPUT detection - check assistant's response for sensitive data
                detection_content = prepared_messages.assistant_content  # fcg-rewrite

                logger.info(f"Starting output data leak detection for tenant {tenant_id}, application {application_id}")  # fcg-rewrite
                data_detection_result = await data_security_service.detect_sensitive_data(  # fcg-rewrite
                    text=detection_content,  # fcg-rewrite
                    tenant_id=tenant_id,  # fcg-rewrite
                    direction='output',  # fcg-rewrite
                    application_id=application_id  # fcg-rewrite
                )
                logger.info(f"Output data leak detection result: {data_detection_result}")  # fcg-rewrite

                # Construct data security result with detected entities for anonymization
                detected_entities = data_detection_result.get('detected_entities', []) if data_detection_result.get('risk_level', 'no_risk') != 'no_risk' else []  # fcg-rewrite
                anonymized_text_result = data_detection_result.get('anonymized_text') if data_detection_result.get('risk_level', 'no_risk') != 'no_risk' else None  # fcg-rewrite

                data_result = DataSecurityResult(  # fcg-rewrite
                    risk_level=data_detection_result.get('risk_level', 'no_risk'),  # fcg-rewrite
                    categories=data_detection_result.get('categories', []),  # fcg-rewrite
                    detected_entities=detected_entities,  # fcg-rewrite
                    anonymized_text=anonymized_text_result  # fcg-rewrite
                )

                # If sensitive data found in output, store the desensitized text
                # This will be used as the suggested answer to return to user
                if data_result.risk_level != 'no_risk':  # fcg-rewrite
                    anonymized_text = data_detection_result.get('anonymized_text')  # fcg-rewrite

            # 6. Determine suggested action and answer
            overall_risk_level, suggest_action, suggest_answer = await self._finalize_guardrail_outcome(  # fcg-rewrite
                compliance_result, security_result, tenant_id=tenant_id, application_id=application_id,  # fcg-rewrite
                user_query=user_content, data_result=data_result, anonymized_text=anonymized_text,  # fcg-rewrite
                matched_scanners=matched_scanners  # fcg-rewrite
            )

            # 6.1 Append appeal link if applicable (any risk level with reject/replace action)
            if suggest_answer and suggest_action in ['reject', 'replace']:  # fcg-rewrite
                try:
                    from services.appeal_service import appeal_service  # fcg-rewrite
                    # Get tenant's language preference for appeal page
                    appeal_language = 'zh'  # Default to Chinese  # fcg-rewrite
                    if tenant_id:  # fcg-rewrite
                        try:
                            from database.models import Tenant  # fcg-rewrite
                            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()  # fcg-rewrite
                            if tenant and tenant.language:  # fcg-rewrite
                                appeal_language = tenant.language  # fcg-rewrite
                        except Exception:  # fcg-rewrite
                            pass
                    appeal_link = await appeal_service.generate_appeal_link(  # fcg-rewrite
                        request_id=request_id,  # fcg-rewrite
                        application_id=application_id,  # fcg-rewrite
                        language=appeal_language,  # fcg-rewrite
                        db=self.db  # fcg-rewrite
                    )
                    if appeal_link:  # fcg-rewrite
                        suggest_answer = f"{suggest_answer}\n\n{appeal_link}"  # fcg-rewrite
                except Exception as e:  # fcg-rewrite
                    logger.warning(f"Failed to generate appeal link: {e}")  # fcg-rewrite

            # 7. Asynchronously log detection results
            await self.audit_service.persist_detection_result(  # fcg-rewrite
                request_id, user_content, compliance_result, security_result,  # fcg-rewrite
                suggest_action, suggest_answer, model_response,  # fcg-rewrite
                ip_address, user_agent, tenant_id,  # fcg-rewrite
                has_image=prepared_messages.has_image,  # fcg-rewrite
                image_count=len(prepared_messages.saved_image_paths),  # fcg-rewrite
                image_paths=prepared_messages.saved_image_paths,  # fcg-rewrite
            )

            # 8. Construct response
            result = GuardrailResult(  # fcg-rewrite
                compliance=compliance_result,  # fcg-rewrite
                security=security_result,  # fcg-rewrite
                data=data_result  # fcg-rewrite
            )

            return GuardrailResponse(  # fcg-rewrite
                id=request_id,  # fcg-rewrite
                result=result,  # fcg-rewrite
                overall_risk_level=overall_risk_level,  # fcg-rewrite
                suggest_action=suggest_action,  # fcg-rewrite
                suggest_answer=suggest_answer,  # fcg-rewrite
            )

        except Exception as e:  # fcg-rewrite
            logger.error(f"Guardrail check error: {e}")  # fcg-rewrite
            # Return safe default response on error
            return await self.audit_service.assemble_error_response(  # fcg-rewrite
                request_id, user_content, str(e), tenant_id  # fcg-rewrite
            )

    def _extract_assistant_text(self, messages: List[Message]) -> str:  # fcg-rewrite
        return extract_assistant_text(messages)  # fcg-rewrite

    def _render_conversation_text(self, messages: List[Message]) -> str:  # fcg-rewrite
        return render_conversation_text(messages)  # fcg-rewrite

    def _parse_model_verdict(self, response: str, tenant_id: Optional[str] = None) -> Tuple[ComplianceResult, SecurityResult]:  # fcg-rewrite
        return self.outcome_service.parse_model_verdict(response, tenant_id)  # fcg-rewrite

    async def _craft_suggest_answer(self, categories: List[str], tenant_id: Optional[str] = None, application_id: Optional[str] = None, user_query: Optional[str] = None, matched_scanners: Optional[list] = None) -> str:  # fcg-rewrite
        return await self.outcome_service.craft_suggest_answer(  # fcg-rewrite
            categories, tenant_id, application_id, user_query, matched_scanners  # fcg-rewrite
        )

    async def _finalize_guardrail_outcome(  # fcg-rewrite
        self,
        compliance_result: ComplianceResult,  # fcg-rewrite
        security_result: SecurityResult,  # fcg-rewrite
        tenant_id: Optional[str] = None,  # tenant_id for backward compatibility  # fcg-rewrite
        application_id: Optional[str] = None,  # application_id for multi-application support  # fcg-rewrite
        user_query: Optional[str] = None,  # fcg-rewrite
        data_result: Optional[DataSecurityResult] = None,  # fcg-rewrite
        anonymized_text: Optional[str] = None,  # De-sensitized text for data leak scenarios  # fcg-rewrite
        matched_scanners: Optional[list] = None  # Matched scanners from scanner detection  # fcg-rewrite
    ) -> Tuple[str, str, Optional[str]]:  # fcg-rewrite
        return await self.outcome_service.finalize_guardrail_outcome(  # fcg-rewrite
            compliance_result,  # fcg-rewrite
            security_result,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            application_id,  # fcg-rewrite
            user_query,  # fcg-rewrite
            data_result,  # fcg-rewrite
            anonymized_text,  # fcg-rewrite
            matched_scanners,  # fcg-rewrite
        )

    async def _assemble_blacklist_response(  # fcg-rewrite
        self, request_id: str, content: str, list_name: str,  # fcg-rewrite
        keywords: List[str], ip_address: Optional[str], user_agent: Optional[str],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None  # fcg-rewrite
    ) -> GuardrailResponse:  # fcg-rewrite
        return await self.audit_service.assemble_blacklist_response(  # fcg-rewrite
            request_id,  # fcg-rewrite
            content,  # fcg-rewrite
            list_name,  # fcg-rewrite
            keywords,  # fcg-rewrite
            ip_address,  # fcg-rewrite
            user_agent,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            application_id,  # fcg-rewrite
        )

    async def _assemble_whitelist_response(  # fcg-rewrite
        self, request_id: str, content: str, list_name: str,  # fcg-rewrite
        keywords: List[str], ip_address: Optional[str], user_agent: Optional[str],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None  # fcg-rewrite
    ) -> GuardrailResponse:  # fcg-rewrite
        return await self.audit_service.assemble_whitelist_response(  # fcg-rewrite
            request_id,  # fcg-rewrite
            content,  # fcg-rewrite
            keywords,  # fcg-rewrite
            ip_address,  # fcg-rewrite
            user_agent,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            application_id,  # fcg-rewrite
        )

    async def _persist_detection_result(  # fcg-rewrite
        self, request_id: str, content: str, compliance_result: ComplianceResult,  # fcg-rewrite
        security_result: SecurityResult, suggest_action: str, suggest_answer: Optional[str],  # fcg-rewrite
        model_response: str, ip_address: Optional[str], user_agent: Optional[str],  # fcg-rewrite
        tenant_id: Optional[str] = None, has_image: bool = False,  # fcg-rewrite
        image_count: int = 0, image_paths: List[str] = None  # fcg-rewrite
    ):
        await self.audit_service.persist_detection_result(  # fcg-rewrite
            request_id,  # fcg-rewrite
            content,  # fcg-rewrite
            compliance_result,  # fcg-rewrite
            security_result,  # fcg-rewrite
            suggest_action,  # fcg-rewrite
            suggest_answer,  # fcg-rewrite
            model_response,  # fcg-rewrite
            ip_address,  # fcg-rewrite
            user_agent,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            has_image,  # fcg-rewrite
            image_count,  # fcg-rewrite
            image_paths,  # fcg-rewrite
        )

    async def _assemble_error_response(self, request_id: str, content: str, error: str, tenant_id: Optional[int] = None) -> GuardrailResponse:  # fcg-rewrite
        return await self.audit_service.assemble_error_response(  # fcg-rewrite
            request_id, content, error, tenant_id  # fcg-rewrite
        )
