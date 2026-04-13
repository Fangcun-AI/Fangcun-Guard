import uuid
import json
from typing import List, Dict, Tuple, Optional, Union, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from services.model_service import model_service
from services.keyword_service import KeywordService
from services.keyword_cache import keyword_cache
from services.template_cache import template_cache
from services.async_logger import async_detection_logger
from services.risk_config_cache import risk_config_cache

from models.requests import GuardrailRequest, Message
from models.responses import GuardrailResponse, GuardrailResult, ComplianceResult, SecurityResult, DataSecurityResult, AgentSafetyResult, HallucinationResult
from utils.logger import setup_logger
from utils.message_truncator import MessageTruncator
from utils.i18n_loader import get_translation
from database.connection import get_db_session
from database.models import Application

logger = setup_logger()

# Risk level mapping (21 risk types)
RISK_LEVEL_MAPPING = {
    'S2': 'high_risk',   # Sensitive Political Topics
    'S3': 'high_risk',   # Insult to National Symbols or Leaders
    'S5': 'high_risk',   # Violent Crime
    'S9': 'high_risk',   # Prompt Attacks
    'S15': 'high_risk',  # Weapons of Mass Destruction
    'S17': 'high_risk',  # Sexual Crimes
    'S4': 'medium_risk', # Harm to Minors
    'S6': 'medium_risk', # Non-Violent Crime
    'S7': 'medium_risk', # Pornography
    'S16': 'medium_risk',# Self-Harm
    'S1': 'low_risk',    # General Political Topics
    'S8': 'low_risk',    # Hate & Discrimination
    'S10': 'low_risk',   # Profanity
    'S11': 'low_risk',   # Privacy Invasion
    'S12': 'low_risk',   # Commercial Violations
    'S13': 'low_risk',   # Intellectual Property Infringement
    'S14': 'low_risk',   # Harassment
    'S18': 'low_risk',   # Threats
    'S19': 'low_risk',   # Professional Financial Advice
    'S20': 'low_risk',   # Professional Medical Advice
    'S21': 'low_risk',   # Professional Legal Advice
}

# Category name mapping (21 risk types)
CATEGORY_NAMES = {
    'S1': 'General Political Topics',
    'S2': 'Sensitive Political Topics',
    'S3': 'Insult to National Symbols or Leaders',
    'S4': 'Harm to Minors',
    'S5': 'Violent Crime',
    'S6': 'Non-Violent Crime',
    'S7': 'Pornography',
    'S8': 'Hate & Discrimination',
    'S9': 'Prompt Attacks',
    'S10': 'Profanity',
    'S11': 'Privacy Invasion',
    'S12': 'Commercial Violations',
    'S13': 'Intellectual Property Infringement',
    'S14': 'Harassment',
    'S15': 'Weapons of Mass Destruction',
    'S16': 'Self-Harm',
    'S17': 'Sexual Crimes',
    'S18': 'Threats',
    'S19': 'Professional Financial Advice',
    'S20': 'Professional Medical Advice',
    'S21': 'Professional Legal Advice',
}

