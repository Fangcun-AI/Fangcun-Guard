"""Response shaping helpers for proxy chat endpoints."""

import json
import time
from typing import Any, Optional, Sequence

import httpx
from fastapi.responses import StreamingResponse

from utils.logger import setup_logger


logger = setup_logger()

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def build_blocked_chat_response(request_id: str, model_name: str, detection_result: dict[str, Any]) -> dict[str, Any]:
    """Build a standard blocked chat-completion payload."""
    suggest_answer = detection_result.get("suggest_answer")
    response = {
        "id": f"chatcmpl-{request_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": suggest_answer,
                },
                "finish_reason": "content_filter",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "detection_info": {
            "suggest_action": detection_result.get("suggest_action"),
            "suggest_answer": suggest_answer,
            "overall_risk_level": detection_result.get("overall_risk_level"),
            "compliance_result": detection_result.get("compliance_result"),
            "security_result": detection_result.get("security_result"),
            "request_id": detection_result.get("request_id"),
        },
    }
    return response


def build_blocked_chat_stream(
    *,
    request_id: str,
    model_name: str,
    input_messages: Sequence[dict[str, Any]],
    detection_result: dict[str, Any],
) -> StreamingResponse:
    """Render a blocked request as OpenAI-style SSE."""
    suggest_answer = detection_result.get("suggest_answer") or ""
    user_content = _last_user_content(input_messages)
    scanner_categories = detection_result.get("security_result", {}).get("categories", [])
    scanner_label = scanner_categories[0] if scanner_categories else "policy violation"
    system_prompt = _build_contextual_rejection_prompt(scanner_label)

    async def blocked_stream_generator():
        from config import settings

        api_url = f"{settings.guardrails_model_api_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.guardrails_model_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.guardrails_model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.7,
            "max_tokens": 500,
            "stream": True,
        }

        chunk_id = f"chatcmpl-{request_id}"
        created = int(time.time())

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
                async with client.stream("POST", api_url, json=payload, headers=headers) as response:
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if not content:
                            continue

                        chunk = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_name,
                            "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
                        }
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error("Streaming contextual rejection failed: %s", exc)
            fallback_chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_name,
                "choices": [{"index": 0, "delta": {"content": suggest_answer}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(fallback_chunk, ensure_ascii=False)}\n\n"

        final_chunk = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "content_filter"}],
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        blocked_stream_generator(),
        media_type="text/event-stream",
        headers=dict(SSE_HEADERS),
    )


def wrap_nonstream_chat_response_as_sse(
    *,
    model_response: dict[str, Any],
    request_id: str,
    output_detection_result: Optional[dict[str, Any]],
) -> StreamingResponse:
    """Wrap a buffered response as SSE for stream clients."""

    def _nonstream_to_sse():
        resp_content = ""
        finish = "stop"
        resp_tool_calls = None
        resp_model = model_response.get("model", "unknown")
        resp_id = model_response.get("id", f"chatcmpl-{request_id}")
        created = model_response.get("created", int(time.time()))
        if model_response.get("choices"):
            choice = model_response["choices"][0]
            resp_content = choice.get("message", {}).get("content", "") or ""
            finish = choice.get("finish_reason", "stop")
            resp_tool_calls = choice.get("message", {}).get("tool_calls")

        def _make_chunk(delta: dict[str, Any], finish_reason: Optional[str] = None) -> str:
            chunk = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": resp_model,
                "choices": [{"index": 0, "delta": delta}],
            }
            if finish_reason:
                chunk["choices"][0]["finish_reason"] = finish_reason
            return f"data: {json.dumps(chunk)}\n\n"

        yield _make_chunk({"role": "assistant", "content": ""})

        if resp_tool_calls:
            tool_chunk_size = 200
            for index, tool_call in enumerate(resp_tool_calls):
                tool_call_id = tool_call.get("id", f"call_{index}")
                tool_name = tool_call.get("function", {}).get("name", "")
                yield _make_chunk(
                    {
                        "tool_calls": [
                            {
                                "index": index,
                                "id": tool_call_id,
                                "type": tool_call.get("type", "function"),
                                "function": {"name": tool_name, "arguments": ""},
                            }
                        ]
                    }
                )

                args_str = tool_call.get("function", {}).get("arguments", "") or ""
                for start in range(0, max(len(args_str), 1), tool_chunk_size):
                    piece = args_str[start : start + tool_chunk_size]
                    yield _make_chunk({"tool_calls": [{"index": index, "function": {"arguments": piece}}]})

        if resp_content and not resp_tool_calls:
            chunk_size = 200
            for start in range(0, len(resp_content), chunk_size):
                piece = resp_content[start : start + chunk_size]
                yield _make_chunk({"content": piece})

        stop_chunk = _make_chunk({}, finish_reason=finish)
        if finish == "content_filter" and output_detection_result:
            stop_obj = json.loads(stop_chunk[len("data: ") : -2])
            stop_obj["detection_info"] = {
                "suggest_action": output_detection_result.get("suggest_action"),
                "suggest_answer": output_detection_result.get("suggest_answer"),
                "overall_risk_level": output_detection_result.get("overall_risk_level"),
            }
            stop_chunk = f"data: {json.dumps(stop_obj)}\n\n"

        yield stop_chunk
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _nonstream_to_sse(),
        media_type="text/event-stream",
        headers=dict(SSE_HEADERS),
    )


def _last_user_content(input_messages: Sequence[dict[str, Any]]) -> str:
    for message in reversed(input_messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def _build_contextual_rejection_prompt(scanner_label: str) -> str:
    return (
        f"你是 FangcunGuard 安全系统。用户的请求触发了安全规则「{scanner_label}」。\n\n"
        f"你的任务：\n"
        f"1. 简要说明你理解用户想做什么\n"
        f"2. 具体指出请求中哪些内容触发了安全规则，以及为什么这些内容有风险\n"
        f"3. 给出建设性的替代建议\n\n"
        f"要求：\n"
        f'- 回复要专业、有分析性，不要笼统地说"违反了策略"\n'
        f"- 不要生成用户要求的危险内容\n"
        f"- 控制在 200 字以内"
    )
