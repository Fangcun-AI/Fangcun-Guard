import asyncio

from models.responses import ComplianceResult, SecurityResult
from services.guardrail_outcome_service import GuardrailOutcomeService


class StubRiskConfigService:
    def __init__(self, disabled=()):
        self.disabled = set(disabled)

    def is_risk_type_enabled(self, tenant_id=None, risk_type=None):
        return risk_type not in self.disabled


def build_service(disabled=()):
    return GuardrailOutcomeService(db=None, risk_config_service=StubRiskConfigService(disabled))


def test_model_verdict_parser_handles_safe_and_disabled_paths():
    service = build_service(disabled={"S2"})

    compliance, security = service.parse_model_verdict("safe", tenant_id="tenant-a")
    assert compliance.risk_level == "no_risk"
    assert security.risk_level == "no_risk"

    compliance, security = service.parse_model_verdict("unsafe\nS2", tenant_id="tenant-a")
    assert compliance.risk_level == "no_risk"
    assert security.risk_level == "no_risk"


def test_model_verdict_parser_partitions_multiple_categories():
    service = build_service()

    compliance, security = service.parse_model_verdict("unsafe\nS4, S9")

    assert compliance.risk_level == "medium_risk"
    assert compliance.categories == ["Harm to Minors"]
    assert security.risk_level == "high_risk"
    assert security.categories == ["Prompt Attacks"]


def test_finalization_selects_pass_replace_and_reject_actions():
    async def exercise():
        service = build_service()

        async def suggest_answer(*args, **kwargs):
            return "suggested"

        service.craft_suggest_answer = suggest_answer
        safe = ComplianceResult(risk_level="no_risk", categories=[])
        low = ComplianceResult(risk_level="low_risk", categories=["Low"])
        medium = ComplianceResult(risk_level="medium_risk", categories=["Medium"])
        high = SecurityResult(risk_level="high_risk", categories=["High"])
        safe_security = SecurityResult(risk_level="no_risk", categories=[])

        assert await service.finalize_guardrail_outcome(safe, safe_security) == (
            "no_risk",
            "pass",
            None,
        )
        assert await service.finalize_guardrail_outcome(low, safe_security) == (
            "low_risk",
            "replace",
            "suggested",
        )
        assert await service.finalize_guardrail_outcome(medium, high) == (
            "high_risk",
            "reject",
            "suggested",
        )

    asyncio.run(exercise())
