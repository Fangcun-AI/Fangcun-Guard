"""
Reverse proxy API route - OpenAI compatible guardrail proxy interface
"""
from fastapi import APIRouter, HTTPException, Request  # fcg-rewrite
from fastapi.responses import JSONResponse  # fcg-rewrite
from typing import Dict, Any, Optional, List, Union  # fcg-rewrite
from pydantic import BaseModel  # fcg-rewrite
import time  # fcg-rewrite

from services.proxy_guard_pipeline import run_input_guard_checks, run_output_guard_checks  # fcg-rewrite
from services.proxy_chat_flow import (  # fcg-rewrite
    apply_output_text,  # fcg-rewrite
    build_missing_route_response,  # fcg-rewrite
    collect_request_tools,  # fcg-rewrite
    inspect_nonstream_output,  # fcg-rewrite
    plan_model_dispatch,  # fcg-rewrite
    resolve_chat_route_config,  # fcg-rewrite
    run_plugin_input_hook,  # fcg-rewrite
    run_plugin_output_hook,  # fcg-rewrite
)
from services.proxy_request_context import (  # fcg-rewrite
    apply_content_overrides,  # fcg-rewrite
    apply_proxy_ban_check,  # fcg-rewrite
    build_chat_messages,  # fcg-rewrite
    ensure_image_detection_subscription,  # fcg-rewrite
    merge_passthrough_fields,  # fcg-rewrite
    resolve_proxy_request_context,  # fcg-rewrite
    should_force_nonstream,  # fcg-rewrite
)
from services.proxy_response_adapter import (  # fcg-rewrite
    build_blocked_chat_response,  # fcg-rewrite
    build_blocked_chat_stream,  # fcg-rewrite
    wrap_nonstream_chat_response_as_sse,  # fcg-rewrite
)
from services.proxy_service import proxy_service  # fcg-rewrite
from services.proxy_streaming import (  # fcg-rewrite
    get_provider_from_url,  # fcg-rewrite
    stream_gateway_response,  # fcg-rewrite
)
from utils.logger import setup_logger  # fcg-rewrite
router = APIRouter()  # fcg-rewrite
logger = setup_logger()  # fcg-rewrite

# ============================================================================
# Gateway Pattern Response Handlers (simplified for MVP)
# ============================================================================

class OpenAIMessage(BaseModel):  # fcg-rewrite
    role: str  # fcg-rewrite
    content: Optional[Union[str, List[Any]]] = None  # fcg-rewrite
    name: Optional[str] = None  # fcg-rewrite

    class Config:  # fcg-rewrite
        extra = "allow"  # fcg-rewrite

class ChatCompletionRequest(BaseModel):  # fcg-rewrite
    model: str  # fcg-rewrite
    messages: List[OpenAIMessage]  # fcg-rewrite
    temperature: Optional[float] = None  # fcg-rewrite
    top_p: Optional[float] = None  # fcg-rewrite
    n: Optional[int] = 1  # fcg-rewrite
    stream: Optional[bool] = False  # fcg-rewrite
    stop: Optional[Union[str, List[str]]] = None  # fcg-rewrite
    max_tokens: Optional[int] = None  # fcg-rewrite
    presence_penalty: Optional[float] = None  # fcg-rewrite
    frequency_penalty: Optional[float] = None  # fcg-rewrite
    logit_bias: Optional[Dict[str, int]] = None  # fcg-rewrite
    user: Optional[str] = None  # fcg-rewrite
    # OpenAI SDK extra parameters support
    extra_body: Optional[Dict[str, Any]] = None  # fcg-rewrite

    class Config:  # fcg-rewrite
        extra = "allow"  # Allow extra fields to pass through  # fcg-rewrite

