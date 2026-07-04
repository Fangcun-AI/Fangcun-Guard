"""Chat-route orchestration helpers for proxy API handlers."""

from dataclasses import dataclass
from typing import Any, Optional
import time

from fastapi.responses import JSONResponse

from database.connection import get_admin_db_session
from services.model_route_service import model_route_service
from utils.logger import setup_logger


logger = setup_logger()


@dataclass(frozen=True)
class ModelDispatchPlan:
    """Resolved upstream config and actual model choice for a chat request."""

    route_config: Any
    effective_config: Any
    effective_model_name: str


@dataclass(frozen=True)
class OutputInspection:
    """Derived output-inspection fields from a non-streaming model response."""

    output_content: str
    combined_content: str
    tool_calls_text: str


async def resolve_chat_route_config(tenant_id: str, application_id: Optional[str], model_name: str):
    """Load the route-matched upstream config for the requested model."""
    db = get_admin_db_session()
    try:
        return model_route_service.find_matching_route(
            db=db,
            tenant_id=tenant_id,
            model_name=model_name,
            application_id=application_id,
        )
    finally:
        db.close()


def build_missing_route_response(model_name: str) -> JSONResponse:
    """Return a standard route-missing payload."""
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "message": f"No routing rule configured for model '{model_name}'. Please configure a model routing rule in Security Gateway > Model Routes.",
                "type": "model_route_not_found",
            }
        },
    )


def plan_model_dispatch(requested_model_name: str, route_config, guard_result: dict[str, Any]) -> ModelDispatchPlan:
    """Decide which upstream config and model name should actually be called."""
    effective_config = guard_result.get("modified_model_config", route_config)
    disposal_action = guard_result.get("disposal_action", "pass")
    effective_model_name = requested_model_name

    if disposal_action == "switch_private_model" and effective_config != route_config:
        if effective_config.default_private_model_name:
            effective_model_name = effective_config.default_private_model_name
        elif effective_config.private_model_names:
            effective_model_name = effective_config.private_model_names[0]
        logger.info(
            "Switched to private model %s, using model name: %s",
            effective_config.config_name,
            effective_model_name,
        )

    return ModelDispatchPlan(
        route_config=route_config,
        effective_config=effective_config,
        effective_model_name=effective_model_name,
    )


def collect_request_tools(request_data) -> list[Any]:
    """Collect tool definitions regardless of whether they came from extra_body or extra fields."""
    if request_data.extra_body and isinstance(request_data.extra_body, dict):
        tools = request_data.extra_body.get("tools", [])
        if tools:
            return tools
    return getattr(request_data, "tools", None) or []


async def run_plugin_input_hook(
    *,
    request_id: str,
    tenant_id: str,
    application_id: Optional[str],
    request_model: str,
    clean_messages: list[dict[str, Any]],
    tools_list: list[Any],
    extra_body: Optional[dict[str, Any]],
):
    """Run plugin input checks and return a blocked response when needed."""
    if not application_id or not tools_list:
        return None

    try:
        from plugins.hooks import HookContext, HookPhase
        from plugins.registry import plugin_registry

        input_ctx = HookContext(
            phase=HookPhase.INPUT,
            request_id=request_id,
            tenant_id=str(tenant_id),
            application_id=str(application_id),
            messages=clean_messages,
            content="",
            tools=tools_list,
            extra_body=extra_body,
        )
        input_results = await plugin_registry.dispatch_hook(HookPhase.INPUT, input_ctx)
        for plugin_result in input_results:
            if plugin_result.action == "block" and plugin_result.blocked_message:
                logger.warning(
                    "[%s] Plugin '%s' blocked input: %s",
                    request_id,
                    plugin_result.plugin_name,
                    plugin_result.categories,
                )
                return JSONResponse(
                    status_code=200,
                    content={
                        "id": request_id,
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": request_model,
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": plugin_result.blocked_message},
                                "finish_reason": "content_filter",
                            }
                        ],
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    },
                )
            if plugin_result.action == "warn":
                logger.info(
                    "[%s] Plugin '%s' warning: %s",
                    request_id,
                    plugin_result.plugin_name,
                    plugin_result.categories,
                )
    except Exception as exc:
        logger.error("[%s] Plugin input check failed: %s", request_id, exc)

    return None


def inspect_nonstream_output(message: dict[str, Any], request_id: str) -> OutputInspection:
    """Flatten message text and tool calls into a single detection payload."""
    output_content = message.get("content", "")
    tool_calls_text_parts = []
    for tool_call in message.get("tool_calls") or []:
        if "function" not in tool_call:
            continue
        function_info = tool_call["function"]
        function_name = function_info.get("name", "")
        function_args = function_info.get("arguments", "")
        tool_calls_text_parts.append(f"[工具调用] {function_name}({function_args})")

    tool_calls_text = " ".join(tool_calls_text_parts)
    if tool_calls_text:
        logger.debug("[%s] Non-streaming detected tool_calls: %s...", request_id, tool_calls_text[:100])

    combined_content = output_content
    if tool_calls_text:
        combined_content = f"{output_content}\n{tool_calls_text}"

    return OutputInspection(
        output_content=output_content,
        combined_content=combined_content,
        tool_calls_text=tool_calls_text,
    )


async def run_plugin_output_hook(
    *,
    request_id: str,
    tenant_id: str,
    application_id: Optional[str],
    input_messages: list[dict[str, Any]],
    output_content: str,
    message: dict[str, Any],
    extra_body: Optional[dict[str, Any]],
    output_blocked: bool,
) -> Optional[str]:
    """Run plugin output checks and return a replacement message when blocked."""
    if output_blocked or not application_id:
        return None

    try:
        from plugins.hooks import HookContext, HookPhase
        from plugins.registry import plugin_registry

        output_ctx = HookContext(
            phase=HookPhase.OUTPUT,
            request_id=request_id,
            tenant_id=str(tenant_id),
            application_id=str(application_id),
            messages=input_messages,
            content=output_content,
            tool_calls=message.get("tool_calls"),
            extra_body=extra_body,
            output_blocked=output_blocked,
        )
        output_results = await plugin_registry.dispatch_hook(HookPhase.OUTPUT, output_ctx)
        for plugin_result in output_results:
            if plugin_result.action == "block" and plugin_result.blocked_message:
                logger.warning(
                    "[%s] Plugin '%s' blocked output: %s",
                    request_id,
                    plugin_result.plugin_name,
                    plugin_result.categories,
                )
                return plugin_result.blocked_message
            if plugin_result.action == "warn":
                logger.info(
                    "[%s] Plugin '%s' flagged output: %s",
                    request_id,
                    plugin_result.plugin_name,
                    plugin_result.categories,
                )
    except Exception as exc:
        logger.error("[%s] Plugin output check failed: %s", request_id, exc)

    return None


def apply_output_text(message: dict[str, Any], final_content: str, output_blocked: bool) -> None:
    """Write the inspected content back into the response payload."""
    if output_blocked:
        message["content"] = final_content
        if "tool_calls" in message:
            del message["tool_calls"]
        return

    if "content" in message:
        message["content"] = final_content
