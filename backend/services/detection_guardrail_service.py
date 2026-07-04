import uuid  # fcg-rewrite
import json  # fcg-rewrite
from typing import List, Dict, Tuple, Optional, Union, Any  # fcg-rewrite
from services.model_service import model_service  # fcg-rewrite
from services.keyword_cache import keyword_cache  # fcg-rewrite
from services.detection_guardrail_message_utils import DetectionRequestContextResolver  # fcg-rewrite
from services.detection_guardrail_outcome import (  # fcg-rewrite
    CATEGORY_NAMES,  # fcg-rewrite
    RISK_LEVEL_MAPPING,  # fcg-rewrite
    DetectionOutcomeCoordinator,  # fcg-rewrite
)

from models.requests import GuardrailRequest, Message  # fcg-rewrite
from models.responses import GuardrailResponse, GuardrailResult, ComplianceResult, SecurityResult, DataSecurityResult, AgentSafetyResult, HallucinationResult  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite
from utils.message_truncator import MessageTrimmer  # fcg-rewrite
from database.connection import get_db_session  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

class DetectionPipeline:  # fcg-rewrite
    """Detection service专用护栏服务 - 只写日志，不写数据库"""

    def __init__(self):  # fcg-rewrite
        # No database connection, only use cache
        self.context_resolver = DetectionRequestContextResolver()  # fcg-rewrite
        self.outcome_coordinator = DetectionOutcomeCoordinator()  # fcg-rewrite

    async def inspect_content_payload(  # fcg-rewrite
        self,
        content: str,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        request_id: str,  # fcg-rewrite
        model_sensitivity_trigger_level: Optional[str] = None  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        """
        Simplified detection method for proxy service
        Wrap single content text as GuardrailRequest and call the full detection flow
        """
        from models.requests import GuardrailRequest, Message  # fcg-rewrite

        # Wrap text content as message format
        message = Message(role="user", content=content)  # fcg-rewrite
        request = GuardrailRequest(model="detection", messages=[message])  # fcg-rewrite

        # Call full detection method
        result = await self.run_guardrail_check(  # fcg-rewrite
            request=request,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            model_sensitivity_trigger_level=model_sensitivity_trigger_level  # fcg-rewrite
        )

        # Return format compatible with proxy API
        return {  # fcg-rewrite
            "request_id": result.id,  # fcg-rewrite
            "suggest_action": result.suggest_action,  # fcg-rewrite
            "suggest_answer": result.suggest_answer,  # fcg-rewrite
            "overall_risk_level": result.overall_risk_level,  # fcg-rewrite
            "compliance_result": result.result.compliance.__dict__ if result.result.compliance else None,  # fcg-rewrite
            "security_result": result.result.security.__dict__ if result.result.security else None  # fcg-rewrite
        }

    async def inspect_message_batch(  # fcg-rewrite
        self,
        messages: List[Dict[str, str]],  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        request_id: str,  # fcg-rewrite
        model_sensitivity_trigger_level: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        """
        Context-aware detection method - support messages structure for question-answer pairs
        Directly use messages list for detection, support multi-turn conversation context
        """
        from models.requests import GuardrailRequest, Message  # fcg-rewrite

        # Convert dictionary format messages to Message objects (skip messages with null content)
        message_objects = []  # fcg-rewrite
        for msg in messages:  # fcg-rewrite
            content = msg.get("content") if isinstance(msg, dict) else msg.content  # fcg-rewrite
            role = msg.get("role") if isinstance(msg, dict) else msg.role  # fcg-rewrite
            if content is not None:  # fcg-rewrite
                message_objects.append(Message(role=role, content=content))  # fcg-rewrite

        request = GuardrailRequest(model="detection", messages=message_objects)  # fcg-rewrite

        # Call full detection method
        result = await self.run_guardrail_check(  # fcg-rewrite
            request=request,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            model_sensitivity_trigger_level=model_sensitivity_trigger_level  # fcg-rewrite
        )

        # Return format compatible with proxy API
        return {  # fcg-rewrite
            "request_id": result.id,  # fcg-rewrite
            "suggest_action": result.suggest_action,  # fcg-rewrite
            "suggest_answer": result.suggest_answer,  # fcg-rewrite
            "overall_risk_level": result.overall_risk_level,  # fcg-rewrite
            "compliance_result": result.result.compliance.__dict__ if result.result.compliance else None,  # fcg-rewrite
            "security_result": result.result.security.__dict__ if result.result.security else None,  # fcg-rewrite
            "data_result": result.result.data.__dict__ if result.result.data else None  # fcg-rewrite
        }

    async def run_guardrail_check(  # fcg-rewrite
        self,
        request: GuardrailRequest,  # fcg-rewrite
        ip_address: Optional[str] = None,  # fcg-rewrite
        user_agent: Optional[str] = None,  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        model_sensitivity_trigger_level: Optional[str] = None  # fcg-rewrite
    ) -> GuardrailResponse:  # fcg-rewrite
        """Execute guardrail detection (only write log file)"""

        # Generate request ID
        request_id = f"guardrails-{uuid.uuid4().hex}"  # fcg-rewrite

        # First truncate messages to meet maximum context length requirements
        truncated_messages = MessageTrimmer.truncate_messages(request.messages)  # fcg-rewrite

        # If no messages after truncation, return error
        if not truncated_messages:  # fcg-rewrite
            logger.warning(f"No valid messages after truncation for request {request_id}")  # fcg-rewrite
            return await self._assemble_error_response(request_id, "", "No valid messages after truncation", tenant_id, application_id)  # fcg-rewrite

        # If application_id is not provided but tenant_id is, find default application
        application_id = self.context_resolver.resolve_default_application(tenant_id, application_id)  # fcg-rewrite

        # Extract user content (using truncated messages)
        user_content = self._render_conversation_text(truncated_messages)  # fcg-rewrite

        try:
            # 1. Blacklist/whitelist pre-check (using high-performance memory cache, application-scoped)
            blacklist_hit, blacklist_name, blacklist_keywords = await keyword_cache.check_blacklist(  # fcg-rewrite
                user_content, tenant_id=tenant_id, application_id=application_id  # fcg-rewrite
            )
            if blacklist_hit:  # fcg-rewrite
                return await self._assemble_blacklist_response(  # fcg-rewrite
                    request_id, user_content, blacklist_name, blacklist_keywords,  # fcg-rewrite
                    ip_address, user_agent, tenant_id, application_id  # fcg-rewrite
                )

            whitelist_hit, whitelist_name, whitelist_keywords = await keyword_cache.check_whitelist(  # fcg-rewrite
                user_content, tenant_id=tenant_id, application_id=application_id  # fcg-rewrite
            )
            if whitelist_hit:  # fcg-rewrite
                return await self._assemble_whitelist_response(  # fcg-rewrite
                    request_id, user_content, whitelist_name, whitelist_keywords,  # fcg-rewrite
                    ip_address, user_agent, tenant_id, application_id  # fcg-rewrite
                )

            # 2. Determine detection direction and content
            # If the last message is assistant (output), detect output
            # Otherwise detect input
            detection_direction = "output" if truncated_messages and truncated_messages[-1].role == "assistant" else "input"  # fcg-rewrite
            # Extract appropriate content for data leak detection
            content_for_data_detection = self._choose_data_inspection_text(truncated_messages, detection_direction)  # fcg-rewrite

            # 2.5 Static pattern check (L1, <0.1ms) — fastest layer, runs before everything
            l1_pattern_detected = False  # fcg-rewrite
            if detection_direction == "input":  # fcg-rewrite
                try:
                    from plugins_builtin.basic_guard.input_pattern_service import input_pattern_service  # fcg-rewrite
                    user_msgs_for_pattern = [  # fcg-rewrite
                        {"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)}  # fcg-rewrite
                        for m in truncated_messages if m.role == "user"  # fcg-rewrite
                    ]
                    pattern_hits = input_pattern_service.check_messages(user_msgs_for_pattern)  # fcg-rewrite
                    if pattern_hits:  # fcg-rewrite
                        high_hits = [h for h in pattern_hits if h.get("severity") == "high"]  # fcg-rewrite
                        if high_hits:  # fcg-rewrite
                            logger.info(f"L1 static pattern detected injection: {[h['category'] for h in high_hits]}")  # fcg-rewrite
                            categories = list(set(h["category"] for h in high_hits))  # fcg-rewrite
                            security_result = SecurityResult(  # fcg-rewrite
                                risk_level="high_risk",  # fcg-rewrite
                                categories=[f"Prompt Injection ({c})" for c in categories],  # fcg-rewrite
                            )
                            l1_pattern_detected = True  # fcg-rewrite
                        else:
                            logger.info(f"L1 static pattern partial match (medium): {[h['category'] for h in pattern_hits]}")  # fcg-rewrite
                except Exception as e:  # fcg-rewrite
                    logger.warning(f"L1 static pattern check failed (fail-open): {e}")  # fcg-rewrite

            # 3. Prepare messages for model detection (must happen before parallel tasks)
            messages_dict, has_image, saved_image_paths = self.context_resolver.build_model_messages(  # fcg-rewrite
                truncated_messages, tenant_id  # fcg-rewrite
            )

            # 4. Three-way parallel detection with early short-circuit
            # - Prompt Guard (~15ms): prompt injection detection, always-on
            # - Qwen3Guard (~200ms): S1-S21 risk classification + E1-E4 HTML scanning
            # - DLP (~50-500ms): data leakage detection (regex + GenAI)
            # If any path detects high_risk, return immediately; others continue in background for logging.

            import asyncio  # fcg-rewrite

            # Initialize results (preserve L1 security_result if already set)
            compliance_result = ComplianceResult(risk_level="no_risk", categories=[])  # fcg-rewrite
            if not l1_pattern_detected:  # fcg-rewrite
                security_result = SecurityResult(risk_level="no_risk", categories=[])  # fcg-rewrite
            data_result = None  # fcg-rewrite
            data_anonymized_text = None  # fcg-rewrite
            matched_scanner_tags = []  # fcg-rewrite
            matched_scanners = []  # fcg-rewrite
            sensitivity_score = None  # fcg-rewrite
            model_response = None  # fcg-rewrite
            prompt_guard_categories = []  # fcg-rewrite

            # --- Task A: Prompt Guard (fastest, ~15ms) ---
            async def _run_prompt_guard():  # fcg-rewrite
                if detection_direction != "input":  # fcg-rewrite
                    return False, []  # fcg-rewrite
                try:
                    from plugins_builtin.basic_guard.prompt_guard_service import prompt_injection_service  # fcg-rewrite
                    user_msgs = [{"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)}  # fcg-rewrite
                                 for m in truncated_messages if m.role == "user"]  # fcg-rewrite
                    if not user_msgs:  # fcg-rewrite
                        return False, []  # fcg-rewrite
                    is_injection, details = await prompt_injection_service.check_messages(  # fcg-rewrite
                        messages=user_msgs, threshold=0.5, scan_user=True, scan_system=False,  # fcg-rewrite
                    )
                    logger.info(f"Prompt Guard raw result: is_injection={is_injection}, details={[{k: v for k, v in d.items() if k != 'content_preview'} for d in details]}")  # fcg-rewrite
                    if is_injection:  # fcg-rewrite
                        detected = False  # fcg-rewrite
                        categories = []  # fcg-rewrite
                        for d in details:  # fcg-rewrite
                            if not d.get("is_injection"):  # fcg-rewrite
                                continue  # fcg-rewrite
                            label = d.get("label", "")  # fcg-rewrite
                            scores = d.get("scores", {})  # fcg-rewrite
                            # v2 model: MALICIOUS label / ProtectAI: INJECTION label
                            if label in ("MALICIOUS", "INJECTION"):  # fcg-rewrite
                                categories.append("Prompt Injection")  # fcg-rewrite
                                detected = True  # fcg-rewrite
                            # v1 model: only trust JAILBREAK with high confidence
                            elif label == "JAILBREAK" and scores.get("JAILBREAK", 0) > 0.9:  # fcg-rewrite
                                categories.append("Prompt Injection (Jailbreak)")  # fcg-rewrite
                                detected = True  # fcg-rewrite
                        if detected:  # fcg-rewrite
                            logger.info(f"Prompt Guard detected: {categories}")  # fcg-rewrite
                            return True, categories  # fcg-rewrite
                    return False, []  # fcg-rewrite
                except Exception as e:  # fcg-rewrite
                    logger.warning(f"Prompt Guard detection failed (fail-open): {e}")  # fcg-rewrite
                    return False, []  # fcg-rewrite

            # --- Task B: Qwen3Guard model detection (S1-S21 + HTML E1-E4) ---
            async def _run_model_detection():  # fcg-rewrite
                _matched_scanner_tags = []  # fcg-rewrite
                _matched_scanners = []  # fcg-rewrite
                _sensitivity_score = None  # fcg-rewrite
                _model_response = None  # fcg-rewrite

                if application_id:  # fcg-rewrite
                    try:
                        from services.scanner_detection_service import ScannerDetectionService  # fcg-rewrite
                        from uuid import UUID  # fcg-rewrite
                        scanner_db = get_db_session()  # fcg-rewrite
                        try:
                            scanner_service = ScannerDetectionService(scanner_db)  # fcg-rewrite
                            scan_type = 'response' if truncated_messages and truncated_messages[-1].role == 'assistant' else 'prompt'  # fcg-rewrite
                            logger.info(f"Using scanner detection for application {application_id}, scan_type={scan_type}")  # fcg-rewrite
                            detection_result = await scanner_service.execute_detection(  # fcg-rewrite
                                content=user_content,  # fcg-rewrite
                                application_id=UUID(application_id),  # fcg-rewrite
                                tenant_id=tenant_id,  # fcg-rewrite
                                scan_type=scan_type,  # fcg-rewrite
                                messages_for_genai=messages_dict  # fcg-rewrite
                            )
                            if detection_result.overall_risk_level == "no_risk":  # fcg-rewrite
                                _comp = ComplianceResult(risk_level="no_risk", categories=[])  # fcg-rewrite
                                _sec = SecurityResult(risk_level="no_risk", categories=[])  # fcg-rewrite
                            else:
                                compliance_risk = detection_result.overall_risk_level if detection_result.compliance_categories else "no_risk"  # fcg-rewrite
                                security_risk = detection_result.overall_risk_level if detection_result.security_categories else "no_risk"  # fcg-rewrite
                                _comp = ComplianceResult(risk_level=compliance_risk, categories=detection_result.compliance_categories)  # fcg-rewrite
                                _sec = SecurityResult(risk_level=security_risk, categories=detection_result.security_categories)  # fcg-rewrite
                            _matched_scanner_tags = detection_result.matched_scanner_tags  # fcg-rewrite
                            _matched_scanners = detection_result.matched_scanners  # fcg-rewrite
                            _model_response = "scanner_detection"  # fcg-rewrite
                            logger.info(f"Scanner detection complete: risk={detection_result.overall_risk_level}, matched_tags={_matched_scanner_tags}")  # fcg-rewrite
                            return _comp, _sec, _matched_scanner_tags, _matched_scanners, _sensitivity_score, _model_response  # fcg-rewrite
                        finally:  # fcg-rewrite
                            scanner_db.close()  # fcg-rewrite
                    except Exception as scanner_error:  # fcg-rewrite
                        logger.error(f"Scanner detection failed, falling back to legacy detection: {scanner_error}")  # fcg-rewrite

                # Legacy detection (no application_id or scanner failed)
                if not application_id:  # fcg-rewrite
                    logger.warning(f"No application_id provided, using legacy detection for tenant {tenant_id}")  # fcg-rewrite
                _matched_scanners = []  # fcg-rewrite
                _model_response, _sensitivity_score = await model_service.check_messages_with_sensitivity(messages_dict, use_vl_model=has_image)  # fcg-rewrite
                _comp, _sec = await self._parse_model_verdict_with_sensitivity(  # fcg-rewrite
                    _model_response, _sensitivity_score, tenant_id, model_sensitivity_trigger_level, application_id  # fcg-rewrite
                )
                return _comp, _sec, _matched_scanner_tags, _matched_scanners, _sensitivity_score, _model_response  # fcg-rewrite

            # --- Task C: DLP data leakage detection ---
            async def _run_dlp():  # fcg-rewrite
                try:
                    return await self._execute_data_security_check(  # fcg-rewrite
                        content_for_data_detection, tenant_id,  # fcg-rewrite
                        direction=detection_direction, application_id=application_id  # fcg-rewrite
                    )
                except Exception as e:  # fcg-rewrite
                    logger.error(f"DLP detection failed: {e}")  # fcg-rewrite
                    return None, None  # fcg-rewrite

            # --- Task D: HTML content scan (conditional: only if input contains HTML) ---
            _has_html = detection_direction == "input" and (  # fcg-rewrite
                "<html" in user_content.lower() or "<!doctype" in user_content.lower()  # fcg-rewrite
                or ("<!--" in user_content and "</" in user_content)  # fcg-rewrite
            )

            async def _run_html_scan():  # fcg-rewrite
                if not _has_html:  # fcg-rewrite
                    return None  # fcg-rewrite
                try:
                    from services.content_scan_service import content_scan_service  # fcg-rewrite
                    result = await content_scan_service.scan_webpage(user_content)  # fcg-rewrite
                    if result.get("risk_level") in ("high", "medium"):  # fcg-rewrite
                        risk_types = result.get("risk_types", [])  # fcg-rewrite
                        logger.info(f"Content scan detected risks in HTML input: {risk_types}")  # fcg-rewrite
                        return SecurityResult(  # fcg-rewrite
                            risk_level="high_risk",  # fcg-rewrite
                            categories=[rt.replace("_", " ").title() for rt in risk_types]  # fcg-rewrite
                        )
                    return None  # fcg-rewrite
                except Exception as e:  # fcg-rewrite
                    logger.warning(f"Content scan enhancement failed: {e}")  # fcg-rewrite
                    return None  # fcg-rewrite

            # Launch all tasks in parallel (skip if L1 static pattern already detected high-risk)
            if l1_pattern_detected:  # fcg-rewrite
                # L1 already set security_result to high_risk, still run DLP for data protection
                dlp_result = await _run_dlp()  # fcg-rewrite
                data_result, data_anonymized_text = dlp_result  # fcg-rewrite
                logger.info("L1 static pattern short-circuit: skipping ML detection, DLP still runs")  # fcg-rewrite
            else:
                pg_task = asyncio.ensure_future(_run_prompt_guard())  # fcg-rewrite
                model_task = asyncio.ensure_future(_run_model_detection())  # fcg-rewrite
                dlp_task = asyncio.ensure_future(_run_dlp())  # fcg-rewrite
                html_task = asyncio.ensure_future(_run_html_scan()) if _has_html else None  # fcg-rewrite

                # Prompt Guard is fastest (~15ms). Wait for it first for early short-circuit.
                pg_is_injection, prompt_guard_categories = await pg_task  # fcg-rewrite
                if pg_is_injection:  # fcg-rewrite
                    security_result = SecurityResult(risk_level="high_risk", categories=prompt_guard_categories)  # fcg-rewrite
                    # Short-circuit: return early, let others finish in background for logging
                    try:
                        if model_task.done():  # fcg-rewrite
                            model_result = model_task.result()  # fcg-rewrite
                            compliance_result = model_result[0]  # fcg-rewrite
                            matched_scanner_tags = model_result[2]  # fcg-rewrite
                            matched_scanners = model_result[3]  # fcg-rewrite
                            sensitivity_score = model_result[4]  # fcg-rewrite
                            model_response = model_result[5]  # fcg-rewrite
                        if dlp_task.done():  # fcg-rewrite
                            data_result, data_anonymized_text = dlp_task.result()  # fcg-rewrite
                    except Exception:  # fcg-rewrite
                        pass

                    # Fire-and-forget: let remaining tasks complete for logging
                    bg_tasks = [model_task, dlp_task]  # fcg-rewrite
                    if html_task:  # fcg-rewrite
                        bg_tasks.append(html_task)  # fcg-rewrite

                    async def _collect_background():  # fcg-rewrite
                        try:
                            await asyncio.gather(*bg_tasks, return_exceptions=True)  # fcg-rewrite
                        except Exception:  # fcg-rewrite
                            pass
                    asyncio.ensure_future(_collect_background())  # fcg-rewrite

                    logger.info(f"Short-circuit: Prompt Guard detected injection, returning early")  # fcg-rewrite
                else:
                    # No injection detected by Prompt Guard, wait for all tasks
                    wait_tasks = [model_task, dlp_task]  # fcg-rewrite
                    if html_task:  # fcg-rewrite
                        wait_tasks.append(html_task)  # fcg-rewrite
                    results = await asyncio.gather(*wait_tasks)  # fcg-rewrite

                    model_result = results[0]  # fcg-rewrite
                    dlp_result = results[1]  # fcg-rewrite
                    html_result = results[2] if html_task else None  # fcg-rewrite

                    compliance_result_model, security_result_model, matched_scanner_tags, matched_scanners, sensitivity_score, model_response = model_result  # fcg-rewrite
                    data_result, data_anonymized_text = dlp_result  # fcg-rewrite

                    # Use model detection results
                    compliance_result = compliance_result_model  # fcg-rewrite
                    security_result = security_result_model  # fcg-rewrite

                    # Merge HTML scan result if it found risks
                    if html_result:  # fcg-rewrite
                        risk_order = {'no_risk': 0, 'low_risk': 1, 'medium_risk': 2, 'high_risk': 3}  # fcg-rewrite
                        if risk_order.get(html_result.risk_level, 0) > risk_order.get(security_result.risk_level, 0):  # fcg-rewrite
                            security_result.categories.extend(html_result.categories)  # fcg-rewrite
                            security_result = SecurityResult(  # fcg-rewrite
                                risk_level=html_result.risk_level,  # fcg-rewrite
                                categories=security_result.categories  # fcg-rewrite
                            )

            # 5.5 Plugin detection hooks (detection phase)
            hallucination_result = None  # fcg-rewrite
            plugin_results_dict = {}  # fcg-rewrite
            if application_id:  # fcg-rewrite
                try:
                    from plugins.registry import plugin_registry  # fcg-rewrite
                    from plugins.hooks import HookContext, HookPhase  # fcg-rewrite
                    messages_as_dicts = [{"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)} for m in truncated_messages]  # fcg-rewrite
                    # Extract assistant content for output-direction checks
                    assistant_content = ""  # fcg-rewrite
                    for msg in reversed(truncated_messages):  # fcg-rewrite
                        if msg.role == "assistant":  # fcg-rewrite
                            assistant_content = msg.content if isinstance(msg.content, str) else str(msg.content)  # fcg-rewrite
                            break
                    hook_ctx = HookContext(  # fcg-rewrite
                        phase=HookPhase.DETECTION,  # fcg-rewrite
                        request_id=request_id,  # fcg-rewrite
                        tenant_id=str(tenant_id) if tenant_id else "",  # fcg-rewrite
                        application_id=str(application_id),  # fcg-rewrite
                        messages=messages_as_dicts,  # fcg-rewrite
                        content=assistant_content or user_content,  # fcg-rewrite
                        detection_direction=detection_direction,  # fcg-rewrite
                    )
                    plugin_hook_results = await plugin_registry.dispatch_hook(HookPhase.DETECTION, hook_ctx)  # fcg-rewrite
                    for pr in plugin_hook_results:  # fcg-rewrite
                        plugin_results_dict[pr.plugin_name] = {  # fcg-rewrite
                            "risk_level": pr.risk_level,  # fcg-rewrite
                            "categories": pr.categories,  # fcg-rewrite
                            "action": pr.action,  # fcg-rewrite
                            "metadata": pr.metadata,  # fcg-rewrite
                        }
                        # Backward compat: populate hallucination_result if hallucination plugin returned
                        if pr.plugin_name == "hallucination_detection" and pr.risk_level != "no_risk":  # fcg-rewrite
                            from models.responses import HallucinationResult  # fcg-rewrite
                            hallucination_result = HallucinationResult(  # fcg-rewrite
                                risk_level=pr.risk_level,  # fcg-rewrite
                                categories=pr.categories,  # fcg-rewrite
                                groundedness_score=pr.metadata.get("groundedness_score"),  # fcg-rewrite
                                consistency_score=pr.metadata.get("consistency_score"),  # fcg-rewrite
                                flagged_claims=pr.metadata.get("flagged_claims", []),  # fcg-rewrite
                            )
                except Exception as e:  # fcg-rewrite
                    logger.error(f"Plugin detection hook error: {e}")  # fcg-rewrite

            # 5.6 Agent safety: reasoning content audit (via extra_body)
            # Run reasoning_content through the scanner detection pipeline
            reasoning_content = None  # fcg-rewrite
            if request.extra_body:  # fcg-rewrite
                reasoning_content = request.extra_body.get('reasoning_content')  # fcg-rewrite
            if reasoning_content and reasoning_content.strip() and application_id:  # fcg-rewrite
                try:
                    logger.info(f"Reasoning content audit: running scanner detection on reasoning_content ({len(reasoning_content)} chars)")  # fcg-rewrite
                    from services.scanner_detection_service import ScannerDetectionService  # fcg-rewrite
                    from uuid import UUID  # fcg-rewrite
                    reasoning_scanner_db = get_db_session()  # fcg-rewrite
                    try:
                        reasoning_scanner_service = ScannerDetectionService(reasoning_scanner_db)  # fcg-rewrite
                        reasoning_messages_for_genai = [{"role": "user", "content": reasoning_content}]  # fcg-rewrite
                        reasoning_detection_result = await reasoning_scanner_service.execute_detection(  # fcg-rewrite
                            content=reasoning_content,  # fcg-rewrite
                            application_id=UUID(application_id),  # fcg-rewrite
                            tenant_id=tenant_id,  # fcg-rewrite
                            scan_type="prompt",  # fcg-rewrite
                            messages_for_genai=reasoning_messages_for_genai  # fcg-rewrite
                        )
                        logger.info(f"Reasoning content scanner result: risk={reasoning_detection_result.overall_risk_level}, tags={reasoning_detection_result.matched_scanner_tags}")  # fcg-rewrite
                        if reasoning_detection_result.overall_risk_level != "no_risk":  # fcg-rewrite
                            reasoning_categories = []  # fcg-rewrite
                            if reasoning_detection_result.compliance_categories:  # fcg-rewrite
                                reasoning_categories.extend(reasoning_detection_result.compliance_categories)  # fcg-rewrite
                            if reasoning_detection_result.security_categories:  # fcg-rewrite
                                reasoning_categories.extend(reasoning_detection_result.security_categories)  # fcg-rewrite
                            plugin_results_dict["agent_safety_reasoning"] = {  # fcg-rewrite
                                "risk_level": reasoning_detection_result.overall_risk_level,  # fcg-rewrite
                                "categories": reasoning_categories,  # fcg-rewrite
                                "action": "block",  # fcg-rewrite
                                "metadata": {"source": "reasoning_content_safety_audit", "matched_tags": reasoning_detection_result.matched_scanner_tags},  # fcg-rewrite
                            }
                            logger.info(f"Reasoning content safety audit: risk={reasoning_detection_result.overall_risk_level}, categories={reasoning_categories}")  # fcg-rewrite
                        else:
                            logger.info(f"Reasoning content safety audit: no risk detected")  # fcg-rewrite
                    finally:  # fcg-rewrite
                        reasoning_scanner_db.close()  # fcg-rewrite
                except Exception as e:  # fcg-rewrite
                    logger.error(f"Reasoning content safety audit failed: {e}", exc_info=True)  # fcg-rewrite

            # 6. Determine suggested action and answer (include data security result)
            overall_risk_level, suggest_action, suggest_answer = await self._finalize_guardrail_outcome_with_data(  # fcg-rewrite
                compliance_result, security_result, data_result, tenant_id, application_id, user_content, data_anonymized_text, matched_scanners  # fcg-rewrite
            )

            # 6.0.1 Incorporate plugin risk into overall assessment
            risk_order = {'no_risk': 0, 'low_risk': 1, 'medium_risk': 2, 'high_risk': 3}  # fcg-rewrite
            for pr_name, pr_data in plugin_results_dict.items():  # fcg-rewrite
                pr_risk = pr_data.get("risk_level", "no_risk")  # fcg-rewrite
                if risk_order.get(pr_risk, 0) > risk_order.get(overall_risk_level, 0):  # fcg-rewrite
                    overall_risk_level = pr_risk  # fcg-rewrite
                if pr_data.get("action") == "block":  # fcg-rewrite
                    suggest_action = 'reject'  # fcg-rewrite
                    suggest_answer = suggest_answer or pr_data.get("metadata", {}).get("blocked_message", "Content blocked by plugin.")  # fcg-rewrite

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
                        language=appeal_language  # fcg-rewrite
                    )
                    if appeal_link:  # fcg-rewrite
                        suggest_answer = f"{suggest_answer}\n\n{appeal_link}"  # fcg-rewrite
                except Exception as e:  # fcg-rewrite
                    logger.warning(f"Failed to generate appeal link: {e}")  # fcg-rewrite

            # 7. Asynchronously record detection results to log file (not write to database)
            await self._persist_detection_result(  # fcg-rewrite
                request_id, user_content, compliance_result, security_result, data_result,  # fcg-rewrite
                suggest_action, suggest_answer, model_response,  # fcg-rewrite
                ip_address, user_agent, tenant_id, application_id, sensitivity_score,  # fcg-rewrite
                has_image=has_image, image_count=len(saved_image_paths), image_paths=saved_image_paths,  # fcg-rewrite
                matched_scanner_tags=matched_scanner_tags,  # fcg-rewrite
                hallucination_result=hallucination_result,  # fcg-rewrite
            )

            # 8. Construct response
            result = GuardrailResult(  # fcg-rewrite
                compliance=compliance_result,  # fcg-rewrite
                security=security_result,  # fcg-rewrite
                data=data_result,  # fcg-rewrite
                hallucination=hallucination_result,  # fcg-rewrite
                plugin_results=plugin_results_dict if plugin_results_dict else None,  # fcg-rewrite
            )

            return GuardrailResponse(  # fcg-rewrite
                id=request_id,  # fcg-rewrite
                result=result,  # fcg-rewrite
                overall_risk_level=overall_risk_level,  # fcg-rewrite
                suggest_action=suggest_action,  # fcg-rewrite
                suggest_answer=suggest_answer,  # fcg-rewrite
                score=sensitivity_score,  # fcg-rewrite
            )

        except Exception as e:  # fcg-rewrite
            logger.error(f"Guardrail check error: {e}")  # fcg-rewrite
            # When an error occurs, return safe default response
            return await self._assemble_error_response(request_id, user_content, str(e), tenant_id, application_id)  # fcg-rewrite

    def _render_conversation_text(self, messages: List[Message]) -> str:  # fcg-rewrite
        return self.context_resolver.render_conversation_text(messages)  # fcg-rewrite

    def _choose_data_inspection_text(self, messages: List[Message], direction: str) -> str:  # fcg-rewrite
        return self.context_resolver.choose_data_inspection_text(messages, direction)  # fcg-rewrite

    async def _parse_model_verdict(self, response: str, tenant_id: Optional[str] = None) -> Tuple[ComplianceResult, SecurityResult]:  # fcg-rewrite
        return await self.outcome_coordinator.parse_model_verdict(response, tenant_id)  # fcg-rewrite

    async def _parse_model_verdict_with_sensitivity(  # fcg-rewrite
        self, response: str, sensitivity_score: Optional[float], tenant_id: Optional[str] = None,  # fcg-rewrite
        model_sensitivity_trigger_level: Optional[str] = None, application_id: Optional[str] = None  # fcg-rewrite
    ) -> Tuple[ComplianceResult, SecurityResult]:  # fcg-rewrite
        return await self.outcome_coordinator.parse_model_verdict_with_sensitivity(  # fcg-rewrite
            response,  # fcg-rewrite
            sensitivity_score,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            model_sensitivity_trigger_level,  # fcg-rewrite
            application_id,  # fcg-rewrite
        )

    async def _execute_data_security_check(self, text: str, tenant_id: Optional[str], direction: str = "input", application_id: Optional[str] = None) -> Tuple[DataSecurityResult, Optional[str]]:  # fcg-rewrite
        return await self.outcome_coordinator.execute_data_security_check(  # fcg-rewrite
            text, tenant_id, direction, application_id  # fcg-rewrite
        )

    def _pick_peak_risk_level(self, categories: List[str]) -> str:  # fcg-rewrite
        if not categories:  # fcg-rewrite
            return "no_risk"  # fcg-rewrite
        risk_levels = []  # fcg-rewrite
        for category in categories:  # fcg-rewrite
            for code, name in CATEGORY_NAMES.items():  # fcg-rewrite
                if name == category:  # fcg-rewrite
                    risk_levels.append(RISK_LEVEL_MAPPING[code])  # fcg-rewrite
                    break
        if "high_risk" in risk_levels:  # fcg-rewrite
            return "high_risk"  # fcg-rewrite
        if "medium_risk" in risk_levels:  # fcg-rewrite
            return "medium_risk"  # fcg-rewrite
        if "low_risk" in risk_levels:  # fcg-rewrite
            return "low_risk"  # fcg-rewrite
        return "no_risk"  # fcg-rewrite

    async def _finalize_guardrail_outcome_with_data(  # fcg-rewrite
        self,
        compliance_result: ComplianceResult,  # fcg-rewrite
        security_result: SecurityResult,  # fcg-rewrite
        data_result: DataSecurityResult,  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        user_query: Optional[str] = None,  # fcg-rewrite
        data_anonymized_text: Optional[str] = None,  # fcg-rewrite
        matched_scanners: Optional[list] = None  # fcg-rewrite
    ) -> Tuple[str, str, Optional[str]]:  # fcg-rewrite
        return await self.outcome_coordinator.finalize_guardrail_outcome_with_data(  # fcg-rewrite
            compliance_result,  # fcg-rewrite
            security_result,  # fcg-rewrite
            data_result,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            application_id,  # fcg-rewrite
            user_query,  # fcg-rewrite
            data_anonymized_text,  # fcg-rewrite
            matched_scanners,  # fcg-rewrite
        )

    async def _finalize_guardrail_outcome(self, compliance_result: ComplianceResult, security_result: SecurityResult, tenant_id: Optional[str] = None, application_id: Optional[str] = None, user_query: Optional[str] = None, matched_scanners: Optional[list] = None) -> Tuple[str, str, Optional[str]]:  # fcg-rewrite
        return await self.outcome_coordinator.finalize_guardrail_outcome(  # fcg-rewrite
            compliance_result,  # fcg-rewrite
            security_result,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            application_id,  # fcg-rewrite
            user_query,  # fcg-rewrite
            matched_scanners,  # fcg-rewrite
        )

    async def _craft_suggest_answer(self, categories: List[str], tenant_id: Optional[str] = None, application_id: Optional[str] = None, user_query: Optional[str] = None, matched_scanners: Optional[list] = None) -> str:  # fcg-rewrite
        return await self.outcome_coordinator.craft_suggest_answer(  # fcg-rewrite
            categories,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            application_id,  # fcg-rewrite
            user_query,  # fcg-rewrite
            matched_scanners,  # fcg-rewrite
        )



    async def _load_sensitivity_trigger_level(self, tenant_id: str = None, application_id: str = None) -> str:  # fcg-rewrite
        return await self.outcome_coordinator.load_sensitivity_trigger_level(  # fcg-rewrite
            tenant_id, application_id  # fcg-rewrite
        )

    async def _meets_sensitivity_threshold(self, sensitivity_score: float, tenant_id: str = None, application_id: str = None) -> bool:  # fcg-rewrite
        return await self.outcome_coordinator.meets_sensitivity_threshold(  # fcg-rewrite
            sensitivity_score, tenant_id, application_id  # fcg-rewrite
        )

    async def _assemble_blacklist_response(  # fcg-rewrite
        self, request_id: str, content: str, list_name: str,  # fcg-rewrite
        keywords: List[str], ip_address: Optional[str], user_agent: Optional[str],  # fcg-rewrite
        tenant_id: Optional[str] = None,  # fcg-rewrite
        application_id: Optional[str] = None  # fcg-rewrite
    ) -> GuardrailResponse:  # fcg-rewrite
        return await self.outcome_coordinator.assemble_blacklist_response(  # fcg-rewrite
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
        return await self.outcome_coordinator.assemble_whitelist_response(  # fcg-rewrite
            request_id,  # fcg-rewrite
            content,  # fcg-rewrite
            list_name,  # fcg-rewrite
            keywords,  # fcg-rewrite
            ip_address,  # fcg-rewrite
            user_agent,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            application_id,  # fcg-rewrite
        )

    async def _persist_detection_result(  # fcg-rewrite
        self, request_id: str, content: str, compliance_result: ComplianceResult,  # fcg-rewrite
        security_result: SecurityResult, data_result: DataSecurityResult,  # fcg-rewrite
        suggest_action: str, suggest_answer: Optional[str],  # fcg-rewrite
        model_response: str, ip_address: Optional[str], user_agent: Optional[str],  # fcg-rewrite
        tenant_id: Optional[str] = None, application_id: Optional[str] = None,  # fcg-rewrite
        sensitivity_score: Optional[float] = None,  # fcg-rewrite
        has_image: bool = False, image_count: int = 0, image_paths: List[str] = None,  # fcg-rewrite
        matched_scanner_tags: List[str] = None,  # fcg-rewrite
        agent_safety_result: Optional[AgentSafetyResult] = None,  # fcg-rewrite
        hallucination_result: Optional[HallucinationResult] = None  # fcg-rewrite
    ):
        await self.outcome_coordinator.persist_detection_result(  # fcg-rewrite
            request_id,  # fcg-rewrite
            content,  # fcg-rewrite
            compliance_result,  # fcg-rewrite
            security_result,  # fcg-rewrite
            data_result,  # fcg-rewrite
            suggest_action,  # fcg-rewrite
            suggest_answer,  # fcg-rewrite
            model_response,  # fcg-rewrite
            ip_address,  # fcg-rewrite
            user_agent,  # fcg-rewrite
            tenant_id,  # fcg-rewrite
            application_id,  # fcg-rewrite
            sensitivity_score,  # fcg-rewrite
            has_image,  # fcg-rewrite
            image_count,  # fcg-rewrite
            image_paths,  # fcg-rewrite
            matched_scanner_tags,  # fcg-rewrite
            agent_safety_result,  # fcg-rewrite
            hallucination_result,  # fcg-rewrite
        )

    async def _assemble_error_response(self, request_id: str, content: str, error: str, tenant_id: Optional[str] = None, application_id: Optional[str] = None) -> GuardrailResponse:  # fcg-rewrite
        return await self.outcome_coordinator.assemble_error_response(  # fcg-rewrite
            request_id, content, error, tenant_id, application_id  # fcg-rewrite
        )
# 创建全局实例
detection_guardrail_service = DetectionPipeline()  # fcg-rewrite