class CompletionRequest(BaseModel):  # fcg-rewrite
    model: str  # fcg-rewrite
    prompt: Union[str, List[str]]  # fcg-rewrite
    temperature: Optional[float] = None  # fcg-rewrite
    top_p: Optional[float] = None  # fcg-rewrite
    n: Optional[int] = 1  # fcg-rewrite
    stream: Optional[bool] = False  # fcg-rewrite
    logprobs: Optional[int] = None  # fcg-rewrite
    echo: Optional[bool] = False  # fcg-rewrite
    stop: Optional[Union[str, List[str]]] = None  # fcg-rewrite
    max_tokens: Optional[int] = None  # fcg-rewrite
    presence_penalty: Optional[float] = None  # fcg-rewrite
    frequency_penalty: Optional[float] = None  # fcg-rewrite
    best_of: Optional[int] = None  # fcg-rewrite
    logit_bias: Optional[Dict[str, int]] = None  # fcg-rewrite
    user: Optional[str] = None  # fcg-rewrite
    # OpenAI SDK extra parameters support
    extra_body: Optional[Dict[str, Any]] = None  # fcg-rewrite

    class Config:  # fcg-rewrite
        extra = "allow"  # Allow extra fields to pass through  # fcg-rewrite

@router.get("/v1/models")  # fcg-rewrite
async def list_models(request: Request):  # fcg-rewrite
    """List models configured for tenant"""
    try:
        request_scope = resolve_proxy_request_context(  # fcg-rewrite
            request,  # fcg-rewrite
            extra_body=None,  # fcg-rewrite
            route_label="List models",  # fcg-rewrite
            default_app_log_label="Model list proxy",  # fcg-rewrite
        )
        tenant_id = request_scope.tenant_id  # fcg-rewrite
        models = await proxy_service.list_tenant_models(tenant_id)  # fcg-rewrite

        return {  # fcg-rewrite
            "object": "list",  # fcg-rewrite
            "data": [  # fcg-rewrite
                {
                    "id": model.config_name,  # fcg-rewrite
                    "object": "model",  # fcg-rewrite
                    "created": int(model.created_at.timestamp()),  # fcg-rewrite
                    "owned_by": model.api_base_url.split('//')[1].split('.')[0] if '//' in model.api_base_url else "unknown",  # fcg-rewrite
                    "permission": [],  # fcg-rewrite
                    "root": model.config_name,  # fcg-rewrite
                    "parent": None,  # fcg-rewrite
                    "display_name": model.config_name  # fcg-rewrite
                }
                for model in models  # fcg-rewrite
            ]
        }
    except Exception as e:  # fcg-rewrite
        logger.error(f"List models error: {e}")  # fcg-rewrite
        return JSONResponse(  # fcg-rewrite
            status_code=500,  # fcg-rewrite
            content={"error": {"message": str(e), "type": "internal_error"}}  # fcg-rewrite
        )

