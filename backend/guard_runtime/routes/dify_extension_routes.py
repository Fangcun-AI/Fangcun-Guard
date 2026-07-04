"""Dify moderation extension adapter."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from config import settings
from database.connection import get_admin_db
from models.requests import DifyModerationRequest, GuardrailRequest, Message
from models.responses import DifyModerationResponse
from services.guardrail_service import GuardrailPipeline
from utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(tags=["Dify Moderation"])
_MASK_MARKERS = ("[PHONE]", "[EMAIL]", "[ID]", "[ADDRESS]", "[NAME]", "***", "[MASKED]")


def _tenant_id(request: Request) -> str:
    auth_context = getattr(request.state, "auth_context", None)
    data = auth_context.get("data", {}) if isinstance(auth_context, dict) else {}
    tenant_id = data.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Valid API key required from FangcunGuard platform")
    return str(tenant_id)


def _client(request: Request):
    return (request.client.host if request.client else None), request.headers.get("user-agent")


def _is_desensitized(text: Optional[str]) -> bool:
    return bool(text) and any(marker in text for marker in _MASK_MARKERS)


async def _inspect(messages, guardrail_service, tenant_id, ip_address, user_agent):
    return await guardrail_service.run_guardrail_check(
        GuardrailRequest(model=settings.guardrails_model_name, messages=messages),
        ip_address=ip_address,
        user_agent=user_agent,
        tenant_id=tenant_id,
    )


@router.post("/dify/moderation", response_model=DifyModerationResponse, response_model_exclude_none=True)
async def dify_moderation(request_data: DifyModerationRequest, request: Request, db: Session = Depends(get_admin_db)):
    try:
        if request_data.point == "ping":
            return DifyModerationResponse(result="pong")
        tenant_id = _tenant_id(request)
        ip_address, user_agent = _client(request)
        service = GuardrailPipeline(db)
        if request_data.point == "app.moderation.input":
            return await handle_input_moderation(request_data, service, tenant_id, ip_address, user_agent)
        if request_data.point == "app.moderation.output":
            return await handle_output_moderation(request_data, service, tenant_id, ip_address, user_agent)
        raise HTTPException(status_code=400, detail=f"Unsupported extension point: {request_data.point}")
    except HTTPException:
        raise
    except Exception as error:
        logger.error("Dify moderation error: %s", error, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {error}")


async def handle_input_moderation(
    request_data: DifyModerationRequest,
    guardrail_service: GuardrailPipeline,
    tenant_id: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> DifyModerationResponse:
    params = request_data.params
    if not params:
        raise HTTPException(status_code=400, detail="Missing params for app.moderation.input")
    values = []
    for name, value in (params.inputs or {}).items():
        if value and isinstance(value, str):
            values.append(("input", name, value))
    if params.query and isinstance(params.query, str):
        values.append(("query", "query", params.query))
    results = []
    for value_type, key, value in values:
        results.append(
            {
                "type": value_type,
                "key": key,
                "value": value,
                "result": await inspect_prompt(value, guardrail_service, tenant_id, ip_address, user_agent),
            }
        )
    return fold_input_results(results, params)


async def handle_output_moderation(
    request_data: DifyModerationRequest,
    guardrail_service: GuardrailPipeline,
    tenant_id: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> DifyModerationResponse:
    params = request_data.params
    if not params or not params.text:
        raise HTTPException(status_code=400, detail="Missing text for app.moderation.output")
    result = await inspect_response(
        "The answer of the assistant is:", params.text, guardrail_service, tenant_id, ip_address, user_agent
    )
    return fold_output_result(result, params.text)


async def inspect_prompt(prompt: str, guardrail_service: GuardrailPipeline, tenant_id: str, ip_address: Optional[str], user_agent: Optional[str]):
    return await _inspect([Message(role="user", content=prompt)], guardrail_service, tenant_id, ip_address, user_agent)


async def inspect_response(
    prompt: str,
    response: str,
    guardrail_service: GuardrailPipeline,
    tenant_id: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
):
    return await _inspect(
        [Message(role="user", content=prompt), Message(role="assistant", content=response)],
        guardrail_service,
        tenant_id,
        ip_address,
        user_agent,
    )


def _direct(answer: str, flagged: bool = True) -> DifyModerationResponse:
    return DifyModerationResponse(flagged=flagged, action="direct_output", preset_response=answer)


def fold_input_results(detection_results: list, params) -> DifyModerationResponse:
    rejected_answer = None
    replaced_answer = None
    overridden_inputs = {}
    overridden_query = None
    replacements = []

    for item in detection_results:
        result = item["result"]
        answer = result.suggest_answer or item["value"]
        if result.suggest_action == "reject":
            rejected_answer = rejected_answer or result.suggest_answer
            continue
        if result.suggest_action == "replace":
            replaced_answer = replaced_answer or result.suggest_answer
            replacements.append(result.suggest_answer)
        if item["type"] == "input":
            overridden_inputs[item["key"]] = answer if result.suggest_action == "replace" else item["value"]
        else:
            overridden_query = answer if result.suggest_action == "replace" else item["value"]

    if rejected_answer is not None or any(item["result"].suggest_action == "reject" for item in detection_results):
        return _direct(rejected_answer or "Your content violates our usage policy.")
    if replacements:
        if any(_is_desensitized(answer) for answer in replacements):
            return DifyModerationResponse(
                flagged=True,
                action="overridden",
                inputs=overridden_inputs if params.inputs else None,
                query=overridden_query,
            )
        return _direct(replaced_answer or "Your content has been moderated.")
    return _direct("", flagged=False)


def fold_output_result(result, original_text: str) -> DifyModerationResponse:
    if result.suggest_action == "reject":
        return _direct(result.suggest_answer or "Your content violates our usage policy.")
    if result.suggest_action == "replace":
        answer = result.suggest_answer or original_text
        if _is_desensitized(answer):
            return DifyModerationResponse(flagged=True, action="overridden", text=answer)
        return _direct(answer)
    return _direct("", flagged=False)
