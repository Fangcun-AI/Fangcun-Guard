"""
Prompt Injection Guard — detection service.

Calls the Prompt Guard inference server (prompt_guard_server.py)
to classify input text for prompt injection / jailbreak attacks.
"""

import os
import logging
import time
from typing import List, Dict, Optional, Tuple

import httpx

from config import settings

logger = logging.getLogger(__name__)

PROMPT_GUARD_URL = os.getenv("PROMPT_GUARD_URL", settings.prompt_guard_url)
PROMPT_GUARD_TIMEOUT = float(os.getenv("PROMPT_GUARD_TIMEOUT", "5.0"))


class PromptInjectionService:
    """Service for detecting prompt injection via Prompt Guard model."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=PROMPT_GUARD_URL,
                timeout=PROMPT_GUARD_TIMEOUT,
            )
        return self._client

    async def classify(
        self,
        text: str,
        threshold: float = 0.5,
    ) -> Dict:
        """Classify a single text for prompt injection.

        Returns dict with: label, scores, is_injection, latency_ms
        """
        try:
            start = time.time()
            resp = await self.client.post("/classify", json={
                "text": text,
                "threshold": threshold,
            })
            resp.raise_for_status()
            data = resp.json()
            result = data["results"][0]
            result["total_latency_ms"] = round((time.time() - start) * 1000, 2)
            return result
        except Exception as e:
            logger.error(f"Prompt Guard classify failed: {e}")
            # Fail-open: treat as benign if service unavailable
            return {
                "label": "BENIGN",
                "scores": {"BENIGN": 1.0, "INJECTION": 0.0, "JAILBREAK": 0.0},
                "is_injection": False,
                "latency_ms": 0,
                "total_latency_ms": 0,
                "error": str(e),
            }

    async def classify_batch(
        self,
        texts: List[str],
        threshold: float = 0.5,
    ) -> List[Dict]:
        """Classify multiple texts in one request."""
        try:
            start = time.time()
            resp = await self.client.post("/classify", json={
                "texts": texts,
                "threshold": threshold,
            })
            resp.raise_for_status()
            data = resp.json()
            total_ms = round((time.time() - start) * 1000, 2)
            for r in data["results"]:
                r["total_latency_ms"] = total_ms
            return data["results"]
        except Exception as e:
            logger.error(f"Prompt Guard batch classify failed: {e}")
            return [{
                "label": "BENIGN",
                "scores": {"BENIGN": 1.0, "INJECTION": 0.0, "JAILBREAK": 0.0},
                "is_injection": False,
                "latency_ms": 0,
                "total_latency_ms": 0,
                "error": str(e),
            } for _ in texts]

    async def check_messages(
        self,
        messages: List[Dict],
        threshold: float = 0.5,
        scan_user: bool = True,
        scan_system: bool = True,
    ) -> Tuple[bool, List[Dict]]:
        """Check all messages in a conversation for injection.

        Returns (is_injection, details) where details is a list of
        per-message classification results.
        """
        texts_to_check = []
        indices = []

        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content or not isinstance(content, str):
                continue
            if role == "user" and scan_user:
                texts_to_check.append(content[:2000])
                indices.append(i)
            elif role == "system" and scan_system:
                texts_to_check.append(content[:2000])
                indices.append(i)

        if not texts_to_check:
            return False, []

        results = await self.classify_batch(texts_to_check, threshold)

        is_injection = False
        details = []
        for idx, result in zip(indices, results):
            msg = messages[idx]
            detail = {
                "message_index": idx,
                "role": msg.get("role", ""),
                "content_preview": msg.get("content", "")[:100],
                **result,
            }
            details.append(detail)
            if result.get("is_injection", False):
                is_injection = True

        return is_injection, details

    async def health_check(self) -> bool:
        """Check if Prompt Guard server is reachable."""
        try:
            resp = await self.client.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Global instance
prompt_injection_service = PromptInjectionService()