@router.post("/v1/chat/completions")  # fcg-rewrite
async def create_chat_completion(  # fcg-rewrite
    request_data: ChatCompletionRequest,  # fcg-rewrite
    request: Request  # fcg-rewrite
):
    """Create chat completion with automatic model routing

    The model name in request body is matched against configured routing rules.
    Matching priority: application-specific routes > global routes > priority > exact match > prefix match
    """
    try:
        request_scope = resolve_proxy_request_context(  # fcg-rewrite
            request,  # fcg-rewrite
            extra_body=request_data.extra_body,  # fcg-rewrite
            route_label="Chat completion",  # fcg-rewrite
            default_app_log_label="Legacy proxy",  # fcg-rewrite
        )
        tenant_id = request_scope.tenant_id  # fcg-rewrite
        application_id = request_scope.application_id  # fcg-rewrite
        user_id = request_scope.user_id  # fcg-rewrite
        request_id = request_scope.request_id  # fcg-rewrite

        # Check if user is banned
        await apply_proxy_ban_check(tenant_id, user_id)  # fcg-rewrite

        image_guard_response = ensure_image_detection_subscription(tenant_id, request_data.messages)  # fcg-rewrite
        if image_guard_response is not None:  # fcg-rewrite
            return image_guard_response  # fcg-rewrite

        model_config = await resolve_chat_route_config(tenant_id, application_id, request_data.model)  # fcg-rewrite

        if not model_config:  # fcg-rewrite
            return build_missing_route_response(request_data.model)  # fcg-rewrite

        logger.info(f"Model routing: '{request_data.model}' -> upstream config '{model_config.config_name}'")  # fcg-rewrite

        input_messages, full_messages = build_chat_messages(request_data.messages)  # fcg-rewrite

        start_time = time.time()  # fcg-rewrite
        input_blocked = False  # fcg-rewrite
        output_blocked = False  # fcg-rewrite
        input_detection_id = None  # fcg-rewrite
        output_detection_id = None  # fcg-rewrite

        try:
            # Input detection - select asynchronous/synchronous mode based on configuration
            input_detection_result = await run_input_guard_checks(  # fcg-rewrite
                model_config, input_messages, tenant_id, request_id, user_id, application_id  # fcg-rewrite
            )

            input_detection_id = input_detection_result.get('detection_id')  # fcg-rewrite
            input_blocked = input_detection_result.get('blocked', False)  # fcg-rewrite
            suggest_answer = input_detection_result.get('suggest_answer')  # fcg-rewrite

            actual_messages = input_detection_result.get('modified_messages', input_messages)  # fcg-rewrite
            dispatch_plan = plan_model_dispatch(request_data.model, model_config, input_detection_result)  # fcg-rewrite
            actual_model_config = dispatch_plan.effective_config  # fcg-rewrite

            disposal_action = input_detection_result.get('disposal_action', 'pass')  # fcg-rewrite
            if disposal_action != 'pass':  # fcg-rewrite
                logger.info(f"Data leakage disposal action: {disposal_action}")  # fcg-rewrite

            # If input is blocked, record log and return
            if input_blocked:  # fcg-rewrite
                # Record log
                await proxy_service.record_proxy_request(  # fcg-rewrite
                        request_id=request_id,  # fcg-rewrite
                        tenant_id=tenant_id,  # fcg-rewrite
                        proxy_config_id=str(model_config.id),  # fcg-rewrite
                        model_requested=request_data.model,  # fcg-rewrite
                        model_used=request_data.model,  # fcg-rewrite
                        provider=model_config.provider or "unknown",  # fcg-rewrite
                        input_detection_id=input_detection_id,  # fcg-rewrite
                        input_blocked=True,  # fcg-rewrite
                        status="blocked",  # fcg-rewrite
                        response_time_ms=int((time.time() - start_time) * 1000)  # fcg-rewrite
                )

                if request_data.stream:  # fcg-rewrite
                    return build_blocked_chat_stream(  # fcg-rewrite
                        request_id=request_id,  # fcg-rewrite
                        model_name=request_data.model,  # fcg-rewrite
                        input_messages=input_messages,  # fcg-rewrite
                        detection_result=input_detection_result,  # fcg-rewrite
                    )

                return build_blocked_chat_response(request_id, request_data.model, input_detection_result)  # fcg-rewrite

            actual_model_name = dispatch_plan.effective_model_name  # fcg-rewrite

            # Use full_messages (preserving tool_calls, tool_call_id, name, etc.) for upstream
            # Apply any content modifications from detection to the full messages
            clean_messages = apply_content_overrides(full_messages, actual_messages, input_messages)  # fcg-rewrite

            tools_list = collect_request_tools(request_data)  # fcg-rewrite
            plugin_block_response = await run_plugin_input_hook(  # fcg-rewrite
                request_id=request_id,  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                application_id=application_id,  # fcg-rewrite
                request_model=request_data.model,  # fcg-rewrite
                clean_messages=clean_messages,  # fcg-rewrite
                tools_list=tools_list,  # fcg-rewrite
                extra_body=request_data.extra_body,  # fcg-rewrite
            )
            if plugin_block_response is not None:  # fcg-rewrite
                return plugin_block_response  # fcg-rewrite

            merge_passthrough_fields(  # fcg-rewrite
                request_data,  # fcg-rewrite
                {
                    "model",  # fcg-rewrite
                    "messages",  # fcg-rewrite
                    "temperature",  # fcg-rewrite
                    "top_p",  # fcg-rewrite
                    "n",
                    "stream",  # fcg-rewrite
                    "stop",
                    "max_tokens",  # fcg-rewrite
                    "presence_penalty",  # fcg-rewrite
                    "frequency_penalty",  # fcg-rewrite
                    "logit_bias",  # fcg-rewrite
                    "user",
                    "extra_body",  # fcg-rewrite
                },
            )

            _force_nonstream = should_force_nonstream(request_data.stream, application_id, request_id)  # fcg-rewrite

            # Check if it is a streaming request
            if request_data.stream and not _force_nonstream:  # fcg-rewrite
                # Streaming request handling using gateway pattern
                upstream_response = await proxy_service.dispatch_upstream_gateway(  # fcg-rewrite
                    api_config=actual_model_config,  # fcg-rewrite
                    model_name=actual_model_name,  # fcg-rewrite
                    messages=clean_messages,  # fcg-rewrite
                    stream=True,  # fcg-rewrite
                    temperature=request_data.temperature,  # fcg-rewrite
                    max_tokens=request_data.max_tokens,  # fcg-rewrite
                    top_p=request_data.top_p,  # fcg-rewrite
                    frequency_penalty=request_data.frequency_penalty,  # fcg-rewrite
                    presence_penalty=request_data.presence_penalty,  # fcg-rewrite
                    stop=request_data.stop,  # fcg-rewrite
                    extra_body=request_data.extra_body  # fcg-rewrite
                )
                return await stream_gateway_response(  # fcg-rewrite
                    upstream_response, actual_model_config, tenant_id, request_id,  # fcg-rewrite
                    input_detection_id, user_id, request_data.model, start_time,  # fcg-rewrite
                    input_messages, application_id  # fcg-rewrite
                )

            # Non-streaming request handling using gateway pattern
            model_response = await proxy_service.dispatch_upstream_gateway(  # fcg-rewrite
                api_config=actual_model_config,  # fcg-rewrite
                model_name=actual_model_name,  # fcg-rewrite
                messages=clean_messages,  # fcg-rewrite
                stream=False,  # fcg-rewrite
                temperature=request_data.temperature,  # fcg-rewrite
                max_tokens=request_data.max_tokens,  # fcg-rewrite
                top_p=request_data.top_p,  # fcg-rewrite
                frequency_penalty=request_data.frequency_penalty,  # fcg-rewrite
                presence_penalty=request_data.presence_penalty,  # fcg-rewrite
                stop=request_data.stop,  # fcg-rewrite
                extra_body=request_data.extra_body  # fcg-rewrite
            )

            # Output detection - select asynchronous/synchronous mode based on configuration
            output_detection_result = {}  # fcg-rewrite
            output_detection_id = None  # fcg-rewrite
            output_blocked = False  # fcg-rewrite
            if model_response.get('choices'):  # fcg-rewrite
                message = model_response['choices'][0]['message']  # fcg-rewrite
                output_inspection = inspect_nonstream_output(message, request_id)  # fcg-rewrite

                # Perform output detection with combined content
                output_detection_result = await run_output_guard_checks(  # fcg-rewrite
                    model_config,  # fcg-rewrite
                    input_messages,  # fcg-rewrite
                    output_inspection.combined_content,  # fcg-rewrite
                    tenant_id,  # fcg-rewrite
                    request_id,  # fcg-rewrite
                    user_id,  # fcg-rewrite
                    application_id,  # fcg-rewrite
                )

                output_detection_id = output_detection_result.get('detection_id')  # fcg-rewrite
                output_blocked = output_detection_result.get('blocked', False)  # fcg-rewrite
                final_content = output_detection_result.get('response_content', output_inspection.output_content)  # fcg-rewrite

                plugin_block_message = await run_plugin_output_hook(  # fcg-rewrite
                    request_id=request_id,  # fcg-rewrite
                    tenant_id=tenant_id,  # fcg-rewrite
                    application_id=application_id,  # fcg-rewrite
                    input_messages=input_messages,  # fcg-rewrite
                    output_content=output_inspection.output_content,  # fcg-rewrite
                    message=message,  # fcg-rewrite
                    extra_body=request_data.extra_body,  # fcg-rewrite
                    output_blocked=output_blocked,  # fcg-rewrite
                )
                if plugin_block_message:  # fcg-rewrite
                    output_blocked = True  # fcg-rewrite
                    final_content = plugin_block_message  # fcg-rewrite

                apply_output_text(message, final_content, output_blocked)  # fcg-rewrite
                if output_blocked:  # fcg-rewrite
                    model_response['choices'][0]['finish_reason'] = 'content_filter'  # fcg-rewrite

            # Record successful request log
            usage = model_response.get('usage', {})  # fcg-rewrite
            await proxy_service.record_proxy_request(  # fcg-rewrite
                request_id=request_id,  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                proxy_config_id=str(model_config.id),  # fcg-rewrite
                model_requested=request_data.model,  # fcg-rewrite
                model_used=request_data.model,  # fcg-rewrite
                provider=model_config.provider or "unknown",  # fcg-rewrite
                input_detection_id=input_detection_id,  # fcg-rewrite
                output_detection_id=output_detection_id,  # fcg-rewrite
                input_blocked=input_blocked,  # fcg-rewrite
                output_blocked=output_blocked,  # fcg-rewrite
                request_tokens=usage.get('prompt_tokens', 0),  # fcg-rewrite
                response_tokens=usage.get('completion_tokens', 0),  # fcg-rewrite
                total_tokens=usage.get('total_tokens', 0),  # fcg-rewrite
                status="success",  # fcg-rewrite
                response_time_ms=int((time.time() - start_time) * 1000)  # fcg-rewrite
            )

            # If we forced non-streaming but the client expects SSE, convert response
            if _force_nonstream and request_data.stream:  # fcg-rewrite
                logger.info(f"[{request_id}] Converting non-streaming response back to SSE for client")  # fcg-rewrite
                return wrap_nonstream_chat_response_as_sse(  # fcg-rewrite
                    model_response=model_response,  # fcg-rewrite
                    request_id=request_id,  # fcg-rewrite
                    output_detection_result=output_detection_result,  # fcg-rewrite
                )

            return model_response  # fcg-rewrite

        except Exception as e:  # fcg-rewrite
            import traceback  # fcg-rewrite
            error_traceback = traceback.format_exc()  # fcg-rewrite
            logger.error(f"Proxy request {request_id} failed: {e}")  # fcg-rewrite
            logger.error(f"Full traceback: {error_traceback}")  # fcg-rewrite

            # Record error log
            await proxy_service.record_proxy_request(  # fcg-rewrite
                request_id=request_id,  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                proxy_config_id=str(model_config.id),  # fcg-rewrite
                model_requested=request_data.model,  # fcg-rewrite
                model_used=request_data.model,  # fcg-rewrite
                provider=model_config.provider or "unknown",  # fcg-rewrite
                input_detection_id=input_detection_id,  # fcg-rewrite
                output_detection_id=output_detection_id,  # fcg-rewrite
                input_blocked=input_blocked,  # fcg-rewrite
                output_blocked=output_blocked,  # fcg-rewrite
                status="error",  # fcg-rewrite
                error_message=str(e),  # fcg-rewrite
                response_time_ms=int((time.time() - start_time) * 1000)  # fcg-rewrite
            )

            return JSONResponse(  # fcg-rewrite
                status_code=500,  # fcg-rewrite
                content={  # fcg-rewrite
                    "error": {  # fcg-rewrite
                        "message": "Failed to process request",  # fcg-rewrite
                        "type": "api_error"  # fcg-rewrite
                    }
                }
            )

    except HTTPException:  # fcg-rewrite
        # Re-raise HTTPException to preserve status codes (e.g., 403 for banned users)
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Chat completion error: {e}")  # fcg-rewrite
        return JSONResponse(  # fcg-rewrite
            status_code=500,  # fcg-rewrite
            content={"error": {"message": str(e), "type": "internal_error"}}  # fcg-rewrite
        )