class DetectionGuardrailService:
    """Detection service专用护栏服务 - 只写日志，不写数据库"""
    
    def __init__(self):
        # No database connection, only use cache
        pass
    
    async def detect_content(
        self,
        content: str,
        tenant_id: str,
        request_id: str,
        model_sensitivity_trigger_level: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Simplified detection method for proxy service
        Wrap single content text as GuardrailRequest and call check_guardrails
        """
        from models.requests import GuardrailRequest, Message
        
        # Wrap text content as message format
        message = Message(role="user", content=content)
        request = GuardrailRequest(model="detection", messages=[message])

        # Call full detection method
        result = await self.check_guardrails(
            request=request,
            tenant_id=tenant_id,
            model_sensitivity_trigger_level=model_sensitivity_trigger_level
        )
        
        # Return format compatible with proxy API
        return {
            "request_id": result.id,
            "suggest_action": result.suggest_action,
            "suggest_answer": result.suggest_answer,
            "overall_risk_level": result.overall_risk_level,
            "compliance_result": result.result.compliance.__dict__ if result.result.compliance else None,
            "security_result": result.result.security.__dict__ if result.result.security else None
        }

    async def detect_messages(
        self,
        messages: List[Dict[str, str]],
        tenant_id: str,
        request_id: str,
        model_sensitivity_trigger_level: Optional[str] = None,
        application_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Context-aware detection method - support messages structure for question-answer pairs
        Directly use messages list for detection, support multi-turn conversation context
        """
        from models.requests import GuardrailRequest, Message

        # Convert dictionary format messages to Message objects (skip messages with null content)
        message_objects = []
        for msg in messages:
            content = msg.get("content") if isinstance(msg, dict) else msg.content
            role = msg.get("role") if isinstance(msg, dict) else msg.role
            if content is not None:
                message_objects.append(Message(role=role, content=content))

        request = GuardrailRequest(model="detection", messages=message_objects)

        # Call full detection method
        result = await self.check_guardrails(
            request=request,
            tenant_id=tenant_id,
            application_id=application_id,
            model_sensitivity_trigger_level=model_sensitivity_trigger_level
        )
        
        # Return format compatible with proxy API
        return {
            "request_id": result.id,
            "suggest_action": result.suggest_action,
            "suggest_answer": result.suggest_answer,
            "overall_risk_level": result.overall_risk_level,
            "compliance_result": result.result.compliance.__dict__ if result.result.compliance else None,
            "security_result": result.result.security.__dict__ if result.result.security else None,
            "data_result": result.result.data.__dict__ if result.result.data else None
        }
    
    async def check_guardrails(
        self,
        request: GuardrailRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tenant_id: Optional[str] = None,
        application_id: Optional[str] = None,
        model_sensitivity_trigger_level: Optional[str] = None
    ) -> GuardrailResponse:
        """Execute guardrail detection (only write log file)"""
        
        # Generate request ID
        request_id = f"guardrails-{uuid.uuid4().hex}"
        
        # First truncate messages to meet maximum context length requirements
        truncated_messages = MessageTruncator.truncate_messages(request.messages)
        
        # If no messages after truncation, return error
        if not truncated_messages:
            logger.warning(f"No valid messages after truncation for request {request_id}")
            return await self._handle_error(request_id, "", "No valid messages after truncation", tenant_id, application_id)
        
        # If application_id is not provided but tenant_id is, find default application
        if not application_id and tenant_id:
            try:
                db = get_db_session()
                try:
                    tenant_uuid = uuid.UUID(str(tenant_id))
                    default_app = db.query(Application).filter(
                        Application.tenant_id == tenant_uuid,
                        Application.is_active == True
                    ).order_by(Application.created_at.asc()).first()
                    
                    if default_app:
                        application_id = str(default_app.id)
                        logger.debug(f"Using default application {application_id} for tenant {tenant_id}")
                    else:
                        logger.warning(f"No active application found for tenant {tenant_id}")
                finally:
                    db.close()
            except (ValueError, Exception) as e:
                logger.warning(f"Failed to find default application for tenant {tenant_id}: {e}")

        # Extract user content (using truncated messages)
        user_content = self._extract_user_content(truncated_messages)
        
        try:
            # 1. Blacklist/whitelist pre-check (using high-performance memory cache, application-scoped)
            blacklist_hit, blacklist_name, blacklist_keywords = await keyword_cache.check_blacklist(
                user_content, tenant_id=tenant_id, application_id=application_id
            )
            if blacklist_hit:
                return await self._handle_blacklist_hit(
                    request_id, user_content, blacklist_name, blacklist_keywords,
                    ip_address, user_agent, tenant_id, application_id
                )

            whitelist_hit, whitelist_name, whitelist_keywords = await keyword_cache.check_whitelist(
                user_content, tenant_id=tenant_id, application_id=application_id
            )
            if whitelist_hit:
                return await self._handle_whitelist_hit(
                    request_id, user_content, whitelist_name, whitelist_keywords,
                    ip_address, user_agent, tenant_id, application_id
                )
            
            # 2. Determine detection direction and content
            # If the last message is assistant (output), detect output
            # Otherwise detect input
            detection_direction = "output" if truncated_messages and truncated_messages[-1].role == "assistant" else "input"
            # Extract appropriate content for data leak detection
            content_for_data_detection = self._extract_content_for_data_detection(truncated_messages, detection_direction)

            # 2.5 Static pattern check (L1, <0.1ms) — fastest layer, runs before everything
            l1_pattern_detected = False
            if detection_direction == "input":
                try:
                    from plugins_builtin.basic_guard.input_pattern_service import input_pattern_service
                    user_msgs_for_pattern = [
                        {"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)}
                        for m in truncated_messages if m.role == "user"
                    ]
                    pattern_hits = input_pattern_service.check_messages(user_msgs_for_pattern)
                    if pattern_hits:
                        high_hits = [h for h in pattern_hits if h.get("severity") == "high"]
                        if high_hits:
                            logger.info(f"L1 static pattern detected injection: {[h['category'] for h in high_hits]}")
                            categories = list(set(h["category"] for h in high_hits))
                            security_result = SecurityResult(
                                risk_level="high_risk",
                                categories=[f"Prompt Injection ({c})" for c in categories],
                            )
                            l1_pattern_detected = True
                        else:
                            logger.info(f"L1 static pattern partial match (medium): {[h['category'] for h in pattern_hits]}")
                except Exception as e:
                    logger.warning(f"L1 static pattern check failed (fail-open): {e}")

            # 3. Prepare messages for model detection (must happen before parallel tasks)
            from utils.image_utils import image_utils

            messages_dict = []
            has_image = False
            saved_image_paths = []

            for msg in truncated_messages:
                content = msg.content
                if isinstance(content, str):
                    messages_dict.append({"role": msg.role, "content": content})
                elif isinstance(content, list):
                    content_parts = []
                    for part in content:
                        if hasattr(part, 'type'):
                            if part.type == 'text' and hasattr(part, 'text'):
                                content_parts.append({"type": "text", "text": part.text})
                            elif part.type == 'image_url' and hasattr(part, 'image_url'):
                                has_image = True
                                original_url = part.image_url.url
                                processed_url, saved_path = image_utils.process_image_url(original_url, tenant_id)
                                if saved_path:
                                    saved_image_paths.append(saved_path)
                                content_parts.append({"type": "image_url", "image_url": {"url": processed_url}})
                    messages_dict.append({"role": msg.role, "content": content_parts})

            # 4. Three-way parallel detection with early short-circuit
            # - Prompt Guard (~15ms): prompt injection detection, always-on
            # - Qwen3Guard (~200ms): S1-S21 risk classification + E1-E4 HTML scanning
            # - DLP (~50-500ms): data leakage detection (regex + GenAI)
            # If any path detects high_risk, return immediately; others continue in background for logging.

            import asyncio

            # Initialize results (preserve L1 security_result if already set)
            compliance_result = ComplianceResult(risk_level="no_risk", categories=[])
            if not l1_pattern_detected:
                security_result = SecurityResult(risk_level="no_risk", categories=[])
            data_result = None
            data_anonymized_text = None
            matched_scanner_tags = []
            matched_scanners = []
            sensitivity_score = None
            model_response = None
            prompt_guard_categories = []

            # --- Task A: Prompt Guard (fastest, ~15ms) ---
            async def _run_prompt_guard():
                if detection_direction != "input":
                    return False, []
                try:
                    from plugins_builtin.basic_guard.prompt_guard_service import prompt_injection_service
                    user_msgs = [{"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)}
                                 for m in truncated_messages if m.role == "user"]
                    if not user_msgs:
                        return False, []
                    is_injection, details = await prompt_injection_service.check_messages(
                        messages=user_msgs, threshold=0.5, scan_user=True, scan_system=False,
                    )
                    logger.info(f"Prompt Guard raw result: is_injection={is_injection}, details={[{k: v for k, v in d.items() if k != 'content_preview'} for d in details]}")
                    if is_injection:
                        detected = False
                        categories = []
                        for d in details:
                            if not d.get("is_injection"):
                                continue
                            label = d.get("label", "")
                            scores = d.get("scores", {})
                            # v2 model: MALICIOUS label / ProtectAI: INJECTION label
                            if label in ("MALICIOUS", "INJECTION"):
                                categories.append("Prompt Injection")
                                detected = True
                            # v1 model: only trust JAILBREAK with high confidence
                            elif label == "JAILBREAK" and scores.get("JAILBREAK", 0) > 0.9:
                                categories.append("Prompt Injection (Jailbreak)")
                                detected = True
                        if detected:
                            logger.info(f"Prompt Guard detected: {categories}")
                            return True, categories
                    return False, []
                except Exception as e:
                    logger.warning(f"Prompt Guard detection failed (fail-open): {e}")
                    return False, []

            # --- Task B: Qwen3Guard model detection (S1-S21 + HTML E1-E4) ---
            async def _run_model_detection():
                _matched_scanner_tags = []
                _matched_scanners = []
                _sensitivity_score = None
                _model_response = None

                if application_id:
                    try:
                        from services.scanner_detection_service import ScannerDetectionService
                        from uuid import UUID
                        scanner_db = get_db_session()
                        try:
                            scanner_service = ScannerDetectionService(scanner_db)
                            scan_type = 'response' if truncated_messages and truncated_messages[-1].role == 'assistant' else 'prompt'
                            logger.info(f"Using scanner detection for application {application_id}, scan_type={scan_type}")
                            detection_result = await scanner_service.execute_detection(
                                content=user_content,
                                application_id=UUID(application_id),
                                tenant_id=tenant_id,
                                scan_type=scan_type,
                                messages_for_genai=messages_dict
                            )
                            if detection_result.overall_risk_level == "no_risk":
                                _comp = ComplianceResult(risk_level="no_risk", categories=[])
                                _sec = SecurityResult(risk_level="no_risk", categories=[])
                            else:
                                compliance_risk = detection_result.overall_risk_level if detection_result.compliance_categories else "no_risk"
                                security_risk = detection_result.overall_risk_level if detection_result.security_categories else "no_risk"
                                _comp = ComplianceResult(risk_level=compliance_risk, categories=detection_result.compliance_categories)
                                _sec = SecurityResult(risk_level=security_risk, categories=detection_result.security_categories)
                            _matched_scanner_tags = detection_result.matched_scanner_tags
                            _matched_scanners = detection_result.matched_scanners
                            _model_response = "scanner_detection"
                            logger.info(f"Scanner detection complete: risk={detection_result.overall_risk_level}, matched_tags={_matched_scanner_tags}")
                            return _comp, _sec, _matched_scanner_tags, _matched_scanners, _sensitivity_score, _model_response
                        finally:
                            scanner_db.close()
                    except Exception as scanner_error:
                        logger.error(f"Scanner detection failed, falling back to legacy detection: {scanner_error}")

                # Legacy detection (no application_id or scanner failed)
                if not application_id:
                    logger.warning(f"No application_id provided, using legacy detection for tenant {tenant_id}")
                _matched_scanners = []
                _model_response, _sensitivity_score = await model_service.check_messages_with_sensitivity(messages_dict, use_vl_model=has_image)
                _comp, _sec = await self._parse_model_response_with_sensitivity(
                    _model_response, _sensitivity_score, tenant_id, model_sensitivity_trigger_level, application_id
                )
                return _comp, _sec, _matched_scanner_tags, _matched_scanners, _sensitivity_score, _model_response

            # --- Task C: DLP data leakage detection ---
            async def _run_dlp():
                try:
                    return await self._check_data_security(
                        content_for_data_detection, tenant_id,
                        direction=detection_direction, application_id=application_id
                    )
                except Exception as e:
                    logger.error(f"DLP detection failed: {e}")
                    return None, None

            # --- Task D: HTML content scan (conditional: only if input contains HTML) ---
            _has_html = detection_direction == "input" and (
                "<html" in user_content.lower() or "<!doctype" in user_content.lower()
                or ("<!--" in user_content and "</" in user_content)
            )

            async def _run_html_scan():
                if not _has_html:
                    return None
                try:
                    from services.content_scan_service import content_scan_service
                    result = await content_scan_service.scan_webpage(user_content)
                    if result.get("risk_level") in ("high", "medium"):
                        risk_types = result.get("risk_types", [])
                        logger.info(f"Content scan detected risks in HTML input: {risk_types}")
                        return SecurityResult(
                            risk_level="high_risk",
                            categories=[rt.replace("_", " ").title() for rt in risk_types]
                        )
                    return None
                except Exception as e:
                    logger.warning(f"Content scan enhancement failed: {e}")
                    return None

            # Launch all tasks in parallel (skip if L1 static pattern already detected high-risk)
            if l1_pattern_detected:
                # L1 already set security_result to high_risk, still run DLP for data protection
                dlp_result = await _run_dlp()
                data_result, data_anonymized_text = dlp_result
                logger.info("L1 static pattern short-circuit: skipping ML detection, DLP still runs")
            else:
                pg_task = asyncio.ensure_future(_run_prompt_guard())
                model_task = asyncio.ensure_future(_run_model_detection())
                dlp_task = asyncio.ensure_future(_run_dlp())
                html_task = asyncio.ensure_future(_run_html_scan()) if _has_html else None

                # Prompt Guard is fastest (~15ms). Wait for it first for early short-circuit.
                pg_is_injection, prompt_guard_categories = await pg_task
                if pg_is_injection:
                    security_result = SecurityResult(risk_level="high_risk", categories=prompt_guard_categories)
                    # Short-circuit: return early, let others finish in background for logging
                    try:
                        if model_task.done():
                            model_result = model_task.result()
                            compliance_result = model_result[0]
                            matched_scanner_tags = model_result[2]
                            matched_scanners = model_result[3]
                            sensitivity_score = model_result[4]
                            model_response = model_result[5]
                        if dlp_task.done():
                            data_result, data_anonymized_text = dlp_task.result()
                    except Exception:
                        pass

                    # Fire-and-forget: let remaining tasks complete for logging
                    bg_tasks = [model_task, dlp_task]
                    if html_task:
                        bg_tasks.append(html_task)

                    async def _collect_background():
                        try:
                            await asyncio.gather(*bg_tasks, return_exceptions=True)
                        except Exception:
                            pass
                    asyncio.ensure_future(_collect_background())

                    logger.info(f"Short-circuit: Prompt Guard detected injection, returning early")
                else:
                    # No injection detected by Prompt Guard, wait for all tasks
                    wait_tasks = [model_task, dlp_task]
                    if html_task:
                        wait_tasks.append(html_task)
                    results = await asyncio.gather(*wait_tasks)

                    model_result = results[0]
                    dlp_result = results[1]
                    html_result = results[2] if html_task else None

                    compliance_result_model, security_result_model, matched_scanner_tags, matched_scanners, sensitivity_score, model_response = model_result
                    data_result, data_anonymized_text = dlp_result

                    # Use model detection results
                    compliance_result = compliance_result_model
                    security_result = security_result_model

                    # Merge HTML scan result if it found risks
                    if html_result:
                        risk_order = {'no_risk': 0, 'low_risk': 1, 'medium_risk': 2, 'high_risk': 3}
                        if risk_order.get(html_result.risk_level, 0) > risk_order.get(security_result.risk_level, 0):
                            security_result.categories.extend(html_result.categories)
                            security_result = SecurityResult(
                                risk_level=html_result.risk_level,
                                categories=security_result.categories
                            )

            # 5.5 Plugin detection hooks (detection phase)
            hallucination_result = None
            plugin_results_dict = {}
            if application_id:
                try:
                    from plugins.registry import plugin_registry
                    from plugins.hooks import HookContext, HookPhase
                    messages_as_dicts = [{"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)} for m in truncated_messages]
                    # Extract assistant content for output-direction checks
                    assistant_content = ""
                    for msg in reversed(truncated_messages):
                        if msg.role == "assistant":
                            assistant_content = msg.content if isinstance(msg.content, str) else str(msg.content)
                            break
                    hook_ctx = HookContext(
                        phase=HookPhase.DETECTION,
                        request_id=request_id,
                        tenant_id=str(tenant_id) if tenant_id else "",
                        application_id=str(application_id),
                        messages=messages_as_dicts,
                        content=assistant_content or user_content,
                        detection_direction=detection_direction,
                    )
                    plugin_hook_results = await plugin_registry.dispatch_hook(HookPhase.DETECTION, hook_ctx)
                    for pr in plugin_hook_results:
                        plugin_results_dict[pr.plugin_name] = {
                            "risk_level": pr.risk_level,
                            "categories": pr.categories,
                            "action": pr.action,
                            "metadata": pr.metadata,
                        }
                        # Backward compat: populate hallucination_result if hallucination plugin returned
                        if pr.plugin_name == "hallucination_detection" and pr.risk_level != "no_risk":
                            from models.responses import HallucinationResult
                            hallucination_result = HallucinationResult(
                                risk_level=pr.risk_level,
                                categories=pr.categories,
                                groundedness_score=pr.metadata.get("groundedness_score"),
                                consistency_score=pr.metadata.get("consistency_score"),
                                flagged_claims=pr.metadata.get("flagged_claims", []),
                            )
                except Exception as e:
                    logger.error(f"Plugin detection hook error: {e}")

            # 5.6 Agent safety: reasoning content audit (via extra_body)
            # Run reasoning_content through the scanner detection pipeline
            reasoning_content = None
            if request.extra_body:
                reasoning_content = request.extra_body.get('reasoning_content')
            if reasoning_content and reasoning_content.strip() and application_id:
                try:
                    logger.info(f"Reasoning content audit: running scanner detection on reasoning_content ({len(reasoning_content)} chars)")
                    from services.scanner_detection_service import ScannerDetectionService
                    from uuid import UUID
                    reasoning_scanner_db = get_db_session()
                    try:
                        reasoning_scanner_service = ScannerDetectionService(reasoning_scanner_db)
                        reasoning_messages_for_genai = [{"role": "user", "content": reasoning_content}]
                        reasoning_detection_result = await reasoning_scanner_service.execute_detection(
                            content=reasoning_content,
                            application_id=UUID(application_id),
                            tenant_id=tenant_id,
                            scan_type="prompt",
                            messages_for_genai=reasoning_messages_for_genai
                        )
                        logger.info(f"Reasoning content scanner result: risk={reasoning_detection_result.overall_risk_level}, tags={reasoning_detection_result.matched_scanner_tags}")
                        if reasoning_detection_result.overall_risk_level != "no_risk":
                            reasoning_categories = []
                            if reasoning_detection_result.compliance_categories:
                                reasoning_categories.extend(reasoning_detection_result.compliance_categories)
                            if reasoning_detection_result.security_categories:
                                reasoning_categories.extend(reasoning_detection_result.security_categories)
                            plugin_results_dict["agent_safety_reasoning"] = {
                                "risk_level": reasoning_detection_result.overall_risk_level,
                                "categories": reasoning_categories,
                                "action": "block",
                                "metadata": {"source": "reasoning_content_safety_audit", "matched_tags": reasoning_detection_result.matched_scanner_tags},
                            }
                            logger.info(f"Reasoning content safety audit: risk={reasoning_detection_result.overall_risk_level}, categories={reasoning_categories}")
                        else:
                            logger.info(f"Reasoning content safety audit: no risk detected")
                    finally:
                        reasoning_scanner_db.close()
                except Exception as e:
                    logger.error(f"Reasoning content safety audit failed: {e}", exc_info=True)

            # 6. Determine suggested action and answer (include data security result)
            overall_risk_level, suggest_action, suggest_answer = await self._determine_action_with_data(
                compliance_result, security_result, data_result, tenant_id, application_id, user_content, data_anonymized_text, matched_scanners
            )

            # 6.0.1 Incorporate plugin risk into overall assessment
            risk_order = {'no_risk': 0, 'low_risk': 1, 'medium_risk': 2, 'high_risk': 3}
            for pr_name, pr_data in plugin_results_dict.items():
                pr_risk = pr_data.get("risk_level", "no_risk")
                if risk_order.get(pr_risk, 0) > risk_order.get(overall_risk_level, 0):
                    overall_risk_level = pr_risk
                if pr_data.get("action") == "block":
                    suggest_action = 'reject'
                    suggest_answer = suggest_answer or pr_data.get("metadata", {}).get("blocked_message", "Content blocked by plugin.")

            # 6.1 Append appeal link if applicable (any risk level with reject/replace action)
            if suggest_answer and suggest_action in ['reject', 'replace']:
                try:
                    from services.appeal_service import appeal_service
                    # Get tenant's language preference for appeal page
                    appeal_language = 'zh'  # Default to Chinese
                    if tenant_id:
                        try:
                            from database.models import Tenant
                            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
                            if tenant and tenant.language:
                                appeal_language = tenant.language
                        except Exception:
                            pass
                    appeal_link = await appeal_service.generate_appeal_link(
                        request_id=request_id,
                        application_id=application_id,
                        language=appeal_language
                    )
                    if appeal_link:
                        suggest_answer = f"{suggest_answer}\n\n{appeal_link}"
                except Exception as e:
                    logger.warning(f"Failed to generate appeal link: {e}")

            # 7. Asynchronously record detection results to log file (not write to database)
            await self._log_detection_result(
                request_id, user_content, compliance_result, security_result, data_result,
                suggest_action, suggest_answer, model_response,
                ip_address, user_agent, tenant_id, application_id, sensitivity_score,
                has_image=has_image, image_count=len(saved_image_paths), image_paths=saved_image_paths,
                matched_scanner_tags=matched_scanner_tags,
                hallucination_result=hallucination_result,
            )

            # 8. Construct response
            result = GuardrailResult(
                compliance=compliance_result,
                security=security_result,
                data=data_result,
                hallucination=hallucination_result,
                plugin_results=plugin_results_dict if plugin_results_dict else None,
            )

            return GuardrailResponse(
                id=request_id,
                result=result,
                overall_risk_level=overall_risk_level,
                suggest_action=suggest_action,
                suggest_answer=suggest_answer,
                score=sensitivity_score,
            )
            
        except Exception as e:
            logger.error(f"Guardrail check error: {e}")
            # When an error occurs, return safe default response
            return await self._handle_error(request_id, user_content, str(e), tenant_id, application_id)
    
    def _extract_user_content(self, messages: List[Message]) -> str:
        """Extract complete conversation content

        For data leak detection:
        - If last message is assistant (QA pair), extract assistant's response only
        - Otherwise extract user's content

        For logging: always include full conversation context
        """
        if len(messages) == 1 and messages[0].role == 'user':
            content = messages[0].content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # For multi-modal content, only extract text part for log
                text_parts = []
                for part in content:
                    if hasattr(part, 'type') and part.type == 'text' and hasattr(part, 'text'):
                        text_parts.append(part.text)
                    elif hasattr(part, 'type') and part.type == 'image_url':
                        text_parts.append("[Image]")
                return ' '.join(text_parts) if text_parts else "[Multi-modal content]"
        else:
            # Multi-message conversation
            conversation_parts = []
            for msg in messages:
                role_label = "User" if msg.role == "user" else "Assistant" if msg.role == "assistant" else msg.role
                content = msg.content
                if isinstance(content, str):
                    conversation_parts.append(f"[{role_label}]: {content}")
                elif isinstance(content, list):
                    # For multi-modal content, only extract text part
                    text_parts = []
                    for part in content:
                        if hasattr(part, 'type') and part.type == 'text' and hasattr(part, 'text'):
                            text_parts.append(part.text)
                        elif hasattr(part, 'type') and part.type == 'image_url':
                            text_parts.append("[Image]")
                    content_str = ' '.join(text_parts) if text_parts else "[多模态内容]"
                    conversation_parts.append(f"[{role_label}]: {content_str}")
            return '\n'.join(conversation_parts)

    def _extract_content_for_data_detection(self, messages: List[Message], direction: str) -> str:
        """Extract content for data leak detection based on direction

        Args:
            messages: List of messages
            direction: "input" for user input, "output" for assistant output

        Returns:
            Text content to be checked for data leaks
        """
        if direction == "output":
            # For output detection, only check assistant messages
            assistant_parts = []
            for msg in messages:
                if msg.role == "assistant":
                    content = msg.content
                    if isinstance(content, str):
                        assistant_parts.append(content)
                    elif isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if hasattr(part, 'type') and part.type == 'text' and hasattr(part, 'text'):
                                text_parts.append(part.text)
                        if text_parts:
                            assistant_parts.append(' '.join(text_parts))
            return '\n'.join(assistant_parts) if assistant_parts else ""
        else:
            # For input detection, check user messages
            user_parts = []
            for msg in messages:
                if msg.role == "user":
                    content = msg.content
                    if isinstance(content, str):
                        user_parts.append(content)
                    elif isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if hasattr(part, 'type') and part.type == 'text' and hasattr(part, 'text'):
                                text_parts.append(part.text)
                        if text_parts:
                            user_parts.append(' '.join(text_parts))
            return '\n'.join(user_parts) if user_parts else ""
    
    async def _parse_model_response(self, response: str, tenant_id: Optional[str] = None) -> Tuple[ComplianceResult, SecurityResult]:
        """Parse model response and apply risk type filtering"""
        response = response.strip()

        if response == "safe":
            return (
                ComplianceResult(risk_level="no_risk", categories=[]),
                SecurityResult(risk_level="no_risk", categories=[])
            )

        if response.startswith("unsafe\n"):
            category = response.split('\n')[1] if '\n' in response else ""

            # Check if tenant/application has disabled this risk type
            # Note: This method is deprecated and only used for backward compatibility
            # Modern code should use _parse_model_response_with_sensitivity which accepts application_id
            if tenant_id and not await risk_config_cache.is_risk_type_enabled(tenant_id=tenant_id, risk_type=category):
                logger.info(f"Risk type {category} is disabled for user {tenant_id}, treating as safe")
                return (
                    ComplianceResult(risk_level="no_risk", categories=[]),
                    SecurityResult(risk_level="no_risk", categories=[])
                )

            risk_level = RISK_LEVEL_MAPPING.get(category, "medium_risk")
            category_name = CATEGORY_NAMES.get(category, category)

            if category == "S9":  # Prompt injection
                return (
                    ComplianceResult(risk_level="no_risk", categories=[]),
                    SecurityResult(risk_level=risk_level, categories=[category_name])
                )
            else:  # Compliance issues
                return (
                    ComplianceResult(risk_level=risk_level, categories=[category_name]),
                    SecurityResult(risk_level="no_risk", categories=[])
                )

        # Default return safe
        return (
            ComplianceResult(risk_level="no_risk", categories=[]),
            SecurityResult(risk_level="no_risk", categories=[])
        )

    async def _parse_model_response_with_sensitivity(
        self, response: str, sensitivity_score: Optional[float], tenant_id: Optional[str] = None,
        model_sensitivity_trigger_level: Optional[str] = None, application_id: Optional[str] = None
    ) -> Tuple[ComplianceResult, SecurityResult]:
        """Parse model response and apply risk type filtering and sensitivity threshold

        Supports multiple labels separated by commas (e.g., "unsafe\nS2,S5,S7")

        Args:
            response: Model response string
            sensitivity_score: Sensitivity score from model
            tenant_id: Tenant ID (deprecated, kept for backward compatibility)
            model_sensitivity_trigger_level: Sensitivity trigger level override
            application_id: Application ID (preferred for risk config lookup)
        """
        response = response.strip()

        if response == "safe":
            return (
                ComplianceResult(risk_level="no_risk", categories=[]),
                SecurityResult(risk_level="no_risk", categories=[])
            )

        if response.startswith("unsafe\n"):
            categories_line = response.split('\n')[1] if '\n' in response else ""
            # Split by comma to support multiple labels
            categories = [cat.strip() for cat in categories_line.split(',') if cat.strip()]

            if not categories:
                return (
                    ComplianceResult(risk_level="no_risk", categories=[]),
                    SecurityResult(risk_level="no_risk", categories=[])
                )

            # Filter out disabled risk types, but only if ALL labels are disabled
            # Use application_id if available, otherwise fallback to tenant_id
            enabled_categories = []
            for category in categories:
                is_enabled = await risk_config_cache.is_risk_type_enabled(
                    tenant_id=tenant_id,
                    application_id=application_id,
                    risk_type=category
                )
                if is_enabled:
                    enabled_categories.append(category)

            # If all categories are disabled, treat as safe
            if not enabled_categories:
                cache_key = application_id if application_id else tenant_id
                logger.info(f"All risk types {categories} are disabled for application/user {cache_key}, treating as safe")
                return (
                    ComplianceResult(risk_level="no_risk", categories=[]),
                    SecurityResult(risk_level="no_risk", categories=[])
                )

            # Check sensitivity trigger level (apply to all enabled categories)
            if sensitivity_score is not None and (tenant_id or application_id):
                if not await self._should_trigger_detection(sensitivity_score, tenant_id, application_id):
                    logger.info(f"Sensitivity score {sensitivity_score} below current threshold for {enabled_categories}, treating as safe")
                    return (
                        ComplianceResult(risk_level="no_risk", categories=[]),
                        SecurityResult(risk_level="no_risk", categories=[])
                    )

            # Determine highest risk level from enabled categories
            risk_priority = {"no_risk": 0, "low_risk": 1, "medium_risk": 2, "high_risk": 3}

            # Separate security (S9) from compliance categories
            security_categories = []
            compliance_categories = []

            for category in enabled_categories:
                category_name = CATEGORY_NAMES.get(category, category)
                if category == "S9":  # Prompt Attacks
                    security_categories.append(category_name)
                else:
                    compliance_categories.append(category_name)

            # Determine risk levels for each type
            security_risk_level = "no_risk"
            compliance_risk_level = "no_risk"

            if security_categories:
                # Get highest risk level for security categories
                for category in enabled_categories:
                    if category == "S9":
                        risk_level = RISK_LEVEL_MAPPING.get(category, "medium_risk")
                        if risk_priority[risk_level] > risk_priority[security_risk_level]:
                            security_risk_level = risk_level

            if compliance_categories:
                # Get highest risk level for compliance categories
                for category in enabled_categories:
                    if category != "S9":
                        risk_level = RISK_LEVEL_MAPPING.get(category, "medium_risk")
                        if risk_priority[risk_level] > risk_priority[compliance_risk_level]:
                            compliance_risk_level = risk_level

            return (
                ComplianceResult(risk_level=compliance_risk_level, categories=compliance_categories),
                SecurityResult(risk_level=security_risk_level, categories=security_categories)
            )

        # Default return safe
        return (
            ComplianceResult(risk_level="no_risk", categories=[]),
            SecurityResult(risk_level="no_risk", categories=[])
        )
    
    async def _check_data_security(self, text: str, tenant_id: Optional[str], direction: str = "input", application_id: Optional[str] = None) -> Tuple[DataSecurityResult, Optional[str]]:
        """Check data security and return anonymized text

        Returns:
            Tuple of (DataSecurityResult, anonymized_text)
        """
        logger.info(f"_check_data_security called for user {tenant_id}, application {application_id}, direction {direction}")
        if not tenant_id:
            logger.info("No tenant_id, returning safe")
            return DataSecurityResult(risk_level="no_risk", categories=[]), None

        try:
            # Get database session
            db = get_db_session()
            try:
                from services.data_security_service import DataSecurityService
                service = DataSecurityService(db)

                # Execute data security detection
                logger.info(f"Calling detect_sensitive_data for text: {text[:50]}...")
                result = await service.detect_sensitive_data(text, tenant_id, direction, application_id=application_id)
                logger.info(f"Data security detection result: {result}")

                # Return both result and anonymized text
                anonymized_text = result.get('anonymized_text') if result['risk_level'] != 'no_risk' else None
                detected_entities = result.get('detected_entities', []) if result['risk_level'] != 'no_risk' else []
                restore_mapping = result.get('restore_mapping') if result['risk_level'] != 'no_risk' else None

                data_result = DataSecurityResult(
                    risk_level=result['risk_level'],
                    categories=result['categories'],
                    detected_entities=detected_entities,
                    anonymized_text=anonymized_text,
                    restore_mapping=restore_mapping
                )

                return data_result, anonymized_text
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Data security check error: {e}", exc_info=True)
            return DataSecurityResult(risk_level="no_risk", categories=[]), None

    def _get_highest_risk_level(self, categories: List[str]) -> str:
        """Get highest risk level"""
        if not categories:
            return "no_risk"

        risk_levels = []
        for category in categories:
            for code, name in CATEGORY_NAMES.items():
                if name == category:
                    risk_levels.append(RISK_LEVEL_MAPPING[code])
                    break

        if "high_risk" in risk_levels:
            return "high_risk"
        elif "medium_risk" in risk_levels:
            return "medium_risk"
        elif "low_risk" in risk_levels:
            return "low_risk"
        else:
            return "no_risk"

    async def _determine_action_with_data(
        self,
        compliance_result: ComplianceResult,
        security_result: SecurityResult,
        data_result: DataSecurityResult,
        tenant_id: Optional[str] = None,
        application_id: Optional[str] = None,
        user_query: Optional[str] = None,
        data_anonymized_text: Optional[str] = None,
        matched_scanners: Optional[list] = None
    ) -> Tuple[str, str, Optional[str]]:
        """Determine suggested action (include data security detection result)

        Important:
        - For general risks (security + compliance), use template/KB answer
        - For DLP risks, use fixed i18n message (not anonymized text)
        - overall_risk_level considers all three types for logging purposes
        - suggest_action is based on the highest risk from general risks
        - DLP disposal is handled separately in proxy layer
        """
        # Collect all categories for general risks only (not DLP)
        all_categories = []

        if compliance_result.risk_level != "no_risk":
            all_categories.extend(compliance_result.categories)
        if security_result.risk_level != "no_risk":
            all_categories.extend(security_result.categories)

        # Determine general risk level (security + compliance only, NOT DLP)
        general_risk_levels = [compliance_result.risk_level, security_result.risk_level]
        general_risk_level = "no_risk"
        for level in ["high_risk", "medium_risk", "low_risk"]:
            if level in general_risk_levels:
                general_risk_level = level
                break

        # Determine overall risk level (including DLP for logging purposes)
        all_risk_levels = [compliance_result.risk_level, security_result.risk_level, data_result.risk_level]
        overall_risk_level = "no_risk"
        for level in ["high_risk", "medium_risk", "low_risk"]:
            if level in all_risk_levels:
                overall_risk_level = level
                break

        # If no risks at all, pass
        if overall_risk_level == "no_risk":
            return overall_risk_level, "pass", None

        # Determine suggest_answer based on risk type
        suggest_answer = None

        # Case 1: Has general risk (security/compliance) - use template/KB answer
        if general_risk_level != "no_risk":
            suggest_answer = await self._get_suggest_answer(all_categories, tenant_id, application_id, user_query, matched_scanners)
            logger.info(f"Using template answer for general risk: {general_risk_level}")

        # Case 2: Only DLP risk (no general risk) - use data leakage template with entity types
        elif data_result.risk_level != "no_risk":
            # Get user's language preference for i18n
            user_language = 'en'  # Default to English
            if tenant_id:
                try:
                    from database.models import Tenant
                    db = get_db_session()
                    try:
                        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                        if tenant and tenant.language:
                            user_language = tenant.language
                    finally:
                        db.close()
                except Exception as e:
                    logger.warning(f"Failed to get user language for DLP message: {e}")

            # Use data leakage template with detected entity type names (not codes)
            from services.enhanced_template_service import enhanced_template_service
            # Extract entity_type_name from detected_entities for user-friendly display
            entity_type_names = []
            if data_result.detected_entities:
                seen_names = set()
                for entity in data_result.detected_entities:
                    name = entity.get('entity_type_name') or entity.get('entity_type', '')
                    if name and name not in seen_names:
                        entity_type_names.append(name)
                        seen_names.add(name)
            # Fallback to categories (codes) if no entity_type_name available
            if not entity_type_names:
                entity_type_names = data_result.categories if data_result.categories else []
            suggest_answer = await enhanced_template_service.get_data_leakage_answer(entity_type_names, user_language, application_id)
            logger.info(f"Using data leakage template for DLP risk: {data_result.risk_level}, entity_type_names={entity_type_names}")

        # Determine action based on general risk level (DLP handling is done in proxy layer)
        if general_risk_level == "high_risk":
            return overall_risk_level, "reject", suggest_answer
        elif general_risk_level == "medium_risk":
            return overall_risk_level, "replace", suggest_answer
        elif general_risk_level == "low_risk":
            # Low risk content is allowed through — log only, do not block or replace.
            # This reduces over-refusal on benign content near the boundary.
            return overall_risk_level, "pass", None
        else:
            # Only DLP risk, no general risk - action depends on DLP policy (handled in proxy)
            # Return "pass" for suggest_action, actual DLP disposal is in proxy layer
            return overall_risk_level, "pass", suggest_answer

    async def _determine_action(self, compliance_result: ComplianceResult, security_result: SecurityResult, tenant_id: Optional[str] = None, application_id: Optional[str] = None, user_query: Optional[str] = None, matched_scanners: Optional[list] = None) -> Tuple[str, str, Optional[str]]:
        """Determine suggested action"""
        overall_risk_level = "no_risk"
        risk_categories = []

        if compliance_result.risk_level != "no_risk":
            overall_risk_level = compliance_result.risk_level
            risk_categories.extend(compliance_result.categories)

        if security_result.risk_level != "no_risk":
            if overall_risk_level == "no_risk" or (overall_risk_level != "high_risk" and security_result.risk_level == "high_risk"):
                overall_risk_level = security_result.risk_level
            risk_categories.extend(security_result.categories)

        if overall_risk_level == "no_risk":
            return overall_risk_level, "pass", None
        elif overall_risk_level == "high_risk":
            suggest_answer = await self._get_suggest_answer(risk_categories, tenant_id, application_id, user_query, matched_scanners)
            return overall_risk_level, "reject", suggest_answer
        elif overall_risk_level == "medium_risk":
            suggest_answer = await self._get_suggest_answer(risk_categories, tenant_id, application_id, user_query, matched_scanners)
            return overall_risk_level, "replace", suggest_answer
        else:  # low_risk
            suggest_answer = await self._get_suggest_answer(risk_categories, tenant_id, application_id, user_query, matched_scanners)
            return overall_risk_level, "replace", suggest_answer
    
    async def _get_suggest_answer(self, categories: List[str], tenant_id: Optional[str] = None, application_id: Optional[str] = None, user_query: Optional[str] = None, matched_scanners: Optional[list] = None) -> str:
        """Get suggested answer (using enhanced template service, support knowledge base search)"""
        from services.enhanced_template_service import enhanced_template_service
        from database.models import Tenant

        # Get user's language preference
        user_language = None
        if tenant_id:
            try:
                db = get_db_session()
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                if tenant:
                    user_language = tenant.language
                db.close()
            except Exception as e:
                logger.warning(f"Failed to get user language for tenant {tenant_id}: {e}")

        # Extract scanner information from matched scanners (use highest risk scanner)
        scanner_type = None
        scanner_identifier = None
        scanner_name = None
        
        if matched_scanners and len(matched_scanners) > 0:
            # Use the first matched scanner (highest priority)
            first_scanner = matched_scanners[0]
            scanner_type = "official_scanner"  # All scanners in new system are official_scanner type
            scanner_identifier = first_scanner.scanner_tag  # Use scanner tag as identifier (e.g., S8, S100)
            scanner_name = first_scanner.scanner_name  # Human-readable name for template variable
            logger.info(f"Using scanner info for answer matching: type={scanner_type}, identifier={scanner_identifier}, name={scanner_name}")
        elif categories:
            # Fallback: use first category as scanner_name
            scanner_name = categories[0]
            logger.debug(f"No matched_scanners provided, using first category as scanner_name: {scanner_name}")

        return await enhanced_template_service.get_suggest_answer(
            categories,
            tenant_id=tenant_id,
            application_id=application_id,
            user_query=user_query,
            user_language=user_language,
            scanner_type=scanner_type,
            scanner_identifier=scanner_identifier,
            scanner_name=scanner_name
        )



    async def _get_sensitivity_trigger_level(self, tenant_id: str = None, application_id: str = None) -> str:
        """Get user/application configured sensitivity trigger level"""
        try:
            from services.risk_config_cache import risk_config_cache
            trigger_level = await risk_config_cache.get_sensitivity_trigger_level(tenant_id=tenant_id, application_id=application_id)
            return trigger_level if trigger_level else "medium"  # Default medium sensitivity trigger
        except Exception as e:
            cache_key = application_id if application_id else tenant_id
            logger.warning(f"Failed to get sensitivity trigger level for {cache_key}: {e}")
            return "medium"  # Default medium sensitivity trigger

    async def _should_trigger_detection(self, sensitivity_score: float, tenant_id: str = None, application_id: str = None) -> bool:
        """Check if should trigger detection based on sensitivity score and current sensitivity level threshold"""
        try:
            # Get user/application current sensitivity level
            current_level = await self._get_sensitivity_trigger_level(tenant_id, application_id)

            # Get sensitivity threshold configuration
            thresholds = await risk_config_cache.get_sensitivity_thresholds(tenant_id=tenant_id, application_id=application_id)

            # Get corresponding threshold based on current sensitivity level
            if current_level == "low":
                threshold = thresholds.get("low", 0.95)
            elif current_level == "medium":
                threshold = thresholds.get("medium", 0.60)
            elif current_level == "high":
                threshold = thresholds.get("high", 0.40)
            else:
                threshold = 0.60  # Default medium sensitivity threshold

            # Trigger when sensitivity score >= current sensitivity threshold
            return sensitivity_score >= threshold

        except Exception as e:
            cache_key = application_id if application_id else tenant_id
            logger.warning(f"Failed to check sensitivity trigger for {cache_key}: {e}")
            # Default use medium sensitivity threshold
            return sensitivity_score >= 0.60
    
    async def _handle_blacklist_hit(
        self, request_id: str, content: str, list_name: str,
        keywords: List[str], ip_address: Optional[str], user_agent: Optional[str],
        tenant_id: Optional[str] = None,
        application_id: Optional[str] = None
    ) -> GuardrailResponse:
        """Handle blacklist hit"""

        # Get user's language preference
        user_language = 'en'  # Default to English
        if tenant_id:
            try:
                from database.models import Tenant
                db = get_db_session()
                try:
                    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                    if tenant and tenant.language:
                        user_language = tenant.language
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Failed to get user language for tenant {tenant_id}: {e}")

        # Use enhanced template service to get blacklist response (supports custom templates and knowledge base)
        from services.enhanced_template_service import enhanced_template_service
        suggest_answer = await enhanced_template_service.get_suggest_answer(
            categories=[],  # Blacklist doesn't use legacy categories
            tenant_id=tenant_id,
            application_id=application_id,
            user_query=content,  # User's original input for KB search
            user_language=user_language,
            scanner_type='blacklist',  # Scanner type
            scanner_identifier=list_name,  # Blacklist name
            scanner_name=list_name  # For {scanner_name} variable replacement
        )

        detection_data = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "application_id": application_id,
            "content": content,
            "suggest_action": "reject",
            "suggest_answer": suggest_answer,
            "hit_keywords": json.dumps(keywords),
            "model_response": "blacklist_hit",
            "ip_address": ip_address,
            "user_agent": user_agent,
            "security_risk_level": "no_risk",
            "security_categories": [],
            "compliance_risk_level": "high_risk",
            "compliance_categories": [list_name],
            "data_risk_level": "no_risk",
            "data_categories": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await async_detection_logger.log_detection(detection_data)

        return GuardrailResponse(
            id=request_id,
            result=GuardrailResult(
                compliance=ComplianceResult(risk_level="high_risk", categories=[list_name]),
                security=SecurityResult(risk_level="no_risk", categories=[]),
                data=DataSecurityResult(risk_level="no_risk", categories=[])
            ),
            overall_risk_level="high_risk",
            suggest_action="reject",
            suggest_answer=suggest_answer
        )

    async def _handle_whitelist_hit(
        self, request_id: str, content: str, list_name: str,
        keywords: List[str], ip_address: Optional[str], user_agent: Optional[str],
        tenant_id: Optional[str] = None,
        application_id: Optional[str] = None
    ) -> GuardrailResponse:
        """Handle whitelist hit"""

        detection_data = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "application_id": application_id,
            "content": content,
            "suggest_action": "pass",
            "suggest_answer": None,
            "hit_keywords": json.dumps(keywords),
            "model_response": "whitelist_hit",
            "ip_address": ip_address,
            "user_agent": user_agent,
            "security_risk_level": "no_risk",
            "security_categories": [],
            "compliance_risk_level": "no_risk",
            "compliance_categories": [],
            "data_risk_level": "no_risk",
            "data_categories": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await async_detection_logger.log_detection(detection_data)

        return GuardrailResponse(
            id=request_id,
            result=GuardrailResult(
                compliance=ComplianceResult(risk_level="no_risk", categories=[]),
                security=SecurityResult(risk_level="no_risk", categories=[]),
                data=DataSecurityResult(risk_level="no_risk", categories=[])
            ),
            overall_risk_level="no_risk",
            suggest_action="pass",
            suggest_answer=None
        )

    async def _log_detection_result(
        self, request_id: str, content: str, compliance_result: ComplianceResult,
        security_result: SecurityResult, data_result: DataSecurityResult,
        suggest_action: str, suggest_answer: Optional[str],
        model_response: str, ip_address: Optional[str], user_agent: Optional[str],
        tenant_id: Optional[str] = None, application_id: Optional[str] = None,
        sensitivity_score: Optional[float] = None,
        has_image: bool = False, image_count: int = 0, image_paths: List[str] = None,
        matched_scanner_tags: List[str] = None,
        agent_safety_result: Optional[AgentSafetyResult] = None,
        hallucination_result: Optional[HallucinationResult] = None
    ):
        """Asynchronously record detection results to log file (not write to database)"""

        # Clean NUL characters from content
        from utils.validators import clean_null_characters

        detection_data = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "application_id": application_id,
            "content": clean_null_characters(content) if content else content,
            "suggest_action": suggest_action,
            "suggest_answer": clean_null_characters(suggest_answer) if suggest_answer else suggest_answer,
            "model_response": clean_null_characters(model_response) if model_response else model_response,
            "ip_address": ip_address,
            "user_agent": clean_null_characters(user_agent) if user_agent else user_agent,
            "security_risk_level": security_result.risk_level,
            "security_categories": security_result.categories,
            "compliance_risk_level": compliance_result.risk_level,
            "compliance_categories": compliance_result.categories,
            "data_risk_level": data_result.risk_level,
            "data_categories": data_result.categories,
            "sensitivity_score": sensitivity_score,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hit_keywords": None,
            "has_image": has_image,
            "image_count": image_count,
            "image_paths": image_paths or [],
            "matched_scanner_tags": matched_scanner_tags or [],
            # Agent safety detection results
            "agent_safety_risk_level": agent_safety_result.risk_level if agent_safety_result else "no_risk",
            "agent_safety_categories": agent_safety_result.categories if agent_safety_result else [],
            # Hallucination detection results
            "hallucination_risk_level": hallucination_result.risk_level if hallucination_result else "no_risk",
            "hallucination_categories": hallucination_result.categories if hallucination_result else [],
            "groundedness_score": hallucination_result.groundedness_score if hallucination_result else None,
            "consistency_score": hallucination_result.consistency_score if hallucination_result else None,
        }
        await async_detection_logger.log_detection(detection_data)
    
    async def _handle_error(self, request_id: str, content: str, error: str, tenant_id: Optional[str] = None, application_id: Optional[str] = None) -> GuardrailResponse:
        """Handle error situation — fail-close: block content when detection system fails."""

        detection_data = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "application_id": application_id,
            "content": content,
            "suggest_action": "block",
            "suggest_answer": None,
            "model_response": f"error: {error}",
            "security_risk_level": "error",
            "security_categories": ["detection_system_error"],
            "compliance_risk_level": "error",
            "compliance_categories": [],
            "data_risk_level": "error",
            "data_categories": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hit_keywords": None,
            "ip_address": None,
            "user_agent": None
        }
        await async_detection_logger.log_detection(detection_data)

        logger.warning(f"Fail-close: blocking request {request_id} due to detection error: {error}")

        return GuardrailResponse(
            id=request_id,
            result=GuardrailResult(
                compliance=ComplianceResult(risk_level="error", categories=[]),
                security=SecurityResult(risk_level="error", categories=["detection_system_error"]),
                data=DataSecurityResult(risk_level="error", categories=[])
            ),
            overall_risk_level="error",
            suggest_action="block",
            suggest_answer="Security detection system temporarily unavailable. Request blocked for safety."
        )
# 创建全局实例
detection_guardrail_service = DetectionGuardrailService()
