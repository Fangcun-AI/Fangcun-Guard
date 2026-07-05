import asyncio

from services.proxy_answer_service import ProxyAnswerService


def build_service():
    return ProxyAnswerService.__new__(ProxyAnswerService)


def test_proxy_answer_prompt_is_language_specific_and_compact():
    service = build_service()

    english = service._build_system_prompt("Prompt Attacks", "high_risk", "en")
    chinese = service._build_system_prompt("提示词攻击", "high_risk", "zh")

    assert "Prompt Attacks" in english
    assert "high_risk" in english
    assert "提示词攻击" in chinese


def test_proxy_answer_uses_fallback_after_model_error():
    async def exercise():
        service = build_service()

        async def fail(messages):
            raise RuntimeError("offline")

        service._call_model = fail
        service._get_fallback_message = lambda scanner_name, language: "fallback"

        assert await service.generate_proxy_answer("question", "reference", "Risk") == "fallback"

    asyncio.run(exercise())
