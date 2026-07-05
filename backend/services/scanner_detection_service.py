"""
Scanner Detection Service - New scanner package system detection logic

This service executes detection using the new scanner package system,
supporting three scanner types:
- GenAI: Uses Qwen3Guard-Gen-8B model for intelligent detection
- Regex: Python regex pattern matching
- Keyword: Case-insensitive keyword matching

Sliding Window Support:
- For long content that exceeds MAX_DETECTION_CONTEXT_LENGTH, the service
  uses a sliding window approach to ensure complete coverage.
- User-only messages: Sliding window on user content
- User+Assistant messages: Cross-detection between user windows and assistant windows
"""

import asyncio  # fcg-rewrite
from typing import List, Dict, Tuple, Optional, Any  # fcg-rewrite
from uuid import UUID  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from config import settings  # fcg-rewrite
from services.scanner_pattern_executor import ScannerPatternExecutor  # fcg-rewrite
from services.scanner_response_parser import ScannerResponseParser, drop_think_tags  # fcg-rewrite
from services.scanner_config_service import ScannerConfigService  # fcg-rewrite
from services.scanner_policy import uses_compact_definition  # fcg-rewrite
from services.scanner_windowing import SlidingWindowProcessor  # fcg-rewrite
from services.model_service import model_service, get_guard_client, UpstreamModelError  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
sliding_window_processor = SlidingWindowProcessor()  # fcg-rewrite


class ScannerDetectionResult:  # fcg-rewrite
    """Single scanner detection result"""
    def __init__(self, scanner_tag: str, scanner_name: str, scanner_type: str,  # fcg-rewrite
                 risk_level: str, matched: bool, match_details: Optional[str] = None):  # fcg-rewrite
        self.scanner_tag = scanner_tag  # fcg-rewrite
        self.scanner_name = scanner_name  # fcg-rewrite
        self.scanner_type = scanner_type  # fcg-rewrite
        self.risk_level = risk_level  # fcg-rewrite
        self.matched = matched  # fcg-rewrite
        self.match_details = match_details  # fcg-rewrite


class AggregatedDetectionResult:  # fcg-rewrite
    """Aggregated detection result from all scanners"""
    def __init__(self, overall_risk_level: str, matched_scanners: List[ScannerDetectionResult],  # fcg-rewrite
                 compliance_categories: List[str], security_categories: List[str]):  # fcg-rewrite
        self.overall_risk_level = overall_risk_level  # fcg-rewrite
        self.matched_scanners = matched_scanners  # fcg-rewrite
        self.compliance_categories = compliance_categories  # fcg-rewrite
        self.security_categories = security_categories  # fcg-rewrite
        self.matched_scanner_tags = [s.scanner_tag for s in matched_scanners]  # fcg-rewrite


