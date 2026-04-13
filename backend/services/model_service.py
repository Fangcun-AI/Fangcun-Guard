import asyncio
import httpx
import json
import math
import time
from typing import List, Tuple, Optional
from config import settings
from utils.logger import setup_logger


class ModelServiceError(Exception):
    """Raised when the model service is unavailable or returns an error.
    Callers must handle this to enforce fail-close semantics."""
    pass


class CircuitBreaker:
    """Simple circuit breaker: after N consecutive failures, open the circuit
    and fail fast for a cooldown period before allowing a retry."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0):
        self._failure_threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = "closed"  # closed | open | half_open

    def record_success(self):
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self._failure_threshold:
            self._state = "open"
            logger.warning(f"Circuit breaker OPEN after {self._failure_count} consecutive failures. "
                           f"Requests will fail fast for {self._cooldown}s.")

    def allow_request(self) -> bool:
        if self._state == "closed":
            return True
        if self._state == "open":
            if time.time() - self._last_failure_time >= self._cooldown:
                self._state = "half_open"
                logger.info("Circuit breaker half-open: allowing probe request")
                return True
            return False
        # half_open: allow one probe
        return True

    @property
    def is_open(self) -> bool:
        return self._state == "open" and (time.time() - self._last_failure_time < self._cooldown)

logger = setup_logger()

class ModelService:
    """Model service class"""

    def __init__(self):
        # Circuit breaker: open after 5 consecutive failures, cooldown 30s
        self._circuit_breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0)

        # Create reusable HTTP client to improve performance
        timeout = httpx.Timeout(30.0, connect=5.0)  # Connection timeout 5 seconds, total timeout 30 seconds
        limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)
        self._client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            # Close HTTP/2 to avoid import error due to missing h2 dependency
            http2=False
        )
        self._headers = {
            "Authorization": f"Bearer {settings.guardrails_model_api_key}",
            "Content-Type": "application/json"
        }
        self._api_url = f"{settings.guardrails_model_api_url}/chat/completions"

        # 多模态模型配置
        self._vl_headers = {
            "Authorization": f"Bearer {settings.guardrails_vl_model_api_key}",
            "Content-Type": "application/json"
        }
        self._vl_api_url = f"{settings.guardrails_vl_model_api_url}/chat/completions"
    
    def _check_circuit_breaker(self):
        """Check circuit breaker before making a request."""
        if not self._circuit_breaker.allow_request():
            raise ModelServiceError(
                "Circuit breaker OPEN: model service has failed repeatedly. "
                "Requests are being rejected to prevent cascade failure."
            )

    async def check_messages(self, messages: List[dict]) -> str:
        """Check content security"""
        self._check_circuit_breaker()
        try:
            result = await self._call_model_api(messages)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"Model service error (fail-close): {e}")
            raise ModelServiceError(f"Model service unavailable: {e}") from e

    async def check_messages_with_confidence(self, messages: List[dict]) -> Tuple[str, Optional[float]]:
        """Check content security and return confidence score"""
        self._check_circuit_breaker()
        try:
            result = await self._call_model_api_with_logprobs(messages)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"Model service error (fail-close): {e}")
            raise ModelServiceError(f"Model service unavailable: {e}") from e

    async def check_messages_with_sensitivity(self, messages: List[dict], use_vl_model: bool = False) -> Tuple[str, Optional[float]]:
        """Check content security and return sensitivity score"""
        self._check_circuit_breaker()
        try:
            if use_vl_model:
                result = await self._call_vl_model_api_with_logprobs(messages)
            else:
                result = await self._call_model_api_with_logprobs(messages)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"Model service error (fail-close): {e}")
            raise ModelServiceError(f"Model service unavailable: {e}") from e
    
    async def _call_model_api(self, messages: List[dict]) -> str:
        """Call model API (using reusable client)"""
        try:
            logger.debug("Calling model API...")  # Reduce log level, reduce I/O
            
            payload = {
                "model": settings.guardrails_model_name,
                "messages": messages,
                "temperature": 0.0
            }
            
            # Use reusable client to avoid duplicate connection creation
            response = await self._client.post(
                self._api_url,
                json=payload,
                headers=self._headers
            )
            
            if response.status_code == 200:
                result_data = response.json()
                result = result_data["choices"][0]["message"]["content"].strip()
                logger.debug(f"Model response: {result}")
                return result
            else:
                logger.error(f"Model API error: {response.status_code} - {response.text}")
                raise Exception(f"API call failed with status {response.status_code}")
        
        except Exception as e:
            logger.error(f"Model API error: {e}")
            raise

    async def _call_model_api_with_logprobs(self, messages: List[dict]) -> Tuple[str, Optional[float]]:
        """Call model API and get logprobs to calculate sensitivity"""
        try:
            logger.debug("Calling model API with logprobs...")

            payload = {
                "model": settings.guardrails_model_name,
                "messages": messages,
                "temperature": 0.0,
                "logprobs": True
            }

            # Use reusable client to avoid duplicate connection creation
            response = await self._client.post(
                self._api_url,
                json=payload,
                headers=self._headers
            )

            if response.status_code == 200:
                result_data = response.json()
                result = result_data["choices"][0]["message"]["content"].strip()

                # Extract sensitivity score
                confidence_score = None
                if "logprobs" in result_data["choices"][0] and result_data["choices"][0]["logprobs"]:
                    logprobs_data = result_data["choices"][0]["logprobs"]
                    if "content" in logprobs_data and logprobs_data["content"]:
                        # Get logprob of the first token
                        first_token_logprob = logprobs_data["content"][0]["logprob"]
                        # Convert to probability
                        confidence_score = math.exp(first_token_logprob)

                logger.debug(f"Model response: {result}, confidence: {confidence_score}")
                return result, confidence_score
            else:
                logger.error(f"Model API error: {response.status_code} - {response.text}")
                raise Exception(f"API call failed with status {response.status_code}")

        except Exception as e:
            logger.error(f"Model API error: {e}")
            raise

    async def _call_vl_model_api_with_logprobs(self, messages: List[dict]) -> Tuple[str, Optional[float]]:
        """Call multi-modal model API and get logprobs to calculate sensitivity"""
        try:
            logger.debug("Calling VL model API with logprobs...")

            payload = {
                "model": settings.guardrails_vl_model_name,
                "messages": messages,
                "temperature": 0.0,
                "logprobs": True
            }

            # Use reusable client to avoid duplicate connection creation
            response = await self._client.post(
                self._vl_api_url,
                json=payload,
                headers=self._vl_headers
            )

            if response.status_code == 200:
                result_data = response.json()
                result = result_data["choices"][0]["message"]["content"].strip()

                # Extract sensitivity score
                confidence_score = None
                if "logprobs" in result_data["choices"][0] and result_data["choices"][0]["logprobs"]:
                    logprobs_data = result_data["choices"][0]["logprobs"]
                    if "content" in logprobs_data and logprobs_data["content"]:
                        # Get logprob of the first token
                        first_token_logprob = logprobs_data["content"][0]["logprob"]
                        # Convert to probability
                        confidence_score = math.exp(first_token_logprob)

                logger.debug(f"VL Model response: {result}, confidence: {confidence_score}")
                return result, confidence_score
            else:
                logger.error(f"VL Model API error: {response.status_code} - {response.text}")
                raise Exception(f"API call failed with status {response.status_code}")

        except Exception as e:
            logger.error(f"VL Model API error: {e}")
            raise

    async def check_messages_with_scanner_definitions(
        self,
        messages: List[dict],
        scanner_definitions: List[str],
        use_vl_model: bool = False
    ) -> Tuple[str, Optional[float]]:
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
            model_name = settings.guardrails_vl_model_name if use_vl_model else settings.guardrails_model_name
            is_qwen3guard = "qwen3guard" in model_name.lower()

            if is_qwen3guard:
                # Qwen3Guard-Gen-8B: send raw messages directly.
                # vLLM applies the model's built-in chat template which includes
                # safety evaluation prompt, categories, and output format.
                # The model has 9 built-in categories and outputs:
                #   "Safety: Safe/Unsafe/Controversial\nCategories: ..."
                prepared_messages = []
                for msg in messages:
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                        content = " ".join(text_parts)
                    prepared_messages.append({
                        "role": msg.get("role", "user"),
                        "content": content
                    })

                role = self._get_last_message_role(messages)
                logger.info(f"Model detection (Qwen3Guard native) - role={role}, content={prepared_messages[-1]['content'][:500]}...")
            else:
                # Qwen3Guard-Gen-8B: use [INST] template with scanner definitions
                if scanner_definitions:
                    unsafe_categories = " \n".join(scanner_definitions) + " \n"
                else:
                    unsafe_categories = ""

                role = self._get_last_message_role(messages)
                conversation = self._messages_to_conversation_string(messages)

                instruction = f"[INST] Task: Check if there is unsafe content in '{role}' messages in conversations according to our safety policy with the below categories.\n\n<BEGIN UNSAFE CONTENT CATEGORIES>\n{unsafe_categories}\n<END UNSAFE CONTENT CATEGORIES>\n\n<BEGIN CONVERSATION>\n\n{conversation}\n\n<END CONVERSATION>\n\nProvide your safety assessment for ONLY THE LAST {role} message in the above conversation:\n- First line must read 'safe' or 'unsafe'.\n- If unsafe, a second line must include a comma-separated list of violated categories. [/INST]"

                logger.info(f"Model detection (FangcunGuard) - role={role}, conversation={conversation[:500]}...")

                prepared_messages = [
                    {"role": "user", "content": instruction}
                ]

            payload = {
                "model": model_name,
                "messages": prepared_messages,
                "temperature": 0.0,
                "logprobs": True,
                "max_tokens": 64
            }

            # Use appropriate API URL and headers
            api_url = self._vl_api_url if use_vl_model else self._api_url
            headers = self._vl_headers if use_vl_model else self._headers

            response = await self._client.post(
                api_url,
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                result_data = response.json()
                result = result_data["choices"][0]["message"]["content"].strip()

                # Extract sensitivity score
                sensitivity_score = None
                if "logprobs" in result_data["choices"][0] and result_data["choices"][0]["logprobs"]:
                    logprobs_data = result_data["choices"][0]["logprobs"]
                    if "content" in logprobs_data and logprobs_data["content"]:
                        # Get logprob of the first token
                        first_token_logprob = logprobs_data["content"][0]["logprob"]
                        # Convert to probability
                        sensitivity_score = math.exp(first_token_logprob)

                logger.debug(f"Model response: {result}, sensitivity: {sensitivity_score}")
                return result, sensitivity_score
            else:
                logger.error(f"Model API error: {response.status_code} - {response.text}")
                raise Exception(f"API call failed with status {response.status_code}")

        except Exception as e:
            logger.error(f"Model API error with scanner definitions (fail-close): {e}")
            raise ModelServiceError(f"Model service unavailable: {e}") from e

    def _has_image_content(self, messages: List[dict]) -> bool:
        """Check if the message contains image content"""
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        return True
        return False

    def _get_last_message_role(self, messages: List[dict]) -> str:
        """Get the role of the last message, converted to User or Agent"""
        if not messages:
            return "User"

        last_role = messages[-1].get("role", "user")
        return "Agent" if last_role == "assistant" else "User"

    def _messages_to_conversation_string(self, messages: List[dict]) -> str:
        """Convert messages list to conversation string format"""
        conversation_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle multimodal content (list format)
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = " ".join(text_parts)

            # Convert role to display name
            display_role = "Agent" if role == "assistant" else "User"
            conversation_parts.append(f"{display_role}: {content}")

        return "\n".join(conversation_parts)

    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()


# ---------------------------------------------------------------------------
# GuardModelClient - Multi-model support for Guard Router
# ---------------------------------------------------------------------------

class GuardModelClient:
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

    def __init__(self, config):
        """Initialize client from a GuardModelConfig."""
        self.config = config
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=config.circuit_breaker.failure_threshold,
            cooldown_seconds=config.circuit_breaker.cooldown_seconds,
        )
        timeout = httpx.Timeout(30.0, connect=5.0)
        limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
        self._client = httpx.AsyncClient(timeout=timeout, limits=limits, http2=False)
        self._headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        # Set API endpoint based on api_type
        api_type = getattr(config, 'api_type', 'chat_completion')
        if api_type == "moderation":
            self._api_url = f"{config.api_url}/moderations"
        elif api_type in ("classification", "ner", "custom"):
            self._api_url = config.api_url  # Use as-is (no path suffix)
        else:
            self._api_url = f"{config.api_url}/chat/completions"

    async def call_with_scanner_definitions(
        self,
        messages: List[dict],
        scanner_definitions: List[str],
        use_vl_model: bool = False,
    ) -> Tuple[str, Optional[float]]:
        """Call this guard model with scanner definitions.

        Dispatches to the appropriate API call method based on config.api_type.

        Returns:
            Tuple of (model_response_text, sensitivity_score)
            Response text is normalized to "safe" or "unsafe\\n<details>"
        """
        if not self._circuit_breaker.allow_request():
            raise ModelServiceError(
                f"Circuit breaker OPEN for guard model '{self.config.id}'"
            )

        api_type = getattr(self.config, 'api_type', 'chat_completion')

        try:
            if api_type == "moderation":
                result = await self._call_moderation_api(messages)
            elif api_type == "classification":
                result = await self._call_classification_api(messages)
            elif api_type == "ner":
                result = await self._call_ner_api(messages)
            elif api_type == "custom":
                result = await self._call_custom_api(messages, scanner_definitions)
            else:
                result = await self._call_chat_completion_api(messages, scanner_definitions)

            self._circuit_breaker.record_success()
            return result

        except ModelServiceError:
            raise
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"Guard model '{self.config.id}' error: {e}")
            raise ModelServiceError(f"Guard model '{self.config.id}' unavailable: {e}") from e

    # ── Chat Completion API (OpenAI-compatible) ──────────────────────────

    async def _call_chat_completion_api(
        self, messages: List[dict], scanner_definitions: List[str]
    ) -> Tuple[str, Optional[float]]:
        """Standard OpenAI chat/completions call."""
        prepared_messages = self._prepare_messages(messages, scanner_definitions)

        payload = {
            "model": self.config.model_name,
            "messages": prepared_messages,
            "temperature": 0.0,
            "logprobs": True,
            "max_tokens": 64,
        }

        response = await self._client.post(
            self._api_url, json=payload, headers=self._headers
        )

        if response.status_code != 200:
            raise Exception(f"API returned status {response.status_code}: {response.text[:200]}")

        result_data = response.json()
        result = result_data["choices"][0]["message"]["content"].strip()

        sensitivity_score = None
        choice = result_data["choices"][0]
        if choice.get("logprobs") and choice["logprobs"].get("content"):
            first_token_logprob = choice["logprobs"]["content"][0]["logprob"]
            sensitivity_score = math.exp(first_token_logprob)

        logger.debug(f"Guard model '{self.config.id}' response: {result[:100]}")
        return result, sensitivity_score

    # ── OpenAI Moderation API ────────────────────────────────────────────

    async def _call_moderation_api(
        self, messages: List[dict]
    ) -> Tuple[str, Optional[float]]:
        """OpenAI /v1/moderations endpoint. Returns normalized safe/unsafe response."""
        content = self._extract_text_content(messages)

        payload = {"model": self.config.model_name, "input": content}
        response = await self._client.post(
            self._api_url, json=payload, headers=self._headers
        )

        if response.status_code != 200:
            raise Exception(f"Moderation API returned {response.status_code}: {response.text[:200]}")

        data = response.json()
        result = data["results"][0]

        if result["flagged"]:
            # Collect flagged categories
            flagged_cats = [cat for cat, flagged in result["categories"].items() if flagged]
            # Get max category score as sensitivity
            max_score = max(result["category_scores"].values()) if result["category_scores"] else None
            return f"unsafe\n{','.join(flagged_cats)}", max_score
        else:
            min_score = min(result["category_scores"].values()) if result["category_scores"] else None
            return "safe", min_score

    # ── Classification API (HuggingFace-style) ──────────────────────────

    async def _call_classification_api(
        self, messages: List[dict]
    ) -> Tuple[str, Optional[float]]:
        """Classification endpoint. Expects JSON with 'texts' or 'inputs' field."""
        content = self._extract_text_content(messages)
        prompt_format = self.config.prompt_format

        if prompt_format == "prompt_guard":
            payload = {"texts": [content], "threshold": 0.5}
        elif prompt_format == "cross_encoder":
            # For hallucination detection: expects premise + hypothesis
            payload = {"inputs": content}
        else:
            # Generic HuggingFace classification
            payload = {"inputs": content}

        response = await self._client.post(
            self._api_url, json=payload, headers=self._headers
        )

        if response.status_code != 200:
            raise Exception(f"Classification API returned {response.status_code}: {response.text[:200]}")

        data = response.json()

        # Parse response based on format
        if prompt_format == "prompt_guard":
            results = data.get("results", [{}])
            r = results[0] if results else {}
            if r.get("is_injection", False):
                label = r.get("label", "INJECTION")
                score = r.get("scores", {}).get(label, 0.9)
                return f"unsafe\n{label}", score
            else:
                return "safe", r.get("scores", {}).get("BENIGN", 0.9)

        elif prompt_format == "cross_encoder":
            # Hallucination score: higher = more hallucinated
            score = data[0] if isinstance(data, list) else data.get("score", 0.5)
            if score > 0.5:
                return f"unsafe\nhallucination_score={score:.3f}", score
            else:
                return "safe", 1.0 - score

        else:
            # Generic: expect [{"label": "...", "score": ...}]
            if isinstance(data, list) and len(data) > 0:
                if isinstance(data[0], list):
                    data = data[0]
                top = max(data, key=lambda x: x.get("score", 0))
                label = top.get("label", "").lower()
                score = top.get("score", 0.5)
                if "toxic" in label or "unsafe" in label or "harmful" in label:
                    return f"unsafe\n{top.get('label', 'toxic')}", score
            return "safe", 0.9

    # ── NER API ─────────────────────────────────────────────────────────

    async def _call_ner_api(
        self, messages: List[dict]
    ) -> Tuple[str, Optional[float]]:
        """NER endpoint for PII detection. Returns unsafe if entities found."""
        content = self._extract_text_content(messages)

        payload = {"inputs": content}
        response = await self._client.post(
            self._api_url, json=payload, headers=self._headers
        )

        if response.status_code != 200:
            raise Exception(f"NER API returned {response.status_code}: {response.text[:200]}")

        entities = response.json()
        if not isinstance(entities, list):
            entities = entities.get("entities", [])

        if entities:
            entity_types = list(set(e.get("entity_group", e.get("label", "PII")) for e in entities))
            return f"unsafe\nPII_detected: {','.join(entity_types[:10])}", float(len(entities)) / 10.0
        else:
            return "safe", 0.0

    # ── Custom API ──────────────────────────────────────────────────────

    async def _call_custom_api(
        self, messages: List[dict], scanner_definitions: List[str]
    ) -> Tuple[str, Optional[float]]:
        """Custom API for model-specific endpoints (CodeShield, Azure, Patronus, etc.)."""
        content = self._extract_text_content(messages)
        prompt_format = self.config.prompt_format

        if prompt_format == "azure_content_safety":
            payload = {"text": content, "categories": ["Hate", "SelfHarm", "Sexual", "Violence"]}
        elif prompt_format == "codeshield":
            payload = {"code": content, "language": "auto"}
        elif prompt_format == "patronus":
            payload = {"text": content, "check_type": "copyright"}
        else:
            payload = {"text": content}

        response = await self._client.post(
            self._api_url, json=payload, headers=self._headers
        )

        if response.status_code != 200:
            raise Exception(f"Custom API returned {response.status_code}: {response.text[:200]}")

        data = response.json()

        # Try to extract a safe/unsafe signal from the response
        if isinstance(data, dict):
            # Azure Content Safety format
            if "categoriesAnalysis" in data:
                flagged = [c["category"] for c in data["categoriesAnalysis"] if c.get("severity", 0) >= 2]
                if flagged:
                    return f"unsafe\n{','.join(flagged)}", 0.9
                return "safe", 0.1

            # Generic: check for flagged/unsafe/is_safe fields
            for key in ("flagged", "unsafe", "is_unsafe", "blocked"):
                if key in data and data[key]:
                    reason = data.get("reason", data.get("message", "flagged"))
                    return f"unsafe\n{reason}", 0.9

            for key in ("safe", "is_safe", "passed"):
                if key in data and data[key]:
                    return "safe", 0.1

        return "safe", 0.5  # Default to safe if response format is unknown

    # ── Message Preparation Helpers ──────────────────────────────────────

    def _extract_text_content(self, messages: List[dict]) -> str:
        """Extract all text content from messages into a single string."""
        parts = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
            elif isinstance(content, str):
                parts.append(content)
        return "\n".join(parts)

    def _prepare_messages(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:
        """Prepare messages for chat_completion API according to prompt_format."""
        fmt = self.config.prompt_format

        if fmt == "qwen3guard":
            return self._format_qwen3guard(messages)
        elif fmt == "llamaguard4":
            return self._format_llamaguard4(messages, scanner_definitions)
        elif fmt == "wildguard":
            return self._format_wildguard(messages, scanner_definitions)
        elif fmt == "shieldgemma":
            return self._format_shieldgemma(messages, scanner_definitions)
        elif fmt == "guard_agent":
            return self._format_guard_agent(messages, scanner_definitions)
        else:
            return self._format_inst(messages, scanner_definitions)

    def _format_qwen3guard(self, messages: List[dict]) -> List[dict]:
        """Qwen3Guard native format: send raw messages, vLLM applies chat template."""
        prepared = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content
                              if isinstance(p, dict) and p.get("type") == "text"]
                content = " ".join(text_parts)
            prepared.append({"role": msg.get("role", "user"), "content": content})
        return prepared

    def _format_inst(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:
        """[INST] format used by FangcunGuard fine-tuned models."""
        unsafe_categories = " \n".join(scanner_definitions) + " \n" if scanner_definitions else ""
        role = "Agent" if messages[-1].get("role") == "assistant" else "User"

        conversation_parts = []
        for msg in messages:
            r = msg.get("role", "user")
            c = msg.get("content", "")
            if isinstance(c, list):
                c = " ".join(p.get("text", "") for p in c
                             if isinstance(p, dict) and p.get("type") == "text")
            display_role = "Agent" if r == "assistant" else "User"
            conversation_parts.append(f"{display_role}: {c}")
        conversation = "\n".join(conversation_parts)

        instruction = (
            f"[INST] Task: Check if there is unsafe content in '{role}' messages "
            f"in conversations according to our safety policy with the below categories.\n\n"
            f"<BEGIN UNSAFE CONTENT CATEGORIES>\n{unsafe_categories}\n"
            f"<END UNSAFE CONTENT CATEGORIES>\n\n"
            f"<BEGIN CONVERSATION>\n\n{conversation}\n\n<END CONVERSATION>\n\n"
            f"Provide your safety assessment for ONLY THE LAST {role} message "
            f"in the above conversation:\n"
            f"- First line must read 'safe' or 'unsafe'.\n"
            f"- If unsafe, a second line must include a comma-separated list of "
            f"violated categories. [/INST]"
        )
        return [{"role": "user", "content": instruction}]

    def _format_llamaguard4(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:
        """Llama Guard 4 format: uses conversation + categories in a specific template."""
        categories_text = ""
        for i, sd in enumerate(scanner_definitions):
            categories_text += f"{sd}\n"

        conversation_parts = []
        for msg in messages:
            r = msg.get("role", "user")
            c = msg.get("content", "")
            if isinstance(c, list):
                c = " ".join(p.get("text", "") for p in c
                             if isinstance(p, dict) and p.get("type") == "text")
            conversation_parts.append({"role": r, "content": c})

        # Llama Guard 4 expects the conversation as messages + a safety check instruction
        system_msg = (
            "You are a safety classifier. Check if the conversation contains unsafe content "
            "according to these categories:\n\n"
            f"{categories_text}\n"
            "Respond with 'safe' if the content is safe, or 'unsafe' followed by "
            "a newline and comma-separated violated category tags (e.g., S2,S5)."
        )
        return [{"role": "system", "content": system_msg}] + conversation_parts

    def _format_wildguard(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:
        """WildGuard format: focused on jailbreak/harmful content detection."""
        user_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                c = msg.get("content", "")
                if isinstance(c, list):
                    c = " ".join(p.get("text", "") for p in c
                                 if isinstance(p, dict) and p.get("type") == "text")
                user_content = c
                break

        instruction = (
            "You are a safety classifier. Determine if the following user request "
            "is harmful or a jailbreak attempt.\n\n"
            f"User request: {user_content}\n\n"
            "Respond with 'safe' if benign, or 'unsafe' followed by a newline "
            "and the reason (e.g., 'jailbreak' or 'harmful')."
        )
        return [{"role": "user", "content": instruction}]

    def _format_shieldgemma(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:
        """ShieldGemma format: image/text safety classification."""
        content = self._extract_text_content(messages)
        instruction = (
            "You are a safety content classifier. Classify the following content "
            "for safety issues including: sexually explicit, dangerous content, "
            "harassment, and hate speech.\n\n"
            f"Content: {content}\n\n"
            "Respond with 'safe' or 'unsafe' on the first line. "
            "If unsafe, list the violated categories on the second line."
        )
        return [{"role": "user", "content": instruction}]

    def _format_guard_agent(self, messages: List[dict], scanner_definitions: List[str]) -> List[dict]:
        """Invariant Guard Agent format: agent trace safety analysis."""
        # Pass the full conversation including tool calls for trace analysis
        trace_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(p.get("text", "") for p in content
                                   if isinstance(p, dict) and p.get("type") == "text")
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    trace_parts.append(f"[TOOL_CALL] {fn.get('name', 'unknown')}: {fn.get('arguments', '')}")
            else:
                trace_parts.append(f"{role}: {content}")

        trace = "\n".join(trace_parts)
        instruction = (
            "You are an AI agent safety auditor. Analyze the following agent trace "
            "for security risks including: privilege escalation, data exfiltration, "
            "unauthorized operations, and confused deputy attacks.\n\n"
            f"Agent trace:\n{trace}\n\n"
            "Respond with 'safe' if the trace is benign, or 'unsafe' followed by "
            "a newline and description of the risk."
        )
        return [{"role": "user", "content": instruction}]

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()


# ---------------------------------------------------------------------------
# Guard Model Client Manager (extends ModelService)
# ---------------------------------------------------------------------------

_guard_clients: dict = {}
_guard_clients_initialized = False


def get_guard_client(model_id: str):
    """Get or create a GuardModelClient for the given model ID.

    Lazy-initializes clients from the guard model registry.
    Returns None if the model is not found or routing is disabled.
    """
    global _guard_clients, _guard_clients_initialized

    if not _guard_clients_initialized:
        _guard_clients_initialized = True
        try:
            from services.guard_model_registry import get_guard_model_registry
            registry = get_guard_model_registry()
            if registry.is_routing_enabled():
                for mid, config in registry.get_all_models().items():
                    _guard_clients[mid] = GuardModelClient(config)
                logger.info(f"Guard model clients initialized: {list(_guard_clients.keys())}")
        except Exception as e:
            logger.warning(f"Failed to initialize guard model clients: {e}")

    return _guard_clients.get(model_id)


# Global model service instance
model_service = ModelService()