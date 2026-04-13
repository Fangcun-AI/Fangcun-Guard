"""
General-purpose LLM service for text generation tasks.

This service connects to a general-purpose LLM (e.g., Qwen3-8B) for tasks that
require text understanding and generation, such as:
- Data anonymization (genai_natural)
- Regex pattern generation
- Entity type code generation
- Appeal review
- Anonymization code generation

This is separate from ModelService which connects to Qwen3Guard (safety classifier).
"""
import asyncio
import httpx
import time
from typing import List
from config import settings
from utils.logger import setup_logger


logger = setup_logger()


class GeneralLLMServiceError(Exception):
    """Raised when the general LLM service is unavailable or returns an error."""
    pass


class CircuitBreaker:
    """Simple circuit breaker for the general LLM service."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0):
        self._failure_threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = "closed"

    def record_success(self):
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self._failure_threshold:
            self._state = "open"
            logger.warning(
                f"General LLM circuit breaker OPEN after {self._failure_count} "
                f"consecutive failures. Failing fast for {self._cooldown}s."
            )

    def allow_request(self) -> bool:
        if self._state == "closed":
            return True
        if self._state == "open":
            if time.time() - self._last_failure_time >= self._cooldown:
                self._state = "half_open"
                logger.info("General LLM circuit breaker half-open: allowing probe request")
                return True
            return False
        return True

    @property
    def is_open(self) -> bool:
        return self._state == "open" and (time.time() - self._last_failure_time < self._cooldown)


class GeneralLLMService:
    """General-purpose LLM service for text generation tasks.

    Connects to a general-purpose model (e.g., Qwen3-8B) via OpenAI-compatible API.
    """

    def __init__(self):
        self._circuit_breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0)

        timeout = httpx.Timeout(60.0, connect=5.0)
        limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
        self._client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=False
        )
        self._headers = {
            "Authorization": f"Bearer {settings.general_llm_api_key}",
            "Content-Type": "application/json"
        }
        self._api_url = f"{settings.general_llm_api_url}/chat/completions"
        self._model_name = settings.general_llm_model_name

    def _check_circuit_breaker(self):
        if not self._circuit_breaker.allow_request():
            raise GeneralLLMServiceError(
                "Circuit breaker OPEN: general LLM service has failed repeatedly. "
                "Requests are being rejected to prevent cascade failure."
            )

    async def chat(self, messages: List[dict], temperature: float = 0.0) -> str:
        """Send messages to the general LLM and return the response text.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature (default 0.0 for deterministic).

        Returns:
            The model's response text.

        Raises:
            GeneralLLMServiceError: If the service is unavailable.
        """
        self._check_circuit_breaker()
        try:
            result = await self._call_api(messages, temperature)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"General LLM service error: {e}")
            raise GeneralLLMServiceError(f"General LLM service unavailable: {e}") from e

    async def _call_api(self, messages: List[dict], temperature: float = 0.0) -> str:
        """Call the general LLM API."""
        logger.debug(f"Calling general LLM API ({self._model_name})...")

        payload = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temperature
        }

        response = await self._client.post(
            self._api_url,
            json=payload,
            headers=self._headers
        )

        if response.status_code == 200:
            result_data = response.json()
            result = result_data["choices"][0]["message"]["content"].strip()
            logger.debug(f"General LLM response: {result[:200]}...")
            return result
        else:
            logger.error(f"General LLM API error: {response.status_code} - {response.text}")
            raise Exception(f"API call failed with status {response.status_code}")

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()


# Global instance
general_llm_service = GeneralLLMService()