def _completion_error(message: str, error_type: str, status_code: int = 500):  # fcg-rewrite
    return JSONResponse(status_code=status_code, content={"error": {"message": message, "type": error_type}})  # fcg-rewrite


def _blocked_completion(request_id: str, model: str, answer: str):  # fcg-rewrite
    return {  # fcg-rewrite
        "id": f"cmpl-{request_id}",  # fcg-rewrite
        "object": "text_completion",  # fcg-rewrite
        "created": int(time.time()),  # fcg-rewrite
        "model": model,  # fcg-rewrite
        "choices": [{"text": answer, "index": 0, "logprobs": None, "finish_reason": "content_filter"}],  # fcg-rewrite
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},  # fcg-rewrite
    }


async def _record_completion(scope, model_config, requested_model: str, started: float, status: str, **fields):  # fcg-rewrite
    usage = fields.pop("usage", {})  # fcg-rewrite
    await proxy_service.record_proxy_request(  # fcg-rewrite
        request_id=scope.request_id,  # fcg-rewrite
        tenant_id=scope.tenant_id,  # fcg-rewrite
        proxy_config_id=str(model_config.id),  # fcg-rewrite
        model_requested=requested_model,  # fcg-rewrite
        model_used=model_config.model_name,  # fcg-rewrite
        provider=get_provider_from_url(model_config.api_base_url),  # fcg-rewrite
        request_tokens=usage.get("prompt_tokens", 0),  # fcg-rewrite
        response_tokens=usage.get("completion_tokens", 0),  # fcg-rewrite
        total_tokens=usage.get("total_tokens", 0),  # fcg-rewrite
        status=status,  # fcg-rewrite
        response_time_ms=int((time.time() - started) * 1000),  # fcg-rewrite
        **fields,  # fcg-rewrite
    )


