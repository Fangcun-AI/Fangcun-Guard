"""Generate a policy-aware answer when a knowledge-base match is available."""

from typing import List

import httpx

from config import settings
from utils.i18n_loader import get_translation
from utils.logger import setup_logger

logger = setup_logger()


class ProxyAnswerService:
    """Guard-model client for constructive replacement answers."""

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=50, max_connections=100),
            http2=False,
        )
        self._headers = {
            "Authorization": f"Bearer {settings.guardrails_model_api_key}",
            "Content-Type": "application/json",
        }
        self._api_url = f"{settings.guardrails_model_api_url}/chat/completions"

    async def generate_proxy_answer(
        self,
        user_query: str,
        kb_reference: str,
        scanner_name: str,
        risk_level: str = "medium_risk",
        user_language: str = "en",
    ) -> str:
        messages = [
            {
                "role": "system",
                "content": self._build_system_prompt(
                    scanner_name, risk_level, user_language
                ),
            },
            {
                "role": "user",
                "content": self._build_user_message(
                    user_query, kb_reference, user_language
                ),
            },
        ]
        try:
            return await self._call_model(messages)
        except Exception as exc:
            logger.error(f"Failed to generate proxy answer: {exc}", exc_info=True)
            return self._get_fallback_message(scanner_name, user_language)

    def _build_system_prompt(
        self, scanner_name: str, risk_level: str, language: str
    ) -> str:
        if language == "zh":
            return (
                f"你是负责任的 AI 助手。当前问题触发了“{scanner_name}”风险，"
                f"等级为 {risk_level}。请基于参考资料，用自己的话给出简洁、守法、"
                "有建设性的回复。必要时礼貌拒绝有害请求，并给出安全替代建议。"
                "不要照抄参考资料。"
            )
        return (
            f"You are a responsible AI assistant. The request triggered {scanner_name} "
            f"at {risk_level}. Use the reference material to write a concise, lawful, "
            "constructive answer in your own words. Politely decline harmful requests "
            "when needed and offer safer alternatives. Do not copy the reference text."
        )

    def _build_user_message(
        self, user_query: str, kb_reference: str, language: str
    ) -> str:
        if language == "zh":
            return f"用户问题：\n{user_query}\n\n参考资料：\n{kb_reference}\n\n请生成安全回复。"
        return (
            f"User question:\n{user_query}\n\nReference material:\n{kb_reference}\n\n"
            "Write a safe response."
        )

    async def _call_model(self, messages: List[dict]) -> str:
        response = await self._client.post(
            self._api_url,
            headers=self._headers,
            json={
                "model": settings.guardrails_model_name,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500,
            },
        )
        if response.status_code != 200:
            raise RuntimeError(f"guard model returned HTTP {response.status_code}")
        return response.json()["choices"][0]["message"]["content"].strip()

    def _get_fallback_message(self, scanner_name: str, language: str) -> str:
        try:
            template = get_translation(
                language, "guardrail", "responseTemplates", "securityRisk"
            )
            return template.replace("{scanner_name}", scanner_name)
        except Exception:
            if language == "zh":
                return f"抱歉，我无法回答涉及{scanner_name}的问题。请联系专业人士或相关机构。"
            return (
                f"Sorry, I cannot answer questions involving {scanner_name}. "
                "Please contact a qualified professional or relevant organization."
            )

    async def close(self) -> None:
        await self._client.aclose()


proxy_answer_service = ProxyAnswerService()
