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

import asyncio
import math
import re
from typing import List, Dict, Tuple, Optional, Any
from uuid import UUID
from sqlalchemy.orm import Session

from config import settings
from services.scanner_config_service import ScannerConfigService
from services.model_service import model_service, get_guard_client, ModelServiceError
from utils.logger import setup_logger
from utils.scanner_cache import get_compiled_regex, get_keyword_assets

logger = setup_logger()

# Pattern to strip <think>...</think> blocks from reasoning models (e.g. MiniMax M2.5)
_THINK_TAG_RE = re.compile(r'<think>.*?</think>', re.DOTALL)

def _strip_think_tags(text: str) -> str:
    """Strip <think>...</think> reasoning blocks from model output.

    Some models (e.g. MiniMax M2.5) wrap their reasoning in <think> tags
    before outputting the actual safe/unsafe classification. This function
    removes those blocks so the parser can find the classification.
    Also handles incomplete think blocks (no closing tag).
    """
    # Remove complete <think>...</think> blocks
    result = _THINK_TAG_RE.sub('', text)
    # Handle incomplete think block (model cut off mid-thinking)
    if '<think>' in result:
        result = result.split('<think>')[0]
    return result.strip()


class SlidingWindowProcessor:
    """
    Sliding window processor for long content detection.

    Handles two scenarios:
    1. User-only messages: Slide window on user content
    2. User+Assistant messages: Cross-detect user windows × assistant windows
    """

    def __init__(self, max_context_length: int = None):
        """
        Initialize sliding window processor.

        Args:
            max_context_length: Maximum context length for detection.
                               Defaults to settings.max_detection_context_length
        """
        self.max_context_length = max_context_length or settings.max_detection_context_length
        # Window overlap to avoid missing content at boundaries (20% overlap)
        self.overlap_ratio = 0.2
        self.max_windows = settings.scanner_window_max_windows
        self.max_pairs = settings.scanner_window_max_pairs

    def _downsample_windows(
        self,
        windows: List[Tuple[str, int, int]],
        target_count: int
    ) -> List[Tuple[str, int, int]]:
        """
        Downsample windows to a target count while preserving coverage.
        """
        if target_count <= 0 or len(windows) <= target_count:
            return windows

        step = len(windows) / target_count
        sampled = [windows[int(i * step)] for i in range(target_count)]

        # Ensure the last window is included for tail coverage
        if sampled and sampled[-1] != windows[-1]:
            sampled[-1] = windows[-1]

        return sampled

    def _create_windows(self, text: str, window_size: int) -> List[Tuple[str, int, int]]:
        """
        Create sliding windows for a text.

        Args:
            text: Text to create windows from
            window_size: Size of each window in characters

        Returns:
            List of (window_text, start_pos, end_pos) tuples
        """
        if not text or len(text) <= window_size:
            return [(text, 0, len(text))]

        windows = []
        step_size = int(window_size * (1 - self.overlap_ratio))  # 80% step, 20% overlap

        start = 0
        while start < len(text):
            end = min(start + window_size, len(text))
            window_text = text[start:end]
            windows.append((window_text, start, end))

            if end >= len(text):
                break
            start += step_size

        logger.info(f"Created {len(windows)} windows for text of length {len(text)} (window_size={window_size})")
        return windows

    def get_message_windows(
        self,
        messages: List[Dict]
    ) -> List[List[Dict]]:
        """
        Generate message window combinations for detection.

        Logic:
        - If only user messages: Create windows from user content
        - If user+assistant: Create cross-product of user windows × assistant windows
          (each user window paired with each assistant window)

        Args:
            messages: Original message list

        Returns:
            List of message lists, each representing one detection window
        """
        if not messages:
            return [[]]

        # Separate user and assistant messages
        user_messages = [m for m in messages if m.get("role") == "user"]
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]

        # Extract text content from messages
        def get_text_content(msg: Dict) -> str:
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Multimodal content - extract text parts
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                return " ".join(text_parts)
            return str(content)

        # Combine all user content and assistant content
        user_content = "\n".join(get_text_content(m) for m in user_messages)
        assistant_content = "\n".join(get_text_content(m) for m in assistant_messages)

        total_length = len(user_content) + len(assistant_content)

        # If total content fits in context, return original messages
        if total_length <= self.max_context_length:
            logger.debug(f"Content length {total_length} <= max {self.max_context_length}, no sliding window needed")
            return [messages]

        logger.info(f"Content length {total_length} > max {self.max_context_length}, applying sliding window")

        # Case 1: Only user messages
        if not assistant_messages:
            window_size = self.max_context_length
            user_windows = self._create_windows(user_content, window_size)
            if len(user_windows) > self.max_windows:
                user_windows = self._downsample_windows(user_windows, self.max_windows)
                logger.warning(
                    f"User windows capped to {len(user_windows)} (max {self.max_windows})"
                )

            result = []
            for window_text, start, end in user_windows:
                result.append([{"role": "user", "content": window_text}])

            logger.info(f"Created {len(result)} user-only windows")
            return result

        # Case 2: User + Assistant messages - cross-product detection
        # Each role gets half the context length
        half_context = self.max_context_length // 2

        user_windows = self._create_windows(user_content, half_context)
        assistant_windows = self._create_windows(assistant_content, half_context)

        # Cap per-role windows to avoid explosion
        if len(user_windows) > self.max_windows:
            user_windows = self._downsample_windows(user_windows, self.max_windows)
        if len(assistant_windows) > self.max_windows:
            assistant_windows = self._downsample_windows(assistant_windows, self.max_windows)

        # Cap cross-product size
        total_pairs = len(user_windows) * len(assistant_windows)
        if total_pairs > self.max_pairs:
            target_user = min(len(user_windows), max(1, int(math.sqrt(self.max_pairs))))
            target_assistant = min(len(assistant_windows), max(1, self.max_pairs // target_user))

            user_windows = self._downsample_windows(user_windows, target_user)
            assistant_windows = self._downsample_windows(assistant_windows, target_assistant)

            logger.warning(
                f"Window pairs capped from {total_pairs} to "
                f"{len(user_windows) * len(assistant_windows)} "
                f"(max {self.max_pairs})"
            )

        # Create cross-product: each user window × each assistant window
        result = []
        for user_text, u_start, u_end in user_windows:
            for asst_text, a_start, a_end in assistant_windows:
                # Create a message pair for this window combination
                window_messages = [
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": asst_text}
                ]
                result.append(window_messages)

        logger.info(f"Created {len(result)} cross-product windows ({len(user_windows)} user × {len(assistant_windows)} assistant)")
        return result


# Global sliding window processor instance
sliding_window_processor = SlidingWindowProcessor()


class ScannerDetectionResult:
    """Single scanner detection result"""
    def __init__(self, scanner_tag: str, scanner_name: str, scanner_type: str,
                 risk_level: str, matched: bool, match_details: Optional[str] = None):
        self.scanner_tag = scanner_tag
        self.scanner_name = scanner_name
        self.scanner_type = scanner_type
        self.risk_level = risk_level
        self.matched = matched
        self.match_details = match_details


class AggregatedDetectionResult:
    """Aggregated detection result from all scanners"""
    def __init__(self, overall_risk_level: str, matched_scanners: List[ScannerDetectionResult],
                 compliance_categories: List[str], security_categories: List[str]):
        self.overall_risk_level = overall_risk_level
        self.matched_scanners = matched_scanners
        self.compliance_categories = compliance_categories
        self.security_categories = security_categories
        self.matched_scanner_tags = [s.scanner_tag for s in matched_scanners]


class ScannerDetectionService:
    """
    Scanner-based detection service

    Replaces the old hardcoded S1-S21 risk type detection logic with
    a flexible scanner system that supports:
    - Built-in scanners (migrated from S1-S21)
    - Purchased scanners (from marketplace)
    - Custom scanners (user-defined S100+)
    """

    def __init__(self, db: Session):
        self.db = db
        self.scanner_config_service = ScannerConfigService(db)

    async def execute_detection(
        self,
        content: str,
        application_id: UUID,
        tenant_id: str,
        scan_type: str = 'prompt',  # 'prompt' or 'response'
        messages_for_genai: Optional[List[Dict]] = None
    ) -> AggregatedDetectionResult:
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
        logger.info(f"Executing scanner detection for app {application_id}, scan_type={scan_type}")

        # 1. Get ONLY enabled scanners for this application and scan type
        # Disabled scanners should not be sent to the model at all
        all_scanners = self.scanner_config_service.get_application_scanners(
            application_id=application_id,
            tenant_id=UUID(tenant_id),
            include_disabled=False  # Only get enabled scanners
        )

        # Filter by scan type
        if scan_type == 'prompt':
            scanners_for_scan_type = [s for s in all_scanners if s['scan_prompt']]
        elif scan_type == 'response':
            scanners_for_scan_type = [s for s in all_scanners if s['scan_response']]
        else:
            scanners_for_scan_type = all_scanners

        if not scanners_for_scan_type:
            logger.info(f"No scanners for app {application_id}, scan_type={scan_type}")
            return AggregatedDetectionResult(
                overall_risk_level="no_risk",
                matched_scanners=[],
                compliance_categories=[],
                security_categories=[]
            )

        # All scanners are now enabled, so no need to filter tags
        logger.info(f"Found {len(scanners_for_scan_type)} enabled scanners")

        # 2. Group scanners by type (all are enabled now)
        genai_scanners = [s for s in scanners_for_scan_type if s['scanner_type'] == 'genai']
        regex_scanners = [s for s in scanners_for_scan_type if s['scanner_type'] == 'regex']
        keyword_scanners = [s for s in scanners_for_scan_type if s['scanner_type'] == 'keyword']

        logger.info(f"Scanner types: GenAI={len(genai_scanners)}, Regex={len(regex_scanners)}, Keyword={len(keyword_scanners)}")

        # 3. Execute scanners in parallel where possible
        tasks: List[Any] = []

        if genai_scanners:
            tasks.append(self._execute_genai_scanners(
                genai_scanners, content, messages_for_genai
            ))

        if regex_scanners:
            tasks.append(asyncio.to_thread(self._execute_regex_scanners, regex_scanners, content))

        if keyword_scanners:
            tasks.append(asyncio.to_thread(self._execute_keyword_scanners, keyword_scanners, content))

        all_results: List[ScannerDetectionResult] = []
        if tasks:
            results_batches = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in results_batches:
                if isinstance(batch, Exception):
                    logger.error(f"Scanner execution error: {batch}")
                    continue
                all_results.extend(batch)

        # 4. Aggregate results
        return self._aggregate_results(all_results)

    async def _execute_genai_scanners(
        self,
        scanners: List[Dict],
        content: str,
        messages: Optional[List[Dict]] = None
    ) -> List[ScannerDetectionResult]:
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
        logger.info(f"Executing {len(scanners)} enabled GenAI scanners")

        try:
            # Prepare scanner definitions for model - send only enabled scanners
            scanner_definitions = self._prepare_scanner_definitions(scanners)

            # Use messages if provided, otherwise wrap content as message
            if messages is None:
                messages = [{"role": "user", "content": content}]

            # Check if messages contain images
            has_image = self._check_has_image(messages)

            # Guard model routing: determine which model to use
            routing_decision = self._get_routing_decision(
                content, messages, [s['tag'] for s in scanners]
            )

            # Apply sliding window if content exceeds max context length
            message_windows = sliding_window_processor.get_message_windows(messages)

            if len(message_windows) == 1:
                # No sliding window needed - single detection
                return await self._execute_single_genai_detection(
                    scanners, scanner_definitions, message_windows[0], has_image,
                    routing_decision=routing_decision,
                )
            else:
                # Multiple windows - parallel detection and aggregate results
                logger.info(f"Executing sliding window detection with {len(message_windows)} windows")
                return await self._execute_sliding_window_detection(
                    scanners, scanner_definitions, message_windows, has_image,
                    routing_decision=routing_decision,
                )

        except Exception as e:
            logger.error(f"Error executing GenAI scanners (fail-close): {e}")
            # Fail-close: treat model errors as high risk to avoid silent bypass
            return [
                ScannerDetectionResult(
                    scanner_tag=s['tag'],
                    scanner_name=s['name'],
                    scanner_type='genai',
                    risk_level=s['risk_level'],
                    matched=True,
                    match_details=f"Model error (fail-close): {str(e)[:100]}"
                ) for s in scanners
            ]

    def _prepare_scanner_definitions(self, scanners: List[Dict]) -> List[str]:
        """
        Prepare scanner definitions for model.

        Args:
            scanners: List of scanner configs

        Returns:
            List of scanner definition strings
        """
        scanner_definitions = []

        for scanner in scanners:
            tag = scanner['tag']
            name = scanner['name']
            definition = scanner['definition']
            package_type = scanner.get('package_type', 'custom')

            # For basic/premium scanners: only send tag and name (model already knows the definition)
            # For custom scanners: send full definition
            if package_type in ['basic', 'premium']:
                scanner_def = f"{tag}: {name}"
            else:
                scanner_def = f"{tag}: {name}. {definition}"

            scanner_definitions.append(scanner_def)

        # Sort by tag number (e.g., S1, S2, ..., S19, S20, S21)
        def extract_tag_number(scanner_def: str) -> int:
            try:
                tag_part = scanner_def.split(':')[0].strip()
                if tag_part.startswith('S'):
                    return int(tag_part[1:])
                return 999999
            except (ValueError, IndexError):
                return 999999

        scanner_definitions.sort(key=extract_tag_number)
        return scanner_definitions

    def _get_routing_decision(self, content: str, messages: List[Dict], scanner_tags: List[str]):
        """Get guard model routing decision. Returns None if routing is disabled."""
        try:
            from services.guard_model_registry import get_guard_model_registry
            registry = get_guard_model_registry()
            if not registry.is_routing_enabled():
                return None

            from services.guard_router_service import GuardRouterService, RoutingContext

            # Detect context signals for routing
            has_image = self._check_has_image(messages)
            has_tool_calls = any(
                msg.get("tool_calls") for msg in messages
            )

            router = GuardRouterService(registry)
            ctx = RoutingContext(
                content=content,
                messages=messages,
                scanner_tags=scanner_tags,
                scan_type="prompt",
                has_image=has_image,
                has_tool_calls=has_tool_calls,
            )
            decision = router.route(ctx)
            if decision.rule_name not in ("disabled", "default"):
                logger.info(f"Guard router: model={decision.model_config.id}, "
                            f"rule={decision.rule_name}, reason={decision.reason}")
            return decision
        except Exception as e:
            logger.warning(f"Guard routing failed, using default model: {e}")
            return None

    def _check_has_image(self, messages: List[Dict]) -> bool:
        """Check if messages contain images."""
        for msg in messages:
            msg_content = msg.get("content")
            if isinstance(msg_content, list):
                for part in msg_content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        return True
        return False

    async def _execute_single_genai_detection(
        self,
        scanners: List[Dict],
        scanner_definitions: List[str],
        messages: List[Dict],
        has_image: bool,
        routing_decision=None,
    ) -> List[ScannerDetectionResult]:
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
        if routing_decision and routing_decision.rule_name not in ("disabled", "default"):
            guard_client = get_guard_client(routing_decision.model_config.id)
            if guard_client:
                try:
                    model_response, sensitivity_score = await guard_client.call_with_scanner_definitions(
                        messages=messages,
                        scanner_definitions=scanner_definitions,
                        use_vl_model=has_image,
                    )
                    logger.info(f"Routed model '{routing_decision.model_config.id}' response: "
                                f"{model_response}, sensitivity: {sensitivity_score}")
                    return self._parse_model_response(
                        scanners, model_response, sensitivity_score,
                        response_format=routing_decision.model_config.response_format,
                    )
                except ModelServiceError as e:
                    logger.warning(f"Routed model '{routing_decision.model_config.id}' failed, "
                                   f"falling back to default: {e}")
                    # Fall through to default model below

        # Default path (unchanged from original)
        model_response, sensitivity_score = await model_service.check_messages_with_scanner_definitions(
            messages=messages,
            scanner_definitions=scanner_definitions,
            use_vl_model=has_image
        )

        logger.info(f"GenAI model response: {model_response}, sensitivity: {sensitivity_score}")
        return self._parse_model_response(scanners, model_response, sensitivity_score)

    async def _execute_sliding_window_detection(
        self,
        scanners: List[Dict],
        scanner_definitions: List[str],
        message_windows: List[List[Dict]],
        has_image: bool,
        routing_decision=None,
    ) -> List[ScannerDetectionResult]:
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
        semaphore = asyncio.Semaphore(settings.scanner_window_concurrency)

        async def bounded_detect(window_index: int, window_messages: List[Dict]):
            async with semaphore:
                return await self._detect_single_window(
                    window_index=window_index,
                    scanners=scanners,
                    scanner_definitions=scanner_definitions,
                    messages=window_messages,
                    has_image=has_image,
                    routing_decision=routing_decision,
                )

        tasks = [
            bounded_detect(i, window_messages)
            for i, window_messages in enumerate(message_windows)
        ]

        # Execute all windows in parallel
        window_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results from all windows
        return self._aggregate_window_results(scanners, window_results)

    async def _detect_single_window(
        self,
        window_index: int,
        scanners: List[Dict],
        scanner_definitions: List[str],
        messages: List[Dict],
        has_image: bool,
        routing_decision=None,
    ) -> Tuple[int, str, Optional[float]]:
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
            if routing_decision and routing_decision.rule_name not in ("disabled", "default"):
                guard_client = get_guard_client(routing_decision.model_config.id)
                if guard_client:
                    try:
                        model_response, sensitivity_score = await guard_client.call_with_scanner_definitions(
                            messages=messages,
                            scanner_definitions=scanner_definitions,
                            use_vl_model=has_image,
                        )
                        logger.debug(f"Window {window_index} routed to '{routing_decision.model_config.id}': "
                                     f"{model_response}, sensitivity: {sensitivity_score}")
                        return (window_index, model_response, sensitivity_score)
                    except ModelServiceError as e:
                        logger.warning(f"Window {window_index} routed model failed, fallback: {e}")

            # Default path
            model_response, sensitivity_score = await model_service.check_messages_with_scanner_definitions(
                messages=messages,
                scanner_definitions=scanner_definitions,
                use_vl_model=has_image
            )
            logger.debug(f"Window {window_index} response: {model_response}, sensitivity: {sensitivity_score}")
            return (window_index, model_response, sensitivity_score)
        except Exception as e:
            logger.error(f"Error detecting window {window_index}: {e}")
            raise  # Fail-close: propagate error instead of silently passing

    def _aggregate_window_results(
        self,
        scanners: List[Dict],
        window_results: List[Any]
    ) -> List[ScannerDetectionResult]:
        """
        Aggregate results from multiple windows.

        A scanner is matched if it matches in ANY window.
        Uses the highest sensitivity score among matched windows.

        Args:
            scanners: List of scanner configs
            window_results: List of (window_index, model_response, sensitivity_score) tuples

        Returns:
            Aggregated list of ScannerDetectionResult
        """
        # Track matched scanners and their best sensitivity scores
        matched_scanner_info = {}  # tag -> (matched, best_sensitivity, window_indices)

        for scanner in scanners:
            matched_scanner_info[scanner['tag']] = {
                'matched': False,
                'sensitivity': None,
                'windows': []
            }

        # Process each window result
        for result in window_results:
            if isinstance(result, Exception):
                logger.error(f"Window detection exception: {result}")
                continue

            window_index, model_response, sensitivity_score = result
            response = _strip_think_tags(model_response)

            if response.startswith("unsafe"):
                lines = [l.strip() for l in response.split('\n')[1:] if l.strip()]
                categories_line = lines[0] if lines else ""
                matched_tags = [tag.strip() for tag in categories_line.split(',') if tag.strip()]

                for tag in matched_tags:
                    if tag in matched_scanner_info:
                        info = matched_scanner_info[tag]
                        info['matched'] = True
                        info['windows'].append(window_index)
                        # Track best (highest) sensitivity score
                        if sensitivity_score is not None:
                            if info['sensitivity'] is None or sensitivity_score > info['sensitivity']:
                                info['sensitivity'] = sensitivity_score

        # Build final results
        results = []
        total_windows = len(window_results)

        for scanner in scanners:
            tag = scanner['tag']
            info = matched_scanner_info[tag]

            match_details = None
            if info['matched']:
                window_count = len(info['windows'])
                match_details = f"Matched in {window_count}/{total_windows} windows"
                if info['sensitivity'] is not None:
                    match_details += f", max sensitivity: {info['sensitivity']:.4f}"

            results.append(ScannerDetectionResult(
                scanner_tag=tag,
                scanner_name=scanner['name'],
                scanner_type='genai',
                risk_level=scanner['risk_level'],
                matched=info['matched'],
                match_details=match_details
            ))

        # Log summary
        matched_count = sum(1 for r in results if r.matched)
        logger.info(f"Sliding window aggregation: {matched_count} scanners matched across {total_windows} windows")

        return results

    # Mapping from Qwen3Guard category names to scanner tags
    QWEN3GUARD_CATEGORY_MAP = {
        # Jailbreak / Prompt injection
        "jailbreak": "S9",
        "prompt injection": "S9",
        "prompt attack": "S9",
        # Violence
        "violence": "S3",
        "violent crimes": "S3",
        "violent crime": "S3",
        # Sexual content
        "sexual content": "S7",
        "sexual": "S7",
        "pornography": "S7",
        # Hate speech
        "hate speech": "S8",
        "hate": "S8",
        "discrimination": "S8",
        # Self-harm
        "self-harm": "S16",
        "self harm": "S16",
        "suicide": "S16",
        # Minors safety
        "child safety": "S4",
        "harm to minors": "S4",
        "child abuse": "S4",
        "minors": "S4",
        # Weapons / WMD
        "weapons": "S5",
        "wmd": "S5",
        "weapons of mass destruction": "S5",
        # Politics
        "politics": "S2",
        "political": "S2",
        "sensitive political": "S2",
        # Non-violent crime
        "non-violent crime": "S6",
        "fraud": "S6",
        "crime": "S6",
        # Privacy
        "privacy": "S11",
        "personal information": "S11",
        "pii": "S11",
        # Professional advice
        "professional advice": "S19",
        "medical advice": "S19",
        "legal advice": "S19",
        # Threats
        "threats": "S18",
        "threat": "S18",
        # Harassment
        "harassment": "S17",
        "bullying": "S17",
        # Profanity
        "profanity": "S10",
        "offensive language": "S10",
        # Sexual crimes
        "sexual crimes": "S15",
        # IP / Copyright
        "intellectual property": "S13",
        "copyright": "S13",
        # Commercial
        "commercial": "S12",
    }

    def _parse_model_response(
        self,
        scanners: List[Dict],
        model_response: str,
        sensitivity_score: Optional[float],
        response_format: Optional[str] = None,
    ) -> List[ScannerDetectionResult]:
        """
        Parse model response into scanner results.
        Supports both Qwen3Guard-Gen-8B format ("safe"/"unsafe\nS2,S5")
        and Qwen3Guard format ("Safety: Controversial\nCategories: Jailbreak").

        When response_format is specified (from guard router), uses model-specific
        parsing. When None, uses existing auto-detection logic (backward compatible).

        Args:
            scanners: List of scanner configs
            model_response: Raw model response
            sensitivity_score: Sensitivity score from model

        Returns:
            List of ScannerDetectionResult
        """
        results = []
        response = _strip_think_tags(model_response)

        # Model-specific parsing for routed models
        if response_format in ("llamaguard4", "wildguard"):
            return self._parse_generic_safe_unsafe(scanners, response, sensitivity_score)

        # Try Qwen3Guard format: "Safety: X\nCategories: Y"
        qwen3guard_result = self._try_parse_qwen3guard_format(response)
        if qwen3guard_result is not None:
            is_safe, matched_tags = qwen3guard_result
            if is_safe:
                for scanner in scanners:
                    results.append(ScannerDetectionResult(
                        scanner_tag=scanner['tag'],
                        scanner_name=scanner['name'],
                        scanner_type='genai',
                        risk_level=scanner['risk_level'],
                        matched=False
                    ))
            else:
                logger.info(f"Qwen3Guard matched tags: {matched_tags}")
                for scanner in scanners:
                    tag = scanner['tag']
                    matched = tag in matched_tags
                    results.append(ScannerDetectionResult(
                        scanner_tag=tag,
                        scanner_name=scanner['name'],
                        scanner_type='genai',
                        risk_level=scanner['risk_level'],
                        matched=matched,
                        match_details=f"Sensitivity: {sensitivity_score}" if matched else None
                    ))
            return results

        # Qwen3Guard-Gen-8B format: "safe" or "unsafe\nS2,S5,S7"
        if response == "safe":
            for scanner in scanners:
                results.append(ScannerDetectionResult(
                    scanner_tag=scanner['tag'],
                    scanner_name=scanner['name'],
                    scanner_type='genai',
                    risk_level=scanner['risk_level'],
                    matched=False
                ))
        elif response.startswith("unsafe"):
            # Extract scanner tags from lines after "unsafe", skipping empty lines
            lines = [l.strip() for l in response.split('\n')[1:] if l.strip()]
            categories_line = lines[0] if lines else ""
            matched_tags = [tag.strip() for tag in categories_line.split(',') if tag.strip()]

            logger.info(f"Model returned matched tags: {matched_tags}")

            for scanner in scanners:
                tag = scanner['tag']
                matched = tag in matched_tags

                results.append(ScannerDetectionResult(
                    scanner_tag=tag,
                    scanner_name=scanner['name'],
                    scanner_type='genai',
                    risk_level=scanner['risk_level'],
                    matched=matched,
                    match_details=f"Sensitivity: {sensitivity_score}" if matched else None
                ))
        else:
            logger.warning(f"Unexpected model response format: {response}")
            for scanner in scanners:
                results.append(ScannerDetectionResult(
                    scanner_tag=scanner['tag'],
                    scanner_name=scanner['name'],
                    scanner_type='genai',
                    risk_level=scanner['risk_level'],
                    matched=False
                ))

        return results

    def _parse_generic_safe_unsafe(
        self,
        scanners: List[Dict],
        response: str,
        sensitivity_score: Optional[float],
    ) -> List[ScannerDetectionResult]:
        """Generic parser for models that output 'safe' or 'unsafe\\n<reason>'.

        Used for Llama Guard 4, WildGuard, and other models whose output doesn't
        include FangcunGuard S-tags. When 'unsafe' is detected, ALL enabled
        scanners are marked as matched (since we can't map to specific tags).
        """
        results = []
        lower = response.lower().strip()
        is_safe = lower.startswith("safe") and not lower.startswith("unsafe")

        for scanner in scanners:
            results.append(ScannerDetectionResult(
                scanner_tag=scanner['tag'],
                scanner_name=scanner['name'],
                scanner_type='genai',
                risk_level=scanner['risk_level'],
                matched=not is_safe,
                match_details=(f"External model flagged unsafe. "
                               f"Response: {response[:200]}" if not is_safe else None),
            ))

        if not is_safe:
            logger.info(f"External guard model flagged content as unsafe: {response[:200]}")

        return results

    def _try_parse_qwen3guard_format(self, response: str) -> Optional[Tuple[bool, List[str]]]:
        """
        Try to parse Qwen3Guard response format.
        Format: "Safety: Safe" or "Safety: Controversial\nCategories: Jailbreak, Violence"

        Returns:
            None if not Qwen3Guard format.
            (True, []) if safe.
            (False, [matched_scanner_tags]) if unsafe.
        """
        response_lower = response.lower().strip()

        # Check if it matches Qwen3Guard format
        if not response_lower.startswith("safety:"):
            return None

        lines = [l.strip() for l in response.split('\n') if l.strip()]

        # Parse safety level from first line
        safety_line = lines[0]
        safety_value = safety_line.split(":", 1)[1].strip().lower()

        if safety_value in ("safe", "controversial"):
            # Controversial = content is ambiguous/borderline, not clearly harmful.
            # Treat as safe to reduce false positives on educational/fictional content.
            return (True, [])

        # Unsafe — parse categories
        matched_tags = set()
        for line in lines[1:]:
            if line.lower().startswith("categories:"):
                categories_str = line.split(":", 1)[1].strip()
                categories = [c.strip().lower() for c in categories_str.split(",") if c.strip()]

                for category in categories:
                    # Direct mapping
                    if category in self.QWEN3GUARD_CATEGORY_MAP:
                        matched_tags.add(self.QWEN3GUARD_CATEGORY_MAP[category])
                    else:
                        # Fuzzy match: check if any key is contained in the category
                        for key, tag in self.QWEN3GUARD_CATEGORY_MAP.items():
                            if key in category or category in key:
                                matched_tags.add(tag)
                                break
                        else:
                            logger.info(f"Qwen3Guard category '{category}' has no scanner tag mapping, treating as S9 (default security)")
                            matched_tags.add("S9")

        return (False, list(matched_tags))

    def _execute_regex_scanners(
        self,
        scanners: List[Dict],
        content: str
    ) -> List[ScannerDetectionResult]:
        """
        Execute Regex scanners using Python re module

        Args:
            scanners: List of Regex scanner configs
            content: Content to check

        Returns:
            List of ScannerDetectionResult
        """
        logger.info(f"Executing {len(scanners)} Regex scanners")

        results = []
        max_samples = settings.scanner_match_sample_limit
        max_count = settings.scanner_regex_match_count_limit
        for scanner in scanners:
            tag = scanner['tag']
            name = scanner['name']
            pattern = scanner['definition']
            risk_level = scanner['risk_level']

            try:
                # Compile and search for pattern (cached)
                regex = get_compiled_regex(pattern)
                if regex is None:
                    raise ValueError("Invalid regex pattern")

                match_samples = []
                match_count = 0
                truncated = False

                for match in regex.finditer(content):
                    match_count += 1
                    if len(match_samples) < max_samples:
                        match_samples.append(match.group(0))
                    if match_count >= max_count:
                        truncated = True
                        break

                matched = match_count > 0
                match_details = None

                if matched:
                    count_display = f">={max_count}" if truncated else str(match_count)
                    match_details = f"Matched {count_display} times. Samples: {match_samples}"
                    logger.info(f"Regex scanner {tag} matched: {match_details}")

                results.append(ScannerDetectionResult(
                    scanner_tag=tag,
                    scanner_name=name,
                    scanner_type='regex',
                    risk_level=risk_level,
                    matched=matched,
                    match_details=match_details
                ))

            except ValueError as e:
                # Invalid regex pattern
                logger.error(f"Invalid regex pattern for scanner {tag}: {e}")
                results.append(ScannerDetectionResult(
                    scanner_tag=tag,
                    scanner_name=name,
                    scanner_type='regex',
                    risk_level=risk_level,
                    matched=False,
                    match_details=f"Error: Invalid regex pattern - {str(e)}"
                ))
            except Exception as e:
                # Other errors
                logger.error(f"Error executing regex scanner {tag}: {e}")
                results.append(ScannerDetectionResult(
                    scanner_tag=tag,
                    scanner_name=name,
                    scanner_type='regex',
                    risk_level=risk_level,
                    matched=False
                ))

        return results

    def _execute_keyword_scanners(
        self,
        scanners: List[Dict],
        content: str
    ) -> List[ScannerDetectionResult]:
        """
        Execute Keyword scanners using case-insensitive string search

        Args:
            scanners: List of Keyword scanner configs
            content: Content to check

        Returns:
            List of ScannerDetectionResult
        """
        logger.info(f"Executing {len(scanners)} Keyword scanners")

        # Convert content to lowercase for case-insensitive matching
        content_lower = content.lower()

        results = []
        max_samples = settings.scanner_match_sample_limit
        for scanner in scanners:
            tag = scanner['tag']
            name = scanner['name']
            keywords_str = scanner['definition']  # Comma-separated keywords
            risk_level = scanner['risk_level']

            try:
                keywords, keyword_regex = get_keyword_assets(keywords_str)

                if not keywords:
                    logger.warning(f"Keyword scanner {tag} has no valid keywords")
                    results.append(ScannerDetectionResult(
                        scanner_tag=tag,
                        scanner_name=name,
                        scanner_type='keyword',
                        risk_level=risk_level,
                        matched=False,
                        match_details="No valid keywords defined"
                    ))
                    continue

                matched_keywords = set()

                if keyword_regex:
                    for match in keyword_regex.finditer(content):
                        matched_keywords.add(match.group(0).lower())
                        if len(matched_keywords) >= max_samples:
                            break
                else:
                    for kw in keywords:
                        if kw in content_lower:
                            matched_keywords.add(kw)
                            if len(matched_keywords) >= max_samples:
                                break

                matched = len(matched_keywords) > 0
                match_details = None

                if matched:
                    # Limit to first N matched keywords
                    match_samples = list(matched_keywords)[:max_samples]
                    match_details = f"Matched keywords: {match_samples}"
                    logger.info(f"Keyword scanner {tag} matched: {match_details}")

                results.append(ScannerDetectionResult(
                    scanner_tag=tag,
                    scanner_name=name,
                    scanner_type='keyword',
                    risk_level=risk_level,
                    matched=matched,
                    match_details=match_details
                ))

            except Exception as e:
                logger.error(f"Error executing keyword scanner {tag}: {e}")
                results.append(ScannerDetectionResult(
                    scanner_tag=tag,
                    scanner_name=name,
                    scanner_type='keyword',
                    risk_level=risk_level,
                    matched=False
                ))

        return results

    def _aggregate_results(
        self,
        scanner_results: List[ScannerDetectionResult]
    ) -> AggregatedDetectionResult:
        """
        Aggregate scanner results and determine overall risk level

        Args:
            scanner_results: List of all scanner results

        Returns:
            AggregatedDetectionResult
        """
        # Filter matched scanners
        matched_scanners = [r for r in scanner_results if r.matched]

        if not matched_scanners:
            logger.info("No scanners matched - content is safe")
            return AggregatedDetectionResult(
                overall_risk_level="no_risk",
                matched_scanners=[],
                compliance_categories=[],
                security_categories=[]
            )

        logger.info(f"{len(matched_scanners)} scanners matched")

        # Determine highest risk level
        risk_priority = {"no_risk": 0, "low_risk": 1, "medium_risk": 2, "high_risk": 3}
        overall_risk_level = "no_risk"

        for scanner in matched_scanners:
            scanner_risk = scanner.risk_level
            if risk_priority[scanner_risk] > risk_priority[overall_risk_level]:
                overall_risk_level = scanner_risk

        # Separate security (S9 = Prompt Attacks) from compliance categories
        security_categories = []
        compliance_categories = []

        for scanner in matched_scanners:
            if scanner.scanner_tag == "S9":
                security_categories.append(scanner.scanner_name)
            else:
                compliance_categories.append(scanner.scanner_name)

        logger.info(f"Overall risk: {overall_risk_level}, Compliance: {len(compliance_categories)}, Security: {len(security_categories)}")

        return AggregatedDetectionResult(
            overall_risk_level=overall_risk_level,
            matched_scanners=matched_scanners,
            compliance_categories=compliance_categories,
            security_categories=security_categories
        )
