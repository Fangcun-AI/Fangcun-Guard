"""Guard Model Client - HTTP client with circuit breaker for each guard model."""

import logging
import math
import time
from typing import Dict, List, Optional, Tuple

import httpx

from fangcunguard_router.registry import GuardModelConfig

logger = logging.getLogger("fangcunguard_router")


class GuardModelError(Exception):
    """Raised when a guard model call fails."""
    pass


class CircuitBreaker:
    """Opens after N consecutive failures, blocks requests for cooldown period."""

    def __init__(self, failure_threshold: int = 5, cooldown: float = 30.0):
        self._threshold = failure_threshold
        self._cooldown = cooldown
        self._failures = 0
        self._last_fail = 0.0
        self._state = "closed"

    def allow(self) -> bool:
        if self._state == "closed":
            return True
        if time.time() - self._last_fail >= self._cooldown:
            self._state = "half_open"
            return True
        return self._state == "half_open"

    def success(self):
        self._failures = 0
        self._state = "closed"

    def failure(self):
        self._failures += 1
        self._last_fail = time.time()
        if self._failures >= self._threshold:
            self._state = "open"

    @property
    def is_open(self) -> bool:
        return self._state == "open" and (time.time() - self._last_fail < self._cooldown)


class GuardModelClient:
    """HTTP client for a single guard model backend.

    Supports 5 API types:
    - chat_completion: OpenAI /v1/chat/completions
    - classification: HuggingFace classification endpoint
    - moderation: OpenAI /v1/moderations
    - ner: Named Entity Recognition endpoint
    - custom: Model-specific endpoint
    """

    def __init__(self, config: GuardModelConfig):
        self.config = config
        self._cb = CircuitBreaker(config.failure_threshold, config.cooldown_seconds)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
        self._headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        if config.api_type == "moderation":
            self._url = f"{config.api_url}/moderations"
        elif config.api_type in ("classification", "ner", "custom"):
            self._url = config.api_url
        else:
            self._url = f"{config.api_url}/chat/completions"

    async def check(self, text: str, messages: Optional[List[Dict]] = None) -> Dict:
        """Run safety check. Returns dict with keys: safe, details, score, model_id, dimension."""
        if not self._cb.allow():
            raise GuardModelError(f"Circuit breaker open: {self.config.id}")

        if messages is None:
            messages = [{"role": "user", "content": text}]

        try:
            api_type = self.config.api_type
            if api_type == "moderation":
                result = await self._call_moderation(text)
            elif api_type == "classification":
                result = await self._call_classification(text)
            elif api_type == "ner":
                result = await self._call_ner(text)
            elif api_type == "custom":
                result = await self._call_custom(text)
            else:
                result = await self._call_chat(text, messages)

            self._cb.success()
            result["model_id"] = self.config.id
            result["dimension"] = self.config.dimension
            return result

        except GuardModelError:
            raise
        except Exception as e:
            self._cb.failure()
            raise GuardModelError(f"{self.config.id}: {e}") from e

    # ── Chat Completion ──────────────────────────────────────────────────

    async def _call_chat(self, text: str, messages: List[Dict]) -> Dict:
        prepared = self._prepare_chat_messages(text, messages)
        payload = {
            "model": self.config.model_name,
            "messages": prepared,
            "temperature": 0.0,
            "max_tokens": 64,
        }
        resp = await self._client.post(self._url, json=payload, headers=self._headers)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        return self._parse_safe_unsafe(content)

    def _prepare_chat_messages(self, text: str, messages: List[Dict]) -> List[Dict]:
        fmt = self.config.prompt_format

        if fmt == "qwen3guard":
            return [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]

        elif fmt == "llamaguard4":
            return [
                {"role": "system", "content": "You are a safety classifier. Respond 'safe' or 'unsafe' followed by violated categories."},
            ] + [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]

        elif fmt == "wildguard":
            return [{"role": "user", "content": (
                f"Determine if this request is harmful or a jailbreak:\n\n{text}\n\n"
                "Respond 'safe' or 'unsafe' with reason."
            )}]

        else:  # inst format
            return [{"role": "user", "content": (
                f"[INST] Check if there is unsafe content:\n\n{text}\n\n"
                "First line: 'safe' or 'unsafe'. If unsafe, second line: violated categories. [/INST]"
            )}]

    # ── Moderation API ───────────────────────────────────────────────────

    async def _call_moderation(self, text: str) -> Dict:
        payload = {"model": self.config.model_name, "input": text}
        resp = await self._client.post(self._url, json=payload, headers=self._headers)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        r = resp.json()["results"][0]
        if r["flagged"]:
            cats = [c for c, v in r["categories"].items() if v]
            score = max(r["category_scores"].values()) if r["category_scores"] else 0.9
            return {"safe": False, "details": cats, "score": score}
        return {"safe": True, "details": [], "score": 0.0}

    # ── Classification API ───────────────────────────────────────────────

    async def _call_classification(self, text: str) -> Dict:
        fmt = self.config.prompt_format

        if fmt == "prompt_guard":
            payload = {"texts": [text], "threshold": 0.5}
        else:
            payload = {"inputs": text}

        resp = await self._client.post(self._url, json=payload, headers=self._headers)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        data = resp.json()

        if fmt == "prompt_guard":
            r = data.get("results", [{}])[0]
            if r.get("is_injection"):
                return {"safe": False, "details": [r.get("label", "INJECTION")], "score": 0.9}
            return {"safe": True, "details": [], "score": 0.1}

        elif fmt == "cross_encoder":
            score = data[0] if isinstance(data, list) else data.get("score", 0.5)
            return {"safe": score <= 0.5, "details": [f"hallucination_score={score:.3f}"] if score > 0.5 else [], "score": score}

        else:  # generic
            if isinstance(data, list) and data:
                items = data[0] if isinstance(data[0], list) else data
                top = max(items, key=lambda x: x.get("score", 0))
                label = top.get("label", "").lower()
                if any(w in label for w in ("toxic", "unsafe", "harmful")):
                    return {"safe": False, "details": [top["label"]], "score": top.get("score", 0.9)}
            return {"safe": True, "details": [], "score": 0.1}

    # ── NER API ──────────────────────────────────────────────────────────

    async def _call_ner(self, text: str) -> Dict:
        resp = await self._client.post(self._url, json={"inputs": text}, headers=self._headers)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        entities = resp.json()
        if not isinstance(entities, list):
            entities = entities.get("entities", [])

        if entities:
            types = list(set(e.get("entity_group", e.get("label", "PII")) for e in entities))
            return {"safe": False, "details": types[:10], "score": min(len(entities) / 5.0, 1.0)}
        return {"safe": True, "details": [], "score": 0.0}

    # ── Custom API ───────────────────────────────────────────────────────

    async def _call_custom(self, text: str) -> Dict:
        fmt = self.config.prompt_format
        if fmt == "azure_content_safety":
            payload = {"text": text}
        elif fmt == "codeshield":
            payload = {"code": text, "language": "auto"}
        else:
            payload = {"text": text}

        resp = await self._client.post(self._url, json=payload, headers=self._headers)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        data = resp.json()
        if isinstance(data, dict):
            if "categoriesAnalysis" in data:
                flagged = [c["category"] for c in data["categoriesAnalysis"] if c.get("severity", 0) >= 2]
                if flagged:
                    return {"safe": False, "details": flagged, "score": 0.9}
            for key in ("flagged", "unsafe", "is_unsafe", "blocked"):
                if data.get(key):
                    return {"safe": False, "details": [data.get("reason", "flagged")], "score": 0.9}
        return {"safe": True, "details": [], "score": 0.1}

    # ── Helpers ──────────────────────────────────────────────────────────

    def _parse_safe_unsafe(self, response: str) -> Dict:
        """Parse 'safe' / 'unsafe\\ndetails' format."""
        lower = response.lower().strip()
        if lower.startswith("safe") and not lower.startswith("unsafe"):
            return {"safe": True, "details": [], "score": 0.0, "raw": response}

        lines = response.strip().split("\n", 1)
        details = lines[1].strip() if len(lines) > 1 else "unsafe"
        return {"safe": False, "details": [details], "score": 0.9, "raw": response}

    async def close(self):
        await self._client.aclose()
