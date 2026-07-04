import httpx  # fcg-rewrite
import time  # fcg-rewrite
from typing import List, Tuple, Optional  # fcg-rewrite
from config import settings  # fcg-rewrite
from services.model_message_formatter import ModelMessageFormatter  # fcg-rewrite
from services.model_response_parser import ModelResponseParser  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite


class UpstreamModelError(Exception):  # fcg-rewrite
    """Raised when the model service is unavailable or returns an error.
    Callers must handle this to enforce fail-close semantics."""
    pass


class FailFastBreaker:  # fcg-rewrite
    """Simple circuit breaker: after N consecutive failures, open the circuit
    and fail fast for a cooldown period before allowing a retry."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0):  # fcg-rewrite
        self._failure_threshold = failure_threshold  # fcg-rewrite
        self._cooldown = cooldown_seconds  # fcg-rewrite
        self._failure_count = 0  # fcg-rewrite
        self._last_failure_time = 0.0  # fcg-rewrite
        self._state = "closed"  # closed | open | half_open  # fcg-rewrite

    def record_success(self):  # fcg-rewrite
        self._failure_count = 0  # fcg-rewrite
        self._state = "closed"  # fcg-rewrite

    def record_failure(self):  # fcg-rewrite
        self._failure_count += 1  # fcg-rewrite
        self._last_failure_time = time.time()  # fcg-rewrite
        if self._failure_count >= self._failure_threshold:  # fcg-rewrite
            self._state = "open"  # fcg-rewrite
            logger.warning(f"Circuit breaker OPEN after {self._failure_count} consecutive failures. "  # fcg-rewrite
                           f"Requests will fail fast for {self._cooldown}s.")  # fcg-rewrite

    def allow_request(self) -> bool:  # fcg-rewrite
        if self._state == "closed":  # fcg-rewrite
            return True  # fcg-rewrite
        if self._state == "open":  # fcg-rewrite
            if time.time() - self._last_failure_time >= self._cooldown:  # fcg-rewrite
                self._state = "half_open"  # fcg-rewrite
                logger.info("Circuit breaker half-open: allowing probe request")  # fcg-rewrite
                return True  # fcg-rewrite
            return False  # fcg-rewrite
        # half_open: allow one probe
        return True  # fcg-rewrite

    @property  # fcg-rewrite
    def is_open(self) -> bool:  # fcg-rewrite
        return self._state == "open" and (time.time() - self._last_failure_time < self._cooldown)  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

class UpstreamModelClient:  # fcg-rewrite
    """Model service class"""

    def __init__(self):  # fcg-rewrite
        # Circuit breaker: open after 5 consecutive failures, cooldown 30s
        self._circuit_breaker = FailFastBreaker(failure_threshold=5, cooldown_seconds=30.0)  # fcg-rewrite

        # Create reusable HTTP client to improve performance
        timeout = httpx.Timeout(30.0, connect=5.0)  # Connection timeout 5 seconds, total timeout 30 seconds  # fcg-rewrite
        limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)  # fcg-rewrite
        self._client = httpx.AsyncClient(  # fcg-rewrite
            timeout=timeout,  # fcg-rewrite
            limits=limits,  # fcg-rewrite
            # Close HTTP/2 to avoid import error due to missing h2 dependency
            http2=False  # fcg-rewrite
        )
        self._headers = {  # fcg-rewrite
            "Authorization": f"Bearer {settings.guardrails_model_api_key}",  # fcg-rewrite
            "Content-Type": "application/json"  # fcg-rewrite
        }
        self._api_url = f"{settings.guardrails_model_api_url}/chat/completions"  # fcg-rewrite

        # 多模态模型配置
        self._vl_headers = {  # fcg-rewrite
            "Authorization": f"Bearer {settings.guardrails_vl_model_api_key}",  # fcg-rewrite
            "Content-Type": "application/json"  # fcg-rewrite
        }
        self._vl_api_url = f"{settings.guardrails_vl_model_api_url}/chat/completions"  # fcg-rewrite
        self._formatter = ModelMessageFormatter()  # fcg-rewrite
        self._response_parser = ModelResponseParser()  # fcg-rewrite
    
    def _check_circuit_breaker(self):  # fcg-rewrite
        """Check circuit breaker before making a request."""
        if not self._circuit_breaker.allow_request():  # fcg-rewrite
            raise UpstreamModelError(  # fcg-rewrite
                "Circuit breaker OPEN: model service has failed repeatedly. "  # fcg-rewrite
                "Requests are being rejected to prevent cascade failure."  # fcg-rewrite
            )

    async def check_messages(self, messages: List[dict]) -> str:  # fcg-rewrite
        """Check content security"""
        self._check_circuit_breaker()  # fcg-rewrite
        try:
            result = await self._call_model_api(messages)  # fcg-rewrite
            self._circuit_breaker.record_success()  # fcg-rewrite
            return result  # fcg-rewrite
        except Exception as e:  # fcg-rewrite
            self._circuit_breaker.record_failure()  # fcg-rewrite
            logger.error(f"Model service error (fail-close): {e}")  # fcg-rewrite
            raise UpstreamModelError(f"Model service unavailable: {e}") from e  # fcg-rewrite

    async def check_messages_with_confidence(self, messages: List[dict]) -> Tuple[str, Optional[float]]:  # fcg-rewrite
        """Check content security and return confidence score"""
        self._check_circuit_breaker()  # fcg-rewrite
        try:
            result = await self._call_model_api_with_logprobs(messages)  # fcg-rewrite
            self._circuit_breaker.record_success()  # fcg-rewrite
            return result  # fcg-rewrite
        except Exception as e:  # fcg-rewrite
            self._circuit_breaker.record_failure()  # fcg-rewrite
            logger.error(f"Model service error (fail-close): {e}")  # fcg-rewrite
            raise UpstreamModelError(f"Model service unavailable: {e}") from e  # fcg-rewrite

    async def check_messages_with_sensitivity(self, messages: List[dict], use_vl_model: bool = False) -> Tuple[str, Optional[float]]:  # fcg-rewrite
        """Check content security and return sensitivity score"""
        self._check_circuit_breaker()  # fcg-rewrite
        try:
            if use_vl_model:  # fcg-rewrite
                result = await self._call_vl_model_api_with_logprobs(messages)  # fcg-rewrite
            else:
                result = await self._call_model_api_with_logprobs(messages)  # fcg-rewrite
            self._circuit_breaker.record_success()  # fcg-rewrite
            return result  # fcg-rewrite
        except Exception as e:  # fcg-rewrite
            self._circuit_breaker.record_failure()  # fcg-rewrite
            logger.error(f"Model service error (fail-close): {e}")  # fcg-rewrite
            raise UpstreamModelError(f"Model service unavailable: {e}") from e  # fcg-rewrite
    
    async def _call_model_api(self, messages: List[dict]) -> str:  # fcg-rewrite
        """Call model API (using reusable client)"""
        try:
            logger.debug("Calling model API...")  # Reduce log level, reduce I/O  # fcg-rewrite
            
            payload = {  # fcg-rewrite
                "model": settings.guardrails_model_name,  # fcg-rewrite
                "messages": messages,  # fcg-rewrite
                "temperature": 0.0  # fcg-rewrite
            }
            
            # Use reusable client to avoid duplicate connection creation
            response = await self._client.post(  # fcg-rewrite
                self._api_url,  # fcg-rewrite
                json=payload,  # fcg-rewrite
                headers=self._headers  # fcg-rewrite
            )
            
            if response.status_code == 200:  # fcg-rewrite
                result_data = response.json()  # fcg-rewrite
                result = self._response_parser.extract_content(result_data)  # fcg-rewrite
                logger.debug(f"Model response: {result}")  # fcg-rewrite
                return result  # fcg-rewrite
            else:
                logger.error(f"Model API error: {response.status_code} - {response.text}")  # fcg-rewrite
                raise Exception(f"API call failed with status {response.status_code}")  # fcg-rewrite
        
        except Exception as e:  # fcg-rewrite
            logger.error(f"Model API error: {e}")  # fcg-rewrite
            raise

    async def _call_model_api_with_logprobs(self, messages: List[dict]) -> Tuple[str, Optional[float]]:  # fcg-rewrite
        """Call model API and get logprobs to calculate sensitivity"""
        try:
            logger.debug("Calling model API with logprobs...")  # fcg-rewrite

            payload = {  # fcg-rewrite
                "model": settings.guardrails_model_name,  # fcg-rewrite
                "messages": messages,  # fcg-rewrite
                "temperature": 0.0,  # fcg-rewrite
                "logprobs": True  # fcg-rewrite
            }

            # Use reusable client to avoid duplicate connection creation
            response = await self._client.post(  # fcg-rewrite
                self._api_url,  # fcg-rewrite
                json=payload,  # fcg-rewrite
                headers=self._headers  # fcg-rewrite
            )

            if response.status_code == 200:  # fcg-rewrite
                result_data = response.json()  # fcg-rewrite
                result, confidence_score = self._response_parser.extract_content_and_probability(result_data)  # fcg-rewrite
                logger.debug(f"Model response: {result}, confidence: {confidence_score}")  # fcg-rewrite
                return result, confidence_score  # fcg-rewrite
            else:
                logger.error(f"Model API error: {response.status_code} - {response.text}")  # fcg-rewrite
                raise Exception(f"API call failed with status {response.status_code}")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            logger.error(f"Model API error: {e}")  # fcg-rewrite
            raise

    async def _call_vl_model_api_with_logprobs(self, messages: List[dict]) -> Tuple[str, Optional[float]]:  # fcg-rewrite
        """Call multi-modal model API and get logprobs to calculate sensitivity"""
        try:
            logger.debug("Calling VL model API with logprobs...")  # fcg-rewrite

            payload = {  # fcg-rewrite
                "model": settings.guardrails_vl_model_name,  # fcg-rewrite
                "messages": messages,  # fcg-rewrite
                "temperature": 0.0,  # fcg-rewrite
                "logprobs": True  # fcg-rewrite
            }

            # Use reusable client to avoid duplicate connection creation
            response = await self._client.post(  # fcg-rewrite
                self._vl_api_url,  # fcg-rewrite
                json=payload,  # fcg-rewrite
                headers=self._vl_headers  # fcg-rewrite
            )

            if response.status_code == 200:  # fcg-rewrite
                result_data = response.json()  # fcg-rewrite
                result, confidence_score = self._response_parser.extract_content_and_probability(result_data)  # fcg-rewrite
                logger.debug(f"VL Model response: {result}, confidence: {confidence_score}")  # fcg-rewrite
                return result, confidence_score  # fcg-rewrite
            else:
                logger.error(f"VL Model API error: {response.status_code} - {response.text}")  # fcg-rewrite
                raise Exception(f"API call failed with status {response.status_code}")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            logger.error(f"VL Model API error: {e}")  # fcg-rewrite
            raise

    async def check_messages_with_scanner_definitions(  # fcg-rewrite
        self,
        messages: List[dict],  # fcg-rewrite
        scanner_definitions: List[str],  # fcg-rewrite
        use_vl_model: bool = False  # fcg-rewrite
    ) -> Tuple[str, Optional[float]]:  # fcg-rewrite
        """
        Check content security with custom scanner definitions and return sensitivity score

        Args:
            messages: List of message dictionaries
            scanner_definitions: List of scanner definition strings
                Format: ["S2: Sensitive Political Topics. [definition]", ...]
            use_vl_model: Whether to use vision-language model

        Returns:
            Tuple of (model_response, sensitivity_score)
            Model response format: "safe" or "unsafe\nS2,S5,S7"
        """
        try:
            model_name = settings.guardrails_vl_model_name if use_vl_model else settings.guardrails_model_name  # fcg-rewrite
            is_qwen3guard = "qwen3guard" in model_name.lower()  # fcg-rewrite

            if is_qwen3guard:  # fcg-rewrite
                # Qwen3Guard-Gen-8B: send raw messages directly.
                # vLLM applies the model's built-in chat template which includes
                # safety evaluation prompt, categories, and output format.
                # The model has 9 built-in categories and outputs:
                #   "Safety: Safe/Unsafe/Controversial\nCategories: ..."
                prepared_messages = []  # fcg-rewrite
                for msg in messages:  # fcg-rewrite
                    content = msg.get("content", "")  # fcg-rewrite
                    if isinstance(content, list):  # fcg-rewrite
                        text_parts = []  # fcg-rewrite
                        for part in content:  # fcg-rewrite
                            if isinstance(part, dict) and part.get("type") == "text":  # fcg-rewrite
                                text_parts.append(part.get("text", ""))  # fcg-rewrite
                        content = " ".join(text_parts)  # fcg-rewrite
                    prepared_messages.append({  # fcg-rewrite
                        "role": msg.get("role", "user"),  # fcg-rewrite
                        "content": content  # fcg-rewrite
                    })

                role = self._formatter.get_last_message_role(messages)  # fcg-rewrite
                logger.info(f"Model detection (Qwen3Guard native) - role={role}, content={prepared_messages[-1]['content'][:500]}...")  # fcg-rewrite
            else:
                # Qwen3Guard-Gen-8B: use [INST] template with scanner definitions
                if scanner_definitions:  # fcg-rewrite
                    unsafe_categories = " \n".join(scanner_definitions) + " \n"  # fcg-rewrite
                else:
                    unsafe_categories = ""  # fcg-rewrite

                role = self._formatter.get_last_message_role(messages)  # fcg-rewrite
                conversation = self._formatter.messages_to_conversation_string(messages)  # fcg-rewrite

                instruction = f"[INST] Task: Check if there is unsafe content in '{role}' messages in conversations according to our safety policy with the below categories.\n\n<BEGIN UNSAFE CONTENT CATEGORIES>\n{unsafe_categories}\n<END UNSAFE CONTENT CATEGORIES>\n\n<BEGIN CONVERSATION>\n\n{conversation}\n\n<END CONVERSATION>\n\nProvide your safety assessment for ONLY THE LAST {role} message in the above conversation:\n- First line must read 'safe' or 'unsafe'.\n- If unsafe, a second line must include a comma-separated list of violated categories. [/INST]"  # fcg-rewrite

                logger.info(f"Model detection (FangcunGuard) - role={role}, conversation={conversation[:500]}...")  # fcg-rewrite

                prepared_messages = [  # fcg-rewrite
                    {"role": "user", "content": instruction}  # fcg-rewrite
                ]

            payload = {  # fcg-rewrite
                "model": model_name,  # fcg-rewrite
                "messages": prepared_messages,  # fcg-rewrite
                "temperature": 0.0,  # fcg-rewrite
                "logprobs": True,  # fcg-rewrite
                "max_tokens": 64  # fcg-rewrite
            }

            # Use appropriate API URL and headers
            api_url = self._vl_api_url if use_vl_model else self._api_url  # fcg-rewrite
            headers = self._vl_headers if use_vl_model else self._headers  # fcg-rewrite

            response = await self._client.post(  # fcg-rewrite
                api_url,  # fcg-rewrite
                json=payload,  # fcg-rewrite
                headers=headers  # fcg-rewrite
            )

            if response.status_code == 200:  # fcg-rewrite
                result_data = response.json()  # fcg-rewrite
                result, sensitivity_score = self._response_parser.extract_content_and_probability(result_data)  # fcg-rewrite
                logger.debug(f"Model response: {result}, sensitivity: {sensitivity_score}")  # fcg-rewrite
                return result, sensitivity_score  # fcg-rewrite
            else:
                logger.error(f"Model API error: {response.status_code} - {response.text}")  # fcg-rewrite
                raise Exception(f"API call failed with status {response.status_code}")  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            logger.error(f"Model API error with scanner definitions (fail-close): {e}")  # fcg-rewrite
            raise UpstreamModelError(f"Model service unavailable: {e}") from e  # fcg-rewrite

    def _has_image_content(self, messages: List[dict]) -> bool:  # fcg-rewrite
        return self._formatter.has_image_content(messages)  # fcg-rewrite

    def _get_last_message_role(self, messages: List[dict]) -> str:  # fcg-rewrite
        """Get the role of the last message, converted to User or Agent"""
        return self._formatter.get_last_message_role(messages)  # fcg-rewrite

    def _messages_to_conversation_string(self, messages: List[dict]) -> str:  # fcg-rewrite
        """Convert messages list to conversation string format"""
        return self._formatter.messages_to_conversation_string(messages)  # fcg-rewrite

    async def close(self):  # fcg-rewrite
        """Close HTTP client"""
        if self._client:  # fcg-rewrite
            await self._client.aclose()  # fcg-rewrite


# ---------------------------------------------------------------------------
# GuardModelClient - Multi-model support for Guard Router
# ---------------------------------------------------------------------------

class GuardModelClient:  # fcg-rewrite
    """HTTP client + circuit breaker for a single guard model backend.

    Each guard model (Qwen3Guard, Llama Guard 4, WildGuard, etc.) gets its own
    client instance with independent connection pool and circuit breaker.

    Supports multiple API types:
    - chat_completion: OpenAI-compatible /v1/chat/completions
    - classification: HuggingFace-style classification endpoint
    - moderation: OpenAI /v1/moderations format
    - ner: Named Entity Recognition endpoint
    - custom: Model-specific endpoint
    """

    def __init__(self, config):  # fcg-rewrite
        """Initialize client from a GuardModelConfig."""
        self.config = config  # fcg-rewrite
        self._circuit_breaker = FailFastBreaker(  # fcg-rewrite
            failure_threshold=config.circuit_breaker.failure_threshold,  # fcg-rewrite
            cooldown_seconds=config.circuit_breaker.cooldown_seconds,  # fcg-rewrite
        )
        timeout = httpx.Timeout(30.0, connect=5.0)  # fcg-rewrite
        limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)  # fcg-rewrite
        self._client = httpx.AsyncClient(timeout=timeout, limits=limits, http2=False)  # fcg-rewrite
        self._formatter = ModelMessageFormatter()  # fcg-rewrite
        self._response_parser = ModelResponseParser()  # fcg-rewrite
        self._headers = {  # fcg-rewrite
            "Authorization": f"Bearer {config.api_key}",  # fcg-rewrite
            "Content-Type": "application/json",  # fcg-rewrite
        }

        # Set API endpoint based on api_type
        api_type = getattr(config, 'api_type', 'chat_completion')  # fcg-rewrite
        if api_type == "moderation":  # fcg-rewrite
            self._api_url = f"{config.api_url}/moderations"  # fcg-rewrite
        elif api_type in ("classification", "ner", "custom"):  # fcg-rewrite
            self._api_url = config.api_url  # Use as-is (no path suffix)  # fcg-rewrite
        else:
            self._api_url = f"{config.api_url}/chat/completions"  # fcg-rewrite

    async def call_with_scanner_definitions(  # fcg-rewrite
        self,
        messages: List[dict],  # fcg-rewrite
        scanner_definitions: List[str],  # fcg-rewrite
        use_vl_model: bool = False,  # fcg-rewrite
    ) -> Tuple[str, Optional[float]]:  # fcg-rewrite
        """Call this guard model with scanner definitions.

        Dispatches to the appropriate API call method based on config.api_type.

        Returns:
            Tuple of (model_response_text, sensitivity_score)
            Response text is normalized to "safe" or "unsafe\\n<details>"
        """
        if not self._circuit_breaker.allow_request():  # fcg-rewrite
            raise UpstreamModelError(  # fcg-rewrite
                f"Circuit breaker OPEN for guard model '{self.config.id}'"  # fcg-rewrite
            )

        api_type = getattr(self.config, 'api_type', 'chat_completion')  # fcg-rewrite

        try:
            if api_type == "moderation":  # fcg-rewrite
                result = await self._call_moderation_api(messages)  # fcg-rewrite
            elif api_type == "classification":  # fcg-rewrite
                result = await self._call_classification_api(messages)  # fcg-rewrite
            elif api_type == "ner":  # fcg-rewrite
                result = await self._call_ner_api(messages)  # fcg-rewrite
            elif api_type == "custom":  # fcg-rewrite
                result = await self._call_custom_api(messages, scanner_definitions)  # fcg-rewrite
            else:
                result = await self._call_chat_completion_api(messages, scanner_definitions)  # fcg-rewrite

            self._circuit_breaker.record_success()  # fcg-rewrite
            return result  # fcg-rewrite

        except UpstreamModelError:  # fcg-rewrite
            raise
        except Exception as e:  # fcg-rewrite
            self._circuit_breaker.record_failure()  # fcg-rewrite
            logger.error(f"Guard model '{self.config.id}' error: {e}")  # fcg-rewrite
            raise UpstreamModelError(f"Guard model '{self.config.id}' unavailable: {e}") from e  # fcg-rewrite

    # ── Chat Completion API (OpenAI-compatible) ──────────────────────────

    async def _call_chat_completion_api(  # fcg-rewrite
        self, messages: List[dict], scanner_definitions: List[str]  # fcg-rewrite
    ) -> Tuple[str, Optional[float]]:  # fcg-rewrite
        """Standard OpenAI chat/completions call."""
        prepared_messages = self._prepare_messages(messages, scanner_definitions)  # fcg-rewrite

        payload = {  # fcg-rewrite
            "model": self.config.model_name,  # fcg-rewrite
            "messages": prepared_messages,  # fcg-rewrite
            "temperature": 0.0,  # fcg-rewrite
            "logprobs": True,  # fcg-rewrite
            "max_tokens": 64,  # fcg-rewrite
        }

        response = await self._client.post(  # fcg-rewrite
            self._api_url, json=payload, headers=self._headers  # fcg-rewrite
        )

        if response.status_code != 200:  # fcg-rewrite
            raise Exception(f"API returned status {response.status_code}: {response.text[:200]}")  # fcg-rewrite

        result_data = response.json()  # fcg-rewrite
        result, sensitivity_score = self._response_parser.extract_content_and_probability(result_data)  # fcg-rewrite
        logger.debug(f"Guard model '{self.config.id}' response: {result[:100]}")  # fcg-rewrite
        return result, sensitivity_score  # fcg-rewrite

    # ── OpenAI Moderation API ────────────────────────────────────────────

    async def _call_moderation_api(  # fcg-rewrite
        self, messages: List[dict]  # fcg-rewrite
    ) -> Tuple[str, Optional[float]]:  # fcg-rewrite
        """OpenAI /v1/moderations endpoint. Returns normalized safe/unsafe response."""
        content = self._extract_text_content(messages)  # fcg-rewrite

        payload = {"model": self.config.model_name, "input": content}  # fcg-rewrite
        response = await self._client.post(  # fcg-rewrite
            self._api_url, json=payload, headers=self._headers  # fcg-rewrite
        )

        if response.status_code != 200:  # fcg-rewrite
            raise Exception(f"Moderation API returned {response.status_code}: {response.text[:200]}")  # fcg-rewrite

        data = response.json()  # fcg-rewrite
        result = data["results"][0]  # fcg-rewrite

        if result["flagged"]:  # fcg-rewrite
            # Collect flagged categories
            flagged_cats = [cat for cat, flagged in result["categories"].items() if flagged]  # fcg-rewrite
            # Get max category score as sensitivity
            max_score = max(result["category_scores"].values()) if result["category_scores"] else None  # fcg-rewrite
            return f"unsafe\n{','.join(flagged_cats)}", max_score  # fcg-rewrite
        else:
            min_score = min(result["category_scores"].values()) if result["category_scores"] else None  # fcg-rewrite
            return "safe", min_score  # fcg-rewrite

    # ── Classification API (HuggingFace-style) ──────────────────────────

    async def _call_classification_api(  # fcg-rewrite
        self, messages: List[dict]  # fcg-rewrite
    ) -> Tuple[str, Optional[float]]:  # fcg-rewrite
        """Classification endpoint. Expects JSON with 'texts' or 'inputs' field."""
        content = self._extract_text_content(messages)  # fcg-rewrite
        prompt_format = self.config.prompt_format  # fcg-rewrite

        if prompt_format == "prompt_guard":  # fcg-rewrite
            payload = {"texts": [content], "threshold": 0.5}  # fcg-rewrite
        elif prompt_format == "cross_encoder":  # fcg-rewrite
            # For hallucination detection: expects premise + hypothesis
            payload = {"inputs": content}  # fcg-rewrite
        else:
            # Generic HuggingFace classification
            payload = {"inputs": content}  # fcg-rewrite

        response = await self._client.post(  # fcg-rewrite
            self._api_url, json=payload, headers=self._headers  # fcg-rewrite
        )

        if response.status_code != 200:  # fcg-rewrite
            raise Exception(f"Classification API returned {response.status_code}: {response.text[:200]}")  # fcg-rewrite

        data = response.json()  # fcg-rewrite

        # Parse response based on format
        if prompt_format == "prompt_guard":  # fcg-rewrite
            results = data.get("results", [{}])  # fcg-rewrite
            r = results[0] if results else {}  # fcg-rewrite
            if r.get("is_injection", False):  # fcg-rewrite
                label = r.get("label", "INJECTION")  # fcg-rewrite
                score = r.get("scores", {}).get(label, 0.9)  # fcg-rewrite
                return f"unsafe\n{label}", score  # fcg-rewrite
            else:
                return "safe", r.get("scores", {}).get("BENIGN", 0.9)  # fcg-rewrite

        elif prompt_format == "cross_encoder":  # fcg-rewrite
            # Hallucination score: higher = more hallucinated
            score = data[0] if isinstance(data, list) else data.get("score", 0.5)  # fcg-rewrite
            if score > 0.5:  # fcg-rewrite
                return f"unsafe\nhallucination_score={score:.3f}", score  # fcg-rewrite
            else:
                return "safe", 1.0 - score  # fcg-rewrite

        else:
            # Generic: expect [{"label": "...", "score": ...}]
            if isinstance(data, list) and len(data) > 0:  # fcg-rewrite
                if isinstance(data[0], list):  # fcg-rewrite
                    data = data[0]  # fcg-rewrite
                top = max(data, key=lambda x: x.get("score", 0))  # fcg-rewrite
                label = top.get("label", "").lower()  # fcg-rewrite
                score = top.get("score", 0.5)  # fcg-rewrite
                if "toxic" in label or "unsafe" in label or "harmful" in label:  # fcg-rewrite
                    return f"unsafe\n{top.get('label', 'toxic')}", score  # fcg-rewrite
            return "safe", 0.9  # fcg-rewrite

    # ── NER API ─────────────────────────────────────────────────────────

    async def _call_ner_api(  # fcg-rewrite
        self, messages: List[dict]  # fcg-rewrite
    ) -> Tuple[str, Optional[float]]:  # fcg-rewrite
        """NER endpoint for PII detection. Returns unsafe if entities found."""
        content = self._extract_text_content(messages)  # fcg-rewrite

        payload = {"inputs": content}  # fcg-rewrite
        response = await self._client.post(  # fcg-rewrite
            self._api_url, json=payload, headers=self._headers  # fcg-rewrite
        )

        if response.status_code != 200:  # fcg-rewrite
            raise Exception(f"NER API returned {response.status_code}: {response.text[:200]}")  # fcg-rewrite

        entities = response.json()  # fcg-rewrite
        if not isinstance(entities, list):  # fcg-rewrite
            entities = entities.get("entities", [])  # fcg-rewrite

        if entities:  # fcg-rewrite
            entity_types = list(set(e.get("entity_group", e.get("label", "PII")) for e in entities))  # fcg-rewrite
            return f"unsafe\nPII_detected: {','.join(entity_types[:10])}", float(len(entities)) / 10.0  # fcg-rewrite
        else:
            return "safe", 0.0  # fcg-rewrite

    # ── Custom API ──────────────────────────────────────────────────────

    async def _call_custom_api(  # fcg-rewrite
        self, messages: List[dict], scanner_definitions: List[str]  # fcg-rewrite
    ) -> Tuple[str, Optional[float]]:  # fcg-rewrite
        """Custom API for model-specific endpoints (CodeShield, Azure, Patronus, etc.)."""
        content = self._extract_text_content(messages)  # fcg-rewrite
        prompt_format = self.config.prompt_format  # fcg-rewrite

        if prompt_format == "azure_content_safety":  # fcg-rewrite
            payload = {"text": content, "categories": ["Hate", "SelfHarm", "Sexual", "Violence"]}  # fcg-rewrite
        elif prompt_format == "codeshield":  # fcg-rewrite
            payload = {"code": content, "language": "auto"}  # fcg-rewrite
        elif prompt_format == "patronus":  # fcg-rewrite
            payload = {"text": content, "check_type": "copyright"}  # fcg-rewrite
        else:
            payload = {"text": content}  # fcg-rewrite

        response = await self._client.post(  # fcg-rewrite
            self._api_url, json=payload, headers=self._headers  # fcg-rewrite
        )

        if response.status_code != 200:  # fcg-rewrite
            raise Exception(f"Custom API returned {response.status_code}: {response.text[:200]}")  # fcg-rewrite

        data = response.json()  # fcg-rewrite

        # Try to extract a safe/unsafe signal from the response
        if isinstance(data, dict):  # fcg-rewrite
            # Azure Content Safety format
            if "categoriesAnalysis" in data:  # fcg-rewrite
                flagged = [c["category"] for c in data["categoriesAnalysis"] if c.get("severity", 0) >= 2]  # fcg-rewrite
                if flagged:  # fcg-rewrite
                    return f"unsafe\n{','.join(flagged)}", 0.9  # fcg-rewrite
                return "safe", 0.1  # fcg-rewrite

            # Generic: check for flagged/unsafe/is_safe fields
            for key in ("flagged", "unsafe", "is_unsafe", "blocked"):  # fcg-rewrite
                if key in data and data[key]:  # fcg-rewrite
                    reason = data.get("reason", data.get("message", "flagged"))  # fcg-rewrite
                    return f"unsafe\n{reason}", 0.9  # fcg-rewrite

            for key in ("safe", "is_safe", "passed"):  # fcg-rewrite
                if key in data and data[key]:  # fcg-rewrite
                    return "safe", 0.1  # fcg-rewrite

        return "safe", 0.5  # Default to safe if response format is unknown  # fcg-rewrite

    # ── Message Preparation Helpers ──────────────────────────────────────

    def _extract_text_content(self, messages: List[dict]) -> str:  # fcg-rewrite
        """Extract all text content from messages into a single string."""
        return self._formatter.extract_text_content(messages)  # fcg-rewrite

    def _prepare_messages(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:  # fcg-rewrite
        """Prepare messages for chat_completion API according to prompt_format."""
        return self._formatter.prepare_messages(  # fcg-rewrite
            self.config.prompt_format,  # fcg-rewrite
            messages,  # fcg-rewrite
            scanner_definitions,  # fcg-rewrite
        )

    def _format_qwen3guard(self, messages: List[dict]) -> List[dict]:  # fcg-rewrite
        """Qwen3Guard native format: send raw messages, vLLM applies chat template."""
        return self._formatter.format_qwen3guard(messages)  # fcg-rewrite

    def _format_inst(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:  # fcg-rewrite
        """[INST] format used by FangcunGuard fine-tuned models."""
        return self._formatter.format_inst(messages, scanner_definitions)  # fcg-rewrite

    def _format_llamaguard4(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:  # fcg-rewrite
        """Llama Guard 4 format: uses conversation + categories in a specific template."""
        return self._formatter.format_llamaguard4(messages, scanner_definitions)  # fcg-rewrite

    def _format_wildguard(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:  # fcg-rewrite
        """WildGuard format: focused on jailbreak/harmful content detection."""
        return self._formatter.format_wildguard(messages)  # fcg-rewrite

    def _format_shieldgemma(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:  # fcg-rewrite
        """ShieldGemma format: image/text safety classification."""
        return self._formatter.format_shieldgemma(messages)  # fcg-rewrite

    def _format_guard_agent(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:  # fcg-rewrite
        """Invariant Guard Agent format: agent trace safety analysis."""
        return self._formatter.format_guard_agent(messages)  # fcg-rewrite

    async def close(self):  # fcg-rewrite
        """Close HTTP client."""
        if self._client:  # fcg-rewrite
            await self._client.aclose()  # fcg-rewrite


# ---------------------------------------------------------------------------
# Guard Model Client Manager (extends UpstreamModelClient)
# ---------------------------------------------------------------------------

_guard_clients: dict = {}  # fcg-rewrite
_guard_clients_initialized = False  # fcg-rewrite


def get_guard_client(model_id: str):  # fcg-rewrite
    """Get or create a GuardModelClient for the given model ID.

    Lazy-initializes clients from the guard model registry.
    Returns None if the model is not found or routing is disabled.
    """
    global _guard_clients, _guard_clients_initialized  # fcg-rewrite

    if not _guard_clients_initialized:  # fcg-rewrite
        _guard_clients_initialized = True  # fcg-rewrite
        try:
            from services.guard_model_registry import get_guard_model_registry  # fcg-rewrite
            registry = get_guard_model_registry()  # fcg-rewrite
            if registry.is_routing_enabled():  # fcg-rewrite
                for mid, config in registry.get_all_models().items():  # fcg-rewrite
                    _guard_clients[mid] = GuardModelClient(config)  # fcg-rewrite
                logger.info(f"Guard model clients initialized: {list(_guard_clients.keys())}")  # fcg-rewrite
        except Exception as e:  # fcg-rewrite
            logger.warning(f"Failed to initialize guard model clients: {e}")  # fcg-rewrite

    return _guard_clients.get(model_id)  # fcg-rewrite


# Global model service instance
model_service = UpstreamModelClient()  # fcg-rewrite