@router.post("/v1/completions")  # fcg-rewrite
async def create_completion(request_data: CompletionRequest, request: Request):  # fcg-rewrite
    """Serve the legacy text-completion wire format through the guard pipeline."""
    try:
        scope = resolve_proxy_request_context(  # fcg-rewrite
            request,  # fcg-rewrite
            extra_body=request_data.extra_body,  # fcg-rewrite
            route_label="Completion",  # fcg-rewrite
            default_app_log_label="Completion proxy",  # fcg-rewrite
        )
        await apply_proxy_ban_check(scope.tenant_id, scope.user_id)  # fcg-rewrite
        model_config = await proxy_service.load_tenant_model_config(scope.tenant_id, request_data.model)  # fcg-rewrite
        if not model_config:  # fcg-rewrite
            return _completion_error(  # fcg-rewrite
                f"Model '{request_data.model}' not found. Please configure this model first.",  # fcg-rewrite
                "model_not_found",  # fcg-rewrite
                404,
            )
        prompt = request_data.prompt if isinstance(request_data.prompt, str) else "\n".join(request_data.prompt)  # fcg-rewrite
        messages = [{"role": "user", "content": prompt}]  # fcg-rewrite
        started = time.time()  # fcg-rewrite
        state = {"input_detection_id": None, "output_detection_id": None, "input_blocked": False, "output_blocked": False}  # fcg-rewrite
        try:
            input_result = await run_input_guard_checks(  # fcg-rewrite
                model_config, messages, scope.tenant_id, scope.request_id, scope.user_id, scope.application_id  # fcg-rewrite
            )
            state["input_detection_id"] = input_result.get("detection_id")  # fcg-rewrite
            state["input_blocked"] = input_result.get("blocked", False)  # fcg-rewrite
            if state["input_blocked"]:  # fcg-rewrite
                await _record_completion(scope, model_config, request_data.model, started, "blocked", **state)  # fcg-rewrite
                return _blocked_completion(scope.request_id, request_data.model, input_result.get("suggest_answer"))  # fcg-rewrite

            response = await proxy_service.relay_completion(  # fcg-rewrite
                model_config=model_config, request_data=request_data, request_id=scope.request_id  # fcg-rewrite
            )
            if response.get("choices"):  # fcg-rewrite
                output_text = response["choices"][0]["text"]  # fcg-rewrite
                output_result = await run_output_guard_checks(  # fcg-rewrite
                    model_config, messages, output_text, scope.tenant_id, scope.request_id, scope.user_id, scope.application_id  # fcg-rewrite
                )
                state["output_detection_id"] = output_result.get("detection_id")  # fcg-rewrite
                state["output_blocked"] = output_result.get("blocked", False)  # fcg-rewrite
                response["choices"][0]["text"] = output_result.get("response_content", output_text)  # fcg-rewrite
                if state["output_blocked"]:  # fcg-rewrite
                    response["choices"][0]["finish_reason"] = "content_filter"  # fcg-rewrite
            await _record_completion(scope, model_config, request_data.model, started, "success", usage=response.get("usage", {}), **state)  # fcg-rewrite
            return response  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Proxy request %s failed: %s", scope.request_id, error, exc_info=True)  # fcg-rewrite
            await _record_completion(scope, model_config, request_data.model, started, "error", error_message=str(error), **state)  # fcg-rewrite
            return _completion_error("Failed to process request", "api_error")  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as error:  # fcg-rewrite
        logger.error("Completion error: %s", error)  # fcg-rewrite
        return _completion_error(str(error), "internal_error")  # fcg-rewrite