class ScannerDetectionService:  # fcg-rewrite
    """
    Scanner-based detection service

    Replaces the old hardcoded S1-S21 risk type detection logic with
    a flexible scanner system that supports:
    - Built-in scanners (migrated from S1-S21)
    - Purchased scanners (from marketplace)
    - Custom scanners (user-defined S100+)
    """

    def __init__(self, db: Session):  # fcg-rewrite
        self.db = db  # fcg-rewrite
        self.scanner_config_service = ScannerConfigService(db)  # fcg-rewrite
        self.response_parser = ScannerResponseParser()  # fcg-rewrite
        self.pattern_executor = ScannerPatternExecutor()  # fcg-rewrite

    async def execute_detection(  # fcg-rewrite
        self,
        content: str,  # fcg-rewrite
        application_id: UUID,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        scan_type: str = 'prompt',  # 'prompt' or 'response'  # fcg-rewrite
        messages_for_genai: Optional[List[Dict]] = None  # fcg-rewrite
    ) -> AggregatedDetectionResult:  # fcg-rewrite
        """
        Execute detection using enabled scanners for the application

        Args:
            content: Text content to check
            application_id: Application UUID
            tenant_id: Tenant ID (UUID string)
            scan_type: 'prompt' or 'response' (determines which scanners to use)
            messages_for_genai: Full message context for GenAI scanners (optional)

        Returns:
            AggregatedDetectionResult with all matched scanners and overall risk
        """
        logger.info(f"Executing scanner detection for app {application_id}, scan_type={scan_type}")  # fcg-rewrite

        # 1. Get ONLY enabled scanners for this application and scan type
        # Disabled scanners should not be sent to the model at all
        all_scanners = self.scanner_config_service.get_application_scanners(  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            tenant_id=UUID(tenant_id),  # fcg-rewrite
            include_disabled=False  # Only get enabled scanners  # fcg-rewrite
        )

        # Filter by scan type
        if scan_type == 'prompt':  # fcg-rewrite
            scanners_for_scan_type = [s for s in all_scanners if s['scan_prompt']]  # fcg-rewrite
        elif scan_type == 'response':  # fcg-rewrite
            scanners_for_scan_type = [s for s in all_scanners if s['scan_response']]  # fcg-rewrite
        else:
            scanners_for_scan_type = all_scanners  # fcg-rewrite

        if not scanners_for_scan_type:  # fcg-rewrite
            logger.info(f"No scanners for app {application_id}, scan_type={scan_type}")  # fcg-rewrite
            return AggregatedDetectionResult(  # fcg-rewrite
                overall_risk_level="no_risk",  # fcg-rewrite
                matched_scanners=[],  # fcg-rewrite
                compliance_categories=[],  # fcg-rewrite
                security_categories=[]  # fcg-rewrite
            )

        # All scanners are now enabled, so no need to filter tags
        logger.info(f"Found {len(scanners_for_scan_type)} enabled scanners")  # fcg-rewrite

        # 2. Group scanners by type (all are enabled now)
        genai_scanners = [s for s in scanners_for_scan_type if s['scanner_type'] == 'genai']  # fcg-rewrite
        regex_scanners = [s for s in scanners_for_scan_type if s['scanner_type'] == 'regex']  # fcg-rewrite
        keyword_scanners = [s for s in scanners_for_scan_type if s['scanner_type'] == 'keyword']  # fcg-rewrite

        logger.info(f"Scanner types: GenAI={len(genai_scanners)}, Regex={len(regex_scanners)}, Keyword={len(keyword_scanners)}")  # fcg-rewrite

        # 3. Execute scanners in parallel where possible
        tasks: List[Any] = []  # fcg-rewrite

        if genai_scanners:  # fcg-rewrite
            tasks.append(self._execute_genai_scanners(  # fcg-rewrite
                genai_scanners, content, messages_for_genai  # fcg-rewrite
            ))

        if regex_scanners:  # fcg-rewrite
            tasks.append(asyncio.to_thread(self._execute_regex_scanners, regex_scanners, content))  # fcg-rewrite

        if keyword_scanners:  # fcg-rewrite
            tasks.append(asyncio.to_thread(self._execute_keyword_scanners, keyword_scanners, content))  # fcg-rewrite

        all_results: List[ScannerDetectionResult] = []  # fcg-rewrite
        if tasks:  # fcg-rewrite
            results_batches = await asyncio.gather(*tasks, return_exceptions=True)  # fcg-rewrite
            for batch in results_batches:  # fcg-rewrite
                if isinstance(batch, Exception):  # fcg-rewrite
                    logger.error(f"Scanner execution error: {batch}")  # fcg-rewrite
                    continue  # fcg-rewrite
                all_results.extend(batch)  # fcg-rewrite

        # 4. Aggregate results
        return self._aggregate_results(all_results)  # fcg-rewrite

    async def _execute_genai_scanners(  # fcg-rewrite
        self,
        scanners: List[Dict],  # fcg-rewrite
        content: str,  # fcg-rewrite
        messages: Optional[List[Dict]] = None  # fcg-rewrite
    ) -> List[ScannerDetectionResult]:  # fcg-rewrite
        """
        Execute GenAI scanners using Qwen3Guard-Gen-8B model

        Only enabled GenAI scanner definitions are sent to the model
        in a single call. No filtering needed since all are enabled.

        Supports sliding window for long content:
        - User-only: Slide window on user content
        - User+Assistant: Cross-detect user windows × assistant windows

        Args:
            scanners: List of enabled GenAI scanner configs only
            content: Content to check
            messages: Full message context (preferred over content)

        Returns:
            List of ScannerDetectionResult
        """
        logger.info(f"Executing {len(scanners)} enabled GenAI scanners")  # fcg-rewrite

        try:
            # Prepare scanner definitions for model - send only enabled scanners
            scanner_definitions = self._prepare_scanner_definitions(scanners)  # fcg-rewrite

            # Use messages if provided, otherwise wrap content as message
            if messages is None:  # fcg-rewrite
                messages = [{"role": "user", "content": content}]  # fcg-rewrite

            # Check if messages contain images
            has_image = self._check_has_image(messages)  # fcg-rewrite

            # Guard model routing: determine which model to use
            routing_decision = self._get_routing_decision(  # fcg-rewrite
                content, messages, [s['tag'] for s in scanners]  # fcg-rewrite
            )

            # Apply sliding window if content exceeds max context length
            message_windows = sliding_window_processor.get_message_windows(messages)  # fcg-rewrite

            if len(message_windows) == 1:  # fcg-rewrite
                # No sliding window needed - single detection
                return await self._execute_single_genai_detection(  # fcg-rewrite
                    scanners, scanner_definitions, message_windows[0], has_image,  # fcg-rewrite
                    routing_decision=routing_decision,  # fcg-rewrite
                )
            else:
                # Multiple windows - parallel detection and aggregate results
                logger.info(f"Executing sliding window detection with {len(message_windows)} windows")  # fcg-rewrite
                return await self._execute_sliding_window_detection(  # fcg-rewrite
                    scanners, scanner_definitions, message_windows, has_image,  # fcg-rewrite
                    routing_decision=routing_decision,  # fcg-rewrite
                )

        except Exception as e:  # fcg-rewrite
            logger.error(f"Error executing GenAI scanners (fail-close): {e}")  # fcg-rewrite
            # Fail-close: treat model errors as high risk to avoid silent bypass
            return [  # fcg-rewrite
                ScannerDetectionResult(  # fcg-rewrite
                    scanner_tag=s['tag'],  # fcg-rewrite
                    scanner_name=s['name'],  # fcg-rewrite
                    scanner_type='genai',  # fcg-rewrite
                    risk_level=s['risk_level'],  # fcg-rewrite
                    matched=True,  # fcg-rewrite
                    match_details=f"Model error (fail-close): {str(e)[:100]}"  # fcg-rewrite
                ) for s in scanners  # fcg-rewrite
            ]

    def _prepare_scanner_definitions(self, scanners: List[Dict]) -> List[str]:  # fcg-rewrite
        """
        Prepare scanner definitions for model.

        Args:
            scanners: List of scanner configs

        Returns:
            List of scanner definition strings
        """
        scanner_definitions = []  # fcg-rewrite

        for scanner in scanners:  # fcg-rewrite
            tag = scanner['tag']  # fcg-rewrite
            name = scanner['name']  # fcg-rewrite
            definition = scanner['definition']  # fcg-rewrite
            package_type = scanner.get('package_type', 'custom')  # fcg-rewrite

            # For basic/premium scanners: only send tag and name (model already knows the definition)
            # For custom scanners: send full definition
            if uses_compact_definition(package_type):  # fcg-rewrite
                scanner_def = f"{tag}: {name}"  # fcg-rewrite
            else:
                scanner_def = f"{tag}: {name}. {definition}"  # fcg-rewrite

            scanner_definitions.append(scanner_def)  # fcg-rewrite

        # Sort by tag number (e.g., S1, S2, ..., S19, S20, S21)
        def extract_tag_number(scanner_def: str) -> int:  # fcg-rewrite
            try:
                tag_part = scanner_def.split(':')[0].strip()  # fcg-rewrite
                if tag_part.startswith('S'):  # fcg-rewrite
                    return int(tag_part[1:])  # fcg-rewrite
                return 999999  # fcg-rewrite
            except (ValueError, IndexError):  # fcg-rewrite
                return 999999  # fcg-rewrite

        scanner_definitions.sort(key=extract_tag_number)  # fcg-rewrite
        return scanner_definitions  # fcg-rewrite

    def _get_routing_decision(self, content: str, messages: List[Dict], scanner_tags: List[str]):  # fcg-rewrite
        """Get guard model routing decision. Returns None if routing is disabled."""
        try:
            from services.guard_model_registry import get_guard_model_registry  # fcg-rewrite
            registry = get_guard_model_registry()  # fcg-rewrite
            if not registry.is_routing_enabled():  # fcg-rewrite
                return None  # fcg-rewrite

            from services.guard_router_service import GuardSelector, RoutingContext  # fcg-rewrite

            # Detect context signals for routing
            has_image = self._check_has_image(messages)  # fcg-rewrite
            has_tool_calls = any(  # fcg-rewrite
                msg.get("tool_calls") for msg in messages  # fcg-rewrite
            )

            router = GuardSelector(registry)  # fcg-rewrite
            ctx = RoutingContext(  # fcg-rewrite
                content=content,  # fcg-rewrite
                messages=messages,  # fcg-rewrite
                scanner_tags=scanner_tags,  # fcg-rewrite
                scan_type="prompt",  # fcg-rewrite
                has_image=has_image,  # fcg-rewrite
                has_tool_calls=has_tool_calls,  # fcg-rewrite
            )
            decision = router.route(ctx)  # fcg-rewrite
            if decision.rule_name not in ("disabled", "default"):  # fcg-rewrite
                logger.info(f"Guard router: model={decision.model_config.id}, "  # fcg-rewrite
                            f"rule={decision.rule_name}, reason={decision.reason}")  # fcg-rewrite
            return decision  # fcg-rewrite
        except Exception as e:  # fcg-rewrite
            logger.warning(f"Guard routing failed, using default model: {e}")  # fcg-rewrite
            return None  # fcg-rewrite

    def _check_has_image(self, messages: List[Dict]) -> bool:  # fcg-rewrite
        """Check if messages contain images."""
        for msg in messages:  # fcg-rewrite
            msg_content = msg.get("content")  # fcg-rewrite
            if isinstance(msg_content, list):  # fcg-rewrite
                for part in msg_content:  # fcg-rewrite
                    if isinstance(part, dict) and part.get("type") == "image_url":  # fcg-rewrite
                        return True  # fcg-rewrite
        return False  # fcg-rewrite

    async def _execute_single_genai_detection(  # fcg-rewrite
        self,
        scanners: List[Dict],  # fcg-rewrite
        scanner_definitions: List[str],  # fcg-rewrite
        messages: List[Dict],  # fcg-rewrite
        has_image: bool,  # fcg-rewrite
        routing_decision=None,  # fcg-rewrite
    ) -> List[ScannerDetectionResult]:  # fcg-rewrite
        """
        Execute a single GenAI detection call.

        Args:
            scanners: List of scanner configs
            scanner_definitions: Prepared scanner definitions
            messages: Messages to check
            has_image: Whether messages contain images
            routing_decision: Optional routing decision from guard router

        Returns:
            List of ScannerDetectionResult
        """
        # Try routed model first (if routing is active and not default)
        if routing_decision and routing_decision.rule_name not in ("disabled", "default"):  # fcg-rewrite
            guard_client = get_guard_client(routing_decision.model_config.id)  # fcg-rewrite
            if guard_client:  # fcg-rewrite
                try:
                    model_response, sensitivity_score = await guard_client.call_with_scanner_definitions(  # fcg-rewrite
                        messages=messages,  # fcg-rewrite
                        scanner_definitions=scanner_definitions,  # fcg-rewrite
                        use_vl_model=has_image,  # fcg-rewrite
                    )
                    logger.info(f"Routed model '{routing_decision.model_config.id}' response: "  # fcg-rewrite
                                f"{model_response}, sensitivity: {sensitivity_score}")  # fcg-rewrite
                    return self._parse_model_response(  # fcg-rewrite
                        scanners, model_response, sensitivity_score,  # fcg-rewrite
                        response_format=routing_decision.model_config.response_format,  # fcg-rewrite
                    )
                except UpstreamModelError as e:  # fcg-rewrite
                    logger.warning(f"Routed model '{routing_decision.model_config.id}' failed, "  # fcg-rewrite
                                   f"falling back to default: {e}")  # fcg-rewrite
                    # Fall through to default model below

        # Default path (unchanged from original)
        model_response, sensitivity_score = await model_service.check_messages_with_scanner_definitions(  # fcg-rewrite
            messages=messages,  # fcg-rewrite
            scanner_definitions=scanner_definitions,  # fcg-rewrite
            use_vl_model=has_image  # fcg-rewrite
        )

        logger.info(f"GenAI model response: {model_response}, sensitivity: {sensitivity_score}")  # fcg-rewrite
        return self._parse_model_response(scanners, model_response, sensitivity_score)  # fcg-rewrite

    async def _execute_sliding_window_detection(  # fcg-rewrite
        self,
        scanners: List[Dict],  # fcg-rewrite
        scanner_definitions: List[str],  # fcg-rewrite
        message_windows: List[List[Dict]],  # fcg-rewrite
        has_image: bool,  # fcg-rewrite
        routing_decision=None,  # fcg-rewrite
    ) -> List[ScannerDetectionResult]:  # fcg-rewrite
        """
        Execute sliding window detection with multiple windows.

        Runs all window detections in parallel and aggregates results.
        A scanner is considered matched if it matches in ANY window.

        Args:
            scanners: List of scanner configs
            scanner_definitions: Prepared scanner definitions
            message_windows: List of message windows to check
            has_image: Whether messages contain images
            routing_decision: Optional routing decision from guard router

        Returns:
            List of ScannerDetectionResult (aggregated from all windows)
        """
        # Create detection tasks for all windows with bounded concurrency
        semaphore = asyncio.Semaphore(settings.scanner_window_concurrency)  # fcg-rewrite

        async def bounded_detect(window_index: int, window_messages: List[Dict]):  # fcg-rewrite
            async with semaphore:  # fcg-rewrite
                return await self._detect_single_window(  # fcg-rewrite
                    window_index=window_index,  # fcg-rewrite
                    scanners=scanners,  # fcg-rewrite
                    scanner_definitions=scanner_definitions,  # fcg-rewrite
                    messages=window_messages,  # fcg-rewrite
                    has_image=has_image,  # fcg-rewrite
                    routing_decision=routing_decision,  # fcg-rewrite
                )

        tasks = [  # fcg-rewrite
            bounded_detect(i, window_messages)  # fcg-rewrite
            for i, window_messages in enumerate(message_windows)  # fcg-rewrite
        ]

        # Execute all windows in parallel
        window_results = await asyncio.gather(*tasks, return_exceptions=True)  # fcg-rewrite

        # Aggregate results from all windows
        return self._aggregate_window_results(scanners, window_results)  # fcg-rewrite

    async def _detect_single_window(  # fcg-rewrite
        self,
        window_index: int,  # fcg-rewrite
        scanners: List[Dict],  # fcg-rewrite
        scanner_definitions: List[str],  # fcg-rewrite
        messages: List[Dict],  # fcg-rewrite
        has_image: bool,  # fcg-rewrite
        routing_decision=None,  # fcg-rewrite
    ) -> Tuple[int, str, Optional[float]]:  # fcg-rewrite
        """
        Detect a single window and return raw response.

        Args:
            window_index: Index of this window
            scanners: List of scanner configs
            scanner_definitions: Prepared scanner definitions
            messages: Messages for this window
            has_image: Whether messages contain images
            routing_decision: Optional routing decision from guard router

        Returns:
            Tuple of (window_index, model_response, sensitivity_score)
        """
        try:
            # Try routed model first
            if routing_decision and routing_decision.rule_name not in ("disabled", "default"):  # fcg-rewrite
                guard_client = get_guard_client(routing_decision.model_config.id)  # fcg-rewrite
                if guard_client:  # fcg-rewrite
                    try:
                        model_response, sensitivity_score = await guard_client.call_with_scanner_definitions(  # fcg-rewrite
                            messages=messages,  # fcg-rewrite
                            scanner_definitions=scanner_definitions,  # fcg-rewrite
                            use_vl_model=has_image,  # fcg-rewrite
                        )
                        logger.debug(f"Window {window_index} routed to '{routing_decision.model_config.id}': "  # fcg-rewrite
                                     f"{model_response}, sensitivity: {sensitivity_score}")  # fcg-rewrite
                        return (window_index, model_response, sensitivity_score)  # fcg-rewrite
                    except UpstreamModelError as e:  # fcg-rewrite
                        logger.warning(f"Window {window_index} routed model failed, fallback: {e}")  # fcg-rewrite

            # Default path
            model_response, sensitivity_score = await model_service.check_messages_with_scanner_definitions(  # fcg-rewrite
                messages=messages,  # fcg-rewrite
                scanner_definitions=scanner_definitions,  # fcg-rewrite
                use_vl_model=has_image  # fcg-rewrite
            )
            logger.debug(f"Window {window_index} response: {model_response}, sensitivity: {sensitivity_score}")  # fcg-rewrite
            return (window_index, model_response, sensitivity_score)  # fcg-rewrite
        except Exception as e:  # fcg-rewrite
            logger.error(f"Error detecting window {window_index}: {e}")  # fcg-rewrite
            raise  # Fail-close: propagate error instead of silently passing  # fcg-rewrite

    def _aggregate_window_results(  # fcg-rewrite
        self,
        scanners: List[Dict],  # fcg-rewrite
        window_results: List[Any]  # fcg-rewrite
    ) -> List[ScannerDetectionResult]:  # fcg-rewrite
        return self.response_parser.aggregate_window_results(  # fcg-rewrite
            scanners, window_results, ScannerDetectionResult  # fcg-rewrite
        )

    def _parse_model_response(  # fcg-rewrite
        self,
        scanners: List[Dict],  # fcg-rewrite
        model_response: str,  # fcg-rewrite
        sensitivity_score: Optional[float],  # fcg-rewrite
        response_format: Optional[str] = None,  # fcg-rewrite
    ) -> List[ScannerDetectionResult]:  # fcg-rewrite
        return self.response_parser.parse_model_response(  # fcg-rewrite
            scanners,  # fcg-rewrite
            model_response,  # fcg-rewrite
            sensitivity_score,  # fcg-rewrite
            ScannerDetectionResult,  # fcg-rewrite
            response_format,  # fcg-rewrite
        )

    def _parse_generic_safe_unsafe(  # fcg-rewrite
        self,
        scanners: List[Dict],  # fcg-rewrite
        response: str,  # fcg-rewrite
        sensitivity_score: Optional[float],  # fcg-rewrite
    ) -> List[ScannerDetectionResult]:  # fcg-rewrite
        return self.response_parser.parse_generic_safe_unsafe(  # fcg-rewrite
            scanners, response, sensitivity_score, ScannerDetectionResult  # fcg-rewrite
        )

    def _try_parse_qwen3guard_format(self, response: str) -> Optional[Tuple[bool, List[str]]]:  # fcg-rewrite
        return self.response_parser.try_parse_qwen3guard_format(response)  # fcg-rewrite

    def _execute_regex_scanners(  # fcg-rewrite
        self,
        scanners: List[Dict],  # fcg-rewrite
        content: str  # fcg-rewrite
    ) -> List[ScannerDetectionResult]:  # fcg-rewrite
        return self.pattern_executor.execute_regex_scanners(  # fcg-rewrite
            scanners, content, ScannerDetectionResult  # fcg-rewrite
        )

    def _execute_keyword_scanners(  # fcg-rewrite
        self,
        scanners: List[Dict],  # fcg-rewrite
        content: str  # fcg-rewrite
    ) -> List[ScannerDetectionResult]:  # fcg-rewrite
        return self.pattern_executor.execute_keyword_scanners(  # fcg-rewrite
            scanners, content, ScannerDetectionResult  # fcg-rewrite
        )

    def _aggregate_results(  # fcg-rewrite
        self,
        scanner_results: List[ScannerDetectionResult]  # fcg-rewrite
    ) -> AggregatedDetectionResult:  # fcg-rewrite
        return self.pattern_executor.aggregate_results(  # fcg-rewrite
            scanner_results, AggregatedDetectionResult  # fcg-rewrite
        )
