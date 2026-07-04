"""Streaming helpers for the proxy gateway path."""

import asyncio  # fcg-rewrite
import json  # fcg-rewrite
import time  # fcg-rewrite
from enum import Enum  # fcg-rewrite

from fastapi.responses import JSONResponse, StreamingResponse  # fcg-rewrite

from database.connection import get_db  # fcg-rewrite
from services.data_leakage_disposal_service import LeakageMitigator  # fcg-rewrite
from services.detection_guardrail_service import detection_guardrail_service  # fcg-rewrite
from services.proxy_service import proxy_service  # fcg-rewrite
from utils.i18n_loader import get_translation  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite


logger = setup_logger()  # fcg-rewrite


class GuardExecutionMode(Enum):  # fcg-rewrite
    """Detection mode enumeration."""

    ASYNC_BYPASS = "async_bypass"  # fcg-rewrite
    SYNC_SERIAL = "sync_serial"  # fcg-rewrite


def resolve_detection_mode(model_config, detection_type: str) -> GuardExecutionMode:  # fcg-rewrite
    """Determine detection mode for proxy guard execution."""
    return GuardExecutionMode.SYNC_SERIAL  # fcg-rewrite


class StreamChunkDetector:  # fcg-rewrite
    """Stream output detector supporting asynchronous and serial modes."""

    def __init__(self, detection_mode: GuardExecutionMode = GuardExecutionMode.ASYNC_BYPASS, application_id: str = None):  # fcg-rewrite
        self.chunks_buffer = []  # fcg-rewrite
        self.chunk_count = 0  # fcg-rewrite
        self.full_content = ""  # fcg-rewrite
        self.risk_detected = False  # fcg-rewrite
        self.should_stop = False  # fcg-rewrite
        self.detection_mode = detection_mode  # fcg-rewrite
        self.application_id = application_id  # fcg-rewrite
        self.full_reasoning_content = ""  # fcg-rewrite
        self.full_tool_calls_content = ""  # fcg-rewrite
        self._in_think_tag = False  # fcg-rewrite
        self._think_buffer = ""  # fcg-rewrite
        self.last_chunk_held = None  # fcg-rewrite
        self.all_chunks_safe = False  # fcg-rewrite
        self.pending_detections = set()  # fcg-rewrite
        self.detection_result = None  # fcg-rewrite

    def _extract_think_from_content(self, content: str) -> tuple:  # fcg-rewrite
        reasoning = ""  # fcg-rewrite
        remaining = ""  # fcg-rewrite
        i = 0
        while i < len(content):  # fcg-rewrite
            if not self._in_think_tag:  # fcg-rewrite
                think_pos = content.find("<think>", i)  # fcg-rewrite
                if think_pos == -1:  # fcg-rewrite
                    remaining += content[i:]  # fcg-rewrite
                    break
                remaining += content[i:think_pos]  # fcg-rewrite
                self._in_think_tag = True  # fcg-rewrite
                i = think_pos + 7  # fcg-rewrite
            else:
                end_pos = content.find("</think>", i)  # fcg-rewrite
                if end_pos == -1:  # fcg-rewrite
                    self._think_buffer += content[i:]  # fcg-rewrite
                    break
                self._think_buffer += content[i:end_pos]  # fcg-rewrite
                reasoning += self._think_buffer  # fcg-rewrite
                self._think_buffer = ""  # fcg-rewrite
                self._in_think_tag = False  # fcg-rewrite
                i = end_pos + 8  # fcg-rewrite
        return remaining, reasoning  # fcg-rewrite

    async def add_chunk(self, chunk_content: str, reasoning_content: str, tool_calls_content: str, model_config, input_messages: list, tenant_id: str, request_id: str) -> bool:  # fcg-rewrite
        reasoning_format = getattr(model_config, "reasoning_format", "auto")  # fcg-rewrite
        if reasoning_format in ("tag", "auto") and not reasoning_content and chunk_content:  # fcg-rewrite
            chunk_content, extracted_reasoning = self._extract_think_from_content(chunk_content)  # fcg-rewrite
            if extracted_reasoning:  # fcg-rewrite
                reasoning_content = extracted_reasoning  # fcg-rewrite

        if not chunk_content.strip() and not reasoning_content.strip() and not tool_calls_content.strip():  # fcg-rewrite
            return False  # fcg-rewrite

        self.chunks_buffer.append(chunk_content)  # fcg-rewrite
        if reasoning_content.strip() and getattr(model_config, "enable_reasoning_detection", True):  # fcg-rewrite
            self.chunks_buffer.append(f"{reasoning_content}")  # fcg-rewrite
        if tool_calls_content.strip():  # fcg-rewrite
            self.chunks_buffer.append(f"{tool_calls_content}")  # fcg-rewrite

        self.chunk_count += 1  # fcg-rewrite
        self.full_content += chunk_content  # fcg-rewrite
        if reasoning_content.strip() and getattr(model_config, "enable_reasoning_detection", True):  # fcg-rewrite
            self.full_content += f"{reasoning_content}"  # fcg-rewrite
        if tool_calls_content.strip():  # fcg-rewrite
            self.full_content += f"{tool_calls_content}"  # fcg-rewrite
        if reasoning_content.strip():  # fcg-rewrite
            self.full_reasoning_content += reasoning_content  # fcg-rewrite
        if tool_calls_content.strip():  # fcg-rewrite
            self.full_tool_calls_content += tool_calls_content  # fcg-rewrite

        detection_threshold = getattr(model_config, "stream_chunk_size", 50) or 50  # fcg-rewrite
        if self.chunk_count >= detection_threshold:  # fcg-rewrite
            if self.detection_mode == GuardExecutionMode.ASYNC_BYPASS:  # fcg-rewrite
                asyncio.create_task(self._async_detection(model_config, input_messages, tenant_id, request_id))  # fcg-rewrite
                return False  # fcg-rewrite
            return await self._sync_detection(model_config, input_messages, tenant_id, request_id)  # fcg-rewrite
        return False  # fcg-rewrite

    async def final_detection(self, model_config, input_messages: list, tenant_id: str, request_id: str) -> bool:  # fcg-rewrite
        if self.chunks_buffer and not self.risk_detected:  # fcg-rewrite
            if self.detection_mode == GuardExecutionMode.ASYNC_BYPASS:  # fcg-rewrite
                asyncio.create_task(self._async_detection(model_config, input_messages, tenant_id, request_id, is_final=True))  # fcg-rewrite
                asyncio.create_task(self._plugin_stream_complete_check(input_messages, tenant_id, request_id))  # fcg-rewrite
                return False  # fcg-rewrite

            should_stop = await self._sync_final_detection(model_config, input_messages, tenant_id, request_id)  # fcg-rewrite
            if not should_stop:  # fcg-rewrite
                should_stop = await self._plugin_stream_complete_check_sync(input_messages, tenant_id, request_id)  # fcg-rewrite
            if not should_stop:  # fcg-rewrite
                self.all_chunks_safe = True  # fcg-rewrite
            return should_stop  # fcg-rewrite
        return False  # fcg-rewrite

    async def _plugin_stream_complete_check(self, input_messages: list, tenant_id: str, request_id: str):  # fcg-rewrite
        try:
            if not self.application_id:  # fcg-rewrite
                return
            if not self.full_reasoning_content and not self.full_tool_calls_content:  # fcg-rewrite
                return
            from plugins.hooks import HookContext, HookPhase  # fcg-rewrite
            from plugins.registry import plugin_registry  # fcg-rewrite

            ctx = HookContext(  # fcg-rewrite
                phase=HookPhase.STREAM_COMPLETE,  # fcg-rewrite
                request_id=request_id,  # fcg-rewrite
                tenant_id=str(tenant_id),  # fcg-rewrite
                application_id=str(self.application_id),  # fcg-rewrite
                messages=input_messages,  # fcg-rewrite
                content=self.full_content,  # fcg-rewrite
                reasoning_content=self.full_reasoning_content,  # fcg-rewrite
                tool_calls=None,  # fcg-rewrite
            )
            results = await plugin_registry.dispatch_hook(HookPhase.STREAM_COMPLETE, ctx)  # fcg-rewrite
            for pr in results:  # fcg-rewrite
                if pr.action == "block":  # fcg-rewrite
                    logger.warning("[%s] Plugin '%s' blocked stream: %s", request_id, pr.plugin_name, pr.categories)  # fcg-rewrite
                    self.risk_detected = True  # fcg-rewrite
                    self.should_stop = True  # fcg-rewrite
                    return
                if pr.action == "warn":  # fcg-rewrite
                    logger.info("[%s] Plugin '%s' flagged stream: %s", request_id, pr.plugin_name, pr.categories)  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error("[%s] Plugin stream_complete check failed: %s", request_id, exc)  # fcg-rewrite

    async def _plugin_stream_complete_check_sync(self, input_messages: list, tenant_id: str, request_id: str) -> bool:  # fcg-rewrite
        try:
            if not self.application_id:  # fcg-rewrite
                return False  # fcg-rewrite
            if not self.full_reasoning_content and not self.full_tool_calls_content:  # fcg-rewrite
                return False  # fcg-rewrite
            from plugins.hooks import HookContext, HookPhase  # fcg-rewrite
            from plugins.registry import plugin_registry  # fcg-rewrite

            ctx = HookContext(  # fcg-rewrite
                phase=HookPhase.STREAM_COMPLETE,  # fcg-rewrite
                request_id=request_id,  # fcg-rewrite
                tenant_id=str(tenant_id),  # fcg-rewrite
                application_id=str(self.application_id),  # fcg-rewrite
                messages=input_messages,  # fcg-rewrite
                content=self.full_content,  # fcg-rewrite
                reasoning_content=self.full_reasoning_content,  # fcg-rewrite
                tool_calls=None,  # fcg-rewrite
            )
            results = await plugin_registry.dispatch_hook(HookPhase.STREAM_COMPLETE, ctx)  # fcg-rewrite
            for pr in results:  # fcg-rewrite
                if pr.action == "block":  # fcg-rewrite
                    logger.warning("[%s] Plugin '%s' blocked stream: %s", request_id, pr.plugin_name, pr.categories)  # fcg-rewrite
                    self.risk_detected = True  # fcg-rewrite
                    self.should_stop = True  # fcg-rewrite
                    return True  # fcg-rewrite
                if pr.action == "warn":  # fcg-rewrite
                    logger.info("[%s] Plugin '%s' flagged stream: %s", request_id, pr.plugin_name, pr.categories)  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error("[%s] Plugin stream_complete check failed: %s", request_id, exc)  # fcg-rewrite
        return False  # fcg-rewrite

    def can_release_last_chunk(self) -> bool:  # fcg-rewrite
        if self.detection_mode == GuardExecutionMode.ASYNC_BYPASS:  # fcg-rewrite
            return True  # fcg-rewrite
        return self.all_chunks_safe and not self.risk_detected  # fcg-rewrite

    async def _async_detection(self, model_config, input_messages: list, tenant_id: str, request_id: str, is_final: bool = False):  # fcg-rewrite
        if not self.chunks_buffer:  # fcg-rewrite
            return
        try:
            accumulated_content = "".join(self.chunks_buffer)  # fcg-rewrite
            detection_messages = input_messages.copy()  # fcg-rewrite
            detection_messages.append({"role": "assistant", "content": accumulated_content})  # fcg-rewrite
            detection_result = await detection_guardrail_service.inspect_message_batch(  # fcg-rewrite
                messages=detection_messages,  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                request_id=f"{request_id}_stream_async_{self.chunk_count}",  # fcg-rewrite
                application_id=self.application_id,  # fcg-rewrite
            )
            if detection_result.get("suggest_action") in ["reject", "replace"]:  # fcg-rewrite
                logger.info("Asynchronous detection found risk but not blocked - chunk %s, request %s", self.chunk_count, request_id)  # fcg-rewrite
                logger.info("Detection result: %s", detection_result)  # fcg-rewrite
            self.chunks_buffer = []  # fcg-rewrite
            self.chunk_count = 0  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error("Asynchronous detection failed: %s", exc)  # fcg-rewrite

    async def _sync_detection(self, model_config, input_messages: list, tenant_id: str, request_id: str, is_final: bool = False) -> bool:  # fcg-rewrite
        if not self.chunks_buffer:  # fcg-rewrite
            return False  # fcg-rewrite
        try:
            accumulated_content = "".join(self.chunks_buffer)  # fcg-rewrite
            detection_messages = input_messages.copy()  # fcg-rewrite
            detection_messages.append({"role": "assistant", "content": accumulated_content})  # fcg-rewrite
            detection_result = await detection_guardrail_service.inspect_message_batch(  # fcg-rewrite
                messages=detection_messages,  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                request_id=f"{request_id}_stream_sync_{self.chunk_count}",  # fcg-rewrite
                application_id=self.application_id,  # fcg-rewrite
            )
            if detection_result.get("suggest_action") in ["reject", "replace"]:  # fcg-rewrite
                logger.warning("Synchronous detection found general risk and block - chunk %s, request %s", self.chunk_count, request_id)  # fcg-rewrite
                logger.warning("Detection result: %s", detection_result)  # fcg-rewrite
                self.risk_detected = True  # fcg-rewrite
                self.should_stop = True  # fcg-rewrite
                self.detection_result = detection_result  # fcg-rewrite
                return True  # fcg-rewrite

            data_risk_level = detection_result.get("data_result", {}).get("risk_level", "no_risk")  # fcg-rewrite
            if data_risk_level != "no_risk" and self.application_id:  # fcg-rewrite
                try:
                    db = next(get_db())  # fcg-rewrite
                    disposal_service = LeakageMitigator(db)  # fcg-rewrite
                    disposal_action = disposal_service.get_disposal_action(self.application_id, data_risk_level, direction="output")  # fcg-rewrite
                    if disposal_action == "block":  # fcg-rewrite
                        logger.warning("Synchronous detection found DLP risk (%s) and block - chunk %s, request %s", data_risk_level, self.chunk_count, request_id)  # fcg-rewrite
                        self.risk_detected = True  # fcg-rewrite
                        self.should_stop = True  # fcg-rewrite
                        self.detection_result = detection_result.copy() if detection_result else {}  # fcg-rewrite
                        try:
                            dlp_block_message = get_translation("en", "guardrail", "sensitiveDataPolicyViolation")  # fcg-rewrite
                        except Exception:  # fcg-rewrite
                            dlp_block_message = "Request blocked by FangcunGuard due to sensitive data policy violation."  # fcg-rewrite
                        self.detection_result["suggest_answer"] = dlp_block_message  # fcg-rewrite
                        return True  # fcg-rewrite
                except Exception as exc:  # fcg-rewrite
                    logger.error("DLP disposal check failed in stream detection: %s", exc)  # fcg-rewrite

            self.chunks_buffer = []  # fcg-rewrite
            self.chunk_count = 0  # fcg-rewrite
            return False  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error("Synchronous detection failed: %s", exc)  # fcg-rewrite
            return False  # fcg-rewrite

    async def _sync_final_detection(self, model_config, input_messages: list, tenant_id: str, request_id: str) -> bool:  # fcg-rewrite
        if not self.chunks_buffer:  # fcg-rewrite
            return False  # fcg-rewrite
        try:
            accumulated_content = "".join(self.chunks_buffer)  # fcg-rewrite
            detection_messages = input_messages.copy()  # fcg-rewrite
            detection_messages.append({"role": "assistant", "content": accumulated_content})  # fcg-rewrite
            detection_result = await detection_guardrail_service.inspect_message_batch(  # fcg-rewrite
                messages=detection_messages,  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                request_id=f"{request_id}_stream_final_{self.chunk_count}",  # fcg-rewrite
                application_id=self.application_id,  # fcg-rewrite
            )

            general_risk_level = detection_result.get("overall_risk_level", "no_risk")  # fcg-rewrite
            if detection_result.get("suggest_action") in ["reject", "replace"] and general_risk_level != "no_risk":  # fcg-rewrite
                general_should_block = False  # fcg-rewrite
                if self.application_id:  # fcg-rewrite
                    try:
                        db = next(get_db())  # fcg-rewrite
                        disposal_service_gen = LeakageMitigator(db)  # fcg-rewrite
                        general_action = disposal_service_gen.get_general_risk_action(self.application_id, general_risk_level, direction="output")  # fcg-rewrite
                        logger.info("Stream final detection: general_risk=%s, policy_action=%s", general_risk_level, general_action)  # fcg-rewrite
                        if general_action in ["block", "replace"]:  # fcg-rewrite
                            general_should_block = True  # fcg-rewrite
                    except Exception as exc:  # fcg-rewrite
                        logger.error("Error checking general risk policy in stream: %s", exc)  # fcg-rewrite
                        general_should_block = True  # fcg-rewrite
                else:
                    general_should_block = True  # fcg-rewrite

                if general_should_block:  # fcg-rewrite
                    logger.warning("Synchronous final detection found general risk and block - chunk %s, request %s", self.chunk_count, request_id)  # fcg-rewrite
                    logger.warning("Detection result: %s", detection_result)  # fcg-rewrite
                    self.risk_detected = True  # fcg-rewrite
                    self.should_stop = True  # fcg-rewrite
                    self.detection_result = detection_result  # fcg-rewrite
                    return True  # fcg-rewrite

            data_risk_level = detection_result.get("data_result", {}).get("risk_level", "no_risk")  # fcg-rewrite
            if data_risk_level != "no_risk" and self.application_id:  # fcg-rewrite
                try:
                    db = next(get_db())  # fcg-rewrite
                    disposal_service = LeakageMitigator(db)  # fcg-rewrite
                    disposal_action = disposal_service.get_disposal_action(self.application_id, data_risk_level, direction="output")  # fcg-rewrite
                    if disposal_action == "block":  # fcg-rewrite
                        logger.warning("Synchronous final detection found DLP risk (%s) and block - chunk %s, request %s", data_risk_level, self.chunk_count, request_id)  # fcg-rewrite
                        self.risk_detected = True  # fcg-rewrite
                        self.should_stop = True  # fcg-rewrite
                        self.detection_result = detection_result.copy() if detection_result else {}  # fcg-rewrite
                        try:
                            dlp_block_message = get_translation("en", "guardrail", "sensitiveDataPolicyViolation")  # fcg-rewrite
                        except Exception:  # fcg-rewrite
                            dlp_block_message = "Request blocked by FangcunGuard due to sensitive data policy violation."  # fcg-rewrite
                        self.detection_result["suggest_answer"] = dlp_block_message  # fcg-rewrite
                        return True  # fcg-rewrite
                    if disposal_action == "anonymize":  # fcg-rewrite
                        anonymized_text = detection_result.get("data_result", {}).get("anonymized_text")  # fcg-rewrite
                        if anonymized_text:  # fcg-rewrite
                            logger.info("Stream final detection: anonymizing DLP content")  # fcg-rewrite
                            self.risk_detected = True  # fcg-rewrite
                            self.should_stop = True  # fcg-rewrite
                            self.detection_result = detection_result.copy() if detection_result else {}  # fcg-rewrite
                            self.detection_result["suggest_answer"] = anonymized_text  # fcg-rewrite
                            return True  # fcg-rewrite
                except Exception as exc:  # fcg-rewrite
                    logger.error("DLP disposal check failed in stream final detection: %s", exc)  # fcg-rewrite

            self.chunks_buffer = []  # fcg-rewrite
            self.chunk_count = 0  # fcg-rewrite
            return False  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error("Synchronous final detection failed: %s", exc)  # fcg-rewrite
            return False  # fcg-rewrite


async def stream_gateway_response(  # fcg-rewrite
    upstream_response,  # fcg-rewrite
    api_config,  # fcg-rewrite
    tenant_id: str,  # fcg-rewrite
    request_id: str,  # fcg-rewrite
    input_detection_id: str,  # fcg-rewrite
    user_id: str,  # fcg-rewrite
    model_name: str,  # fcg-rewrite
    start_time: float,  # fcg-rewrite
    input_messages: list,  # fcg-rewrite
    application_id: str = None,  # fcg-rewrite
):
    """Handle gateway streaming response with output detection."""
    try:
        from services.request_context import AnonymizationContext  # fcg-rewrite
        from services.restore_anonymization_service import StreamingRestoreBuffer  # fcg-rewrite

        restore_mapping = AnonymizationContext.get_mapping()  # fcg-rewrite
        has_restore_mapping = bool(restore_mapping)  # fcg-rewrite
        restore_buffer = StreamingRestoreBuffer(restore_mapping) if has_restore_mapping else None  # fcg-rewrite

        if has_restore_mapping:  # fcg-rewrite
            logger.info("Gateway streaming: Using restore buffer with %s mappings", len(restore_mapping))  # fcg-rewrite

        output_detection_mode = resolve_detection_mode(api_config, "output")  # fcg-rewrite
        detector = StreamChunkDetector(output_detection_mode, application_id=application_id)  # fcg-rewrite

        async def stream_generator():  # fcg-rewrite
            nonlocal restore_buffer, has_restore_mapping  # fcg-rewrite
            output_detection_id = None  # fcg-rewrite
            output_blocked = False  # fcg-rewrite
            chunks_queue = []  # fcg-rewrite
            tc_buffer = {}  # fcg-rewrite
            tc_seen = False  # fcg-rewrite
            tc_finish_reason = None  # fcg-rewrite

            try:
                async with upstream_response as response:  # fcg-rewrite
                    response.raise_for_status()  # fcg-rewrite
                    async for line in response.aiter_lines():  # fcg-rewrite
                        if not line.strip():  # fcg-rewrite
                            continue  # fcg-rewrite
                        if line.startswith("data: "):  # fcg-rewrite
                            line = line[6:]  # fcg-rewrite

                        if line.strip() == "[DONE]":  # fcg-rewrite
                            if not detector.should_stop:  # fcg-rewrite
                                should_stop = await detector.final_detection(api_config, input_messages, tenant_id, request_id)  # fcg-rewrite
                                if should_stop:  # fcg-rewrite
                                    output_blocked = True  # fcg-rewrite
                                    if detector.detection_mode == GuardExecutionMode.SYNC_SERIAL:  # fcg-rewrite
                                        chunks_queue = []  # fcg-rewrite
                                    suggest_answer = detector.detection_result.get("suggest_answer") if detector.detection_result else None  # fcg-rewrite
                                    if suggest_answer:  # fcg-rewrite
                                        logger.info("Gateway final detection - Sending suggest_answer as content chunks: %s...", suggest_answer[:50])  # fcg-rewrite
                                        for chunk_str in emit_suggested_answer_chunks(request_id, suggest_answer, model_name):  # fcg-rewrite
                                            yield chunk_str  # fcg-rewrite
                                    else:
                                        logger.warning("Gateway final detection - No suggest_answer found in detection_result: %s", detector.detection_result)  # fcg-rewrite
                                    stop_chunk = emit_stop_chunk(request_id, detector.detection_result, model_name)  # fcg-rewrite
                                    yield f"data: {json.dumps(stop_chunk)}\n\n"  # fcg-rewrite
                                    yield "data: [DONE]\n\n"  # fcg-rewrite
                                    break
                                if tc_buffer:  # fcg-rewrite
                                    for sse in reshape_tool_call_sse(tc_buffer, tc_finish_reason, f"chatcmpl-{request_id}", model_name):  # fcg-rewrite
                                        yield sse  # fcg-rewrite
                                    break
                                if detector.detection_mode == GuardExecutionMode.SYNC_SERIAL:  # fcg-rewrite
                                    for queued_chunk in chunks_queue:  # fcg-rewrite
                                        if has_restore_mapping and restore_buffer:  # fcg-rewrite
                                            if "choices" in queued_chunk and queued_chunk["choices"]:  # fcg-rewrite
                                                delta = queued_chunk["choices"][0].get("delta", {})  # fcg-rewrite
                                                chunk_content = delta.get("content", "")  # fcg-rewrite
                                                if chunk_content:  # fcg-rewrite
                                                    restored_content = restore_buffer.process_chunk(chunk_content)  # fcg-rewrite
                                                    if restored_content:  # fcg-rewrite
                                                        modified_chunk = json.loads(json.dumps(queued_chunk))  # fcg-rewrite
                                                        modified_chunk["choices"][0]["delta"]["content"] = restored_content  # fcg-rewrite
                                                        yield f"data: {json.dumps(modified_chunk)}\n\n"  # fcg-rewrite
                                                else:
                                                    yield f"data: {json.dumps(queued_chunk)}\n\n"  # fcg-rewrite
                                            else:
                                                yield f"data: {json.dumps(queued_chunk)}\n\n"  # fcg-rewrite
                                        else:
                                            yield f"data: {json.dumps(queued_chunk)}\n\n"  # fcg-rewrite

                            if has_restore_mapping and restore_buffer and restore_buffer.has_pending_content():  # fcg-rewrite
                                remaining = restore_buffer.flush()  # fcg-rewrite
                                if remaining:  # fcg-rewrite
                                    flush_chunk = emit_content_chunk(request_id, remaining, model_name)  # fcg-rewrite
                                    yield f"data: {json.dumps(flush_chunk)}\n\n"  # fcg-rewrite
                            if tc_buffer:  # fcg-rewrite
                                for sse in reshape_tool_call_sse(tc_buffer, tc_finish_reason, f"chatcmpl-{request_id}", model_name):  # fcg-rewrite
                                    yield sse  # fcg-rewrite
                                break
                            yield "data: [DONE]\n\n"  # fcg-rewrite
                            break

                        try:
                            chunk_data = json.loads(line)  # fcg-rewrite
                            if chunk_carries_tool_calls(chunk_data):  # fcg-rewrite
                                tc_seen = True  # fcg-rewrite
                                for tc in chunk_data["choices"][0].get("delta", {}).get("tool_calls", []):  # fcg-rewrite
                                    tc_idx = tc.get("index", 0)  # fcg-rewrite
                                    if tc_idx not in tc_buffer:  # fcg-rewrite
                                        tc_buffer[tc_idx] = {"id": "", "name": "", "type": "function", "arguments": ""}  # fcg-rewrite
                                    if tc.get("id"):  # fcg-rewrite
                                        tc_buffer[tc_idx]["id"] = tc["id"]  # fcg-rewrite
                                    if tc.get("function", {}).get("name"):  # fcg-rewrite
                                        tc_buffer[tc_idx]["name"] = tc["function"]["name"]  # fcg-rewrite
                                    if tc.get("function", {}).get("arguments"):  # fcg-rewrite
                                        tc_buffer[tc_idx]["arguments"] += tc["function"]["arguments"]  # fcg-rewrite
                            if tc_seen and chunk_data.get("choices"):  # fcg-rewrite
                                finish_reason = chunk_data["choices"][0].get("finish_reason")  # fcg-rewrite
                                if finish_reason:  # fcg-rewrite
                                    tc_finish_reason = finish_reason  # fcg-rewrite

                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:  # fcg-rewrite
                                delta = chunk_data["choices"][0].get("delta", {})  # fcg-rewrite
                                content = delta.get("content") or ""  # fcg-rewrite
                                reasoning_content = ""  # fcg-rewrite
                                if getattr(api_config, "enable_reasoning_detection", True):  # fcg-rewrite
                                    reasoning_format = getattr(api_config, "reasoning_format", "auto")  # fcg-rewrite
                                    if reasoning_format in ("field", "auto"):  # fcg-rewrite
                                        reasoning_content = delta.get("reasoning_content") or ""  # fcg-rewrite

                                if content or reasoning_content:  # fcg-rewrite
                                    tool_calls_content = ""  # fcg-rewrite
                                    if chunk_carries_tool_calls(chunk_data):  # fcg-rewrite
                                        tool_calls_content = pull_tool_calls_content(chunk_data)  # fcg-rewrite
                                        logger.debug("Extracted tool_calls content for detection: %s...", tool_calls_content[:100])  # fcg-rewrite
                                    should_stop = await detector.add_chunk(content, reasoning_content, tool_calls_content, api_config, input_messages, tenant_id, request_id)  # fcg-rewrite
                                    if should_stop:  # fcg-rewrite
                                        output_blocked = True  # fcg-rewrite
                                        if detector.detection_mode == GuardExecutionMode.SYNC_SERIAL:  # fcg-rewrite
                                            chunks_queue = []  # fcg-rewrite
                                        suggest_answer = detector.detection_result.get("suggest_answer") if detector.detection_result else None  # fcg-rewrite
                                        if suggest_answer:  # fcg-rewrite
                                            logger.info("Gateway streaming - Sending suggest_answer as content chunks: %s...", suggest_answer[:50])  # fcg-rewrite
                                            for chunk_str in emit_suggested_answer_chunks(request_id, suggest_answer, model_name):  # fcg-rewrite
                                                yield chunk_str  # fcg-rewrite
                                        else:
                                            logger.warning("Gateway streaming - No suggest_answer found in detection_result: %s", detector.detection_result)  # fcg-rewrite
                                        stop_chunk = emit_stop_chunk(request_id, detector.detection_result, model_name)  # fcg-rewrite
                                        yield f"data: {json.dumps(stop_chunk)}\n\n"  # fcg-rewrite
                                        yield "data: [DONE]\n\n"  # fcg-rewrite
                                        break

                            if tc_seen:  # fcg-rewrite
                                continue  # fcg-rewrite

                            if detector.detection_mode == GuardExecutionMode.ASYNC_BYPASS:  # fcg-rewrite
                                if has_restore_mapping and restore_buffer:  # fcg-rewrite
                                    if "choices" in chunk_data and chunk_data["choices"]:  # fcg-rewrite
                                        delta = chunk_data["choices"][0].get("delta", {})  # fcg-rewrite
                                        chunk_content = delta.get("content", "")  # fcg-rewrite
                                        if chunk_content:  # fcg-rewrite
                                            restored_content = restore_buffer.process_chunk(chunk_content)  # fcg-rewrite
                                            if restored_content:  # fcg-rewrite
                                                modified_chunk = json.loads(json.dumps(chunk_data))  # fcg-rewrite
                                                modified_chunk["choices"][0]["delta"]["content"] = restored_content  # fcg-rewrite
                                                yield f"data: {json.dumps(modified_chunk)}\n\n"  # fcg-rewrite
                                        else:
                                            yield f"data: {json.dumps(chunk_data)}\n\n"  # fcg-rewrite
                                    else:
                                        yield f"data: {json.dumps(chunk_data)}\n\n"  # fcg-rewrite
                                else:
                                    yield f"data: {json.dumps(chunk_data)}\n\n"  # fcg-rewrite
                            else:
                                chunks_queue.append(chunk_data)  # fcg-rewrite
                        except json.JSONDecodeError:  # fcg-rewrite
                            continue  # fcg-rewrite

                await proxy_service.record_gateway_proxy_request(  # fcg-rewrite
                    request_id=request_id,  # fcg-rewrite
                    tenant_id=tenant_id,  # fcg-rewrite
                    upstream_api_config_id=str(api_config.id),  # fcg-rewrite
                    model_requested=model_name,  # fcg-rewrite
                    model_used=model_name,  # fcg-rewrite
                    provider=api_config.provider or "unknown",  # fcg-rewrite
                    input_detection_id=input_detection_id,  # fcg-rewrite
                    output_detection_id=output_detection_id,  # fcg-rewrite
                    input_blocked=False,  # fcg-rewrite
                    output_blocked=output_blocked,  # fcg-rewrite
                    status="stream_blocked" if output_blocked else "stream_success",  # fcg-rewrite
                    response_time_ms=int((time.time() - start_time) * 1000),  # fcg-rewrite
                )

                if has_restore_mapping:  # fcg-rewrite
                    AnonymizationContext.clear()  # fcg-rewrite
                    logger.debug("Cleared AnonymizationContext at end of stream")  # fcg-rewrite

            except Exception as exc:  # fcg-rewrite
                logger.error("Gateway streaming error: %s", exc)  # fcg-rewrite
                if has_restore_mapping:  # fcg-rewrite
                    try:
                        AnonymizationContext.clear()  # fcg-rewrite
                    except Exception:  # fcg-rewrite
                        pass
                error_chunk = {  # fcg-rewrite
                    "id": f"chatcmpl-{request_id}",  # fcg-rewrite
                    "object": "chat.completion.chunk",  # fcg-rewrite
                    "created": int(time.time()),  # fcg-rewrite
                    "model": model_name,  # fcg-rewrite
                    "choices": [{  # fcg-rewrite
                        "index": 0,  # fcg-rewrite
                        "delta": {"role": "assistant", "content": f"Error: {str(exc)}"},  # fcg-rewrite
                        "finish_reason": "error",  # fcg-rewrite
                    }],
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"  # fcg-rewrite
                yield "data: [DONE]\n\n"  # fcg-rewrite

        return StreamingResponse(  # fcg-rewrite
            stream_generator(),  # fcg-rewrite
            media_type="text/event-stream",  # fcg-rewrite
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},  # fcg-rewrite
        )
    except Exception as exc:  # fcg-rewrite
        logger.error("Gateway streaming handler error: %s", exc)  # fcg-rewrite
        return JSONResponse(status_code=500, content={"error": {"message": str(exc), "type": "internal_error"}})  # fcg-rewrite


def pull_tool_calls_content(chunk: dict) -> str:  # fcg-rewrite
    try:
        if "choices" in chunk and chunk["choices"]:  # fcg-rewrite
            choice = chunk["choices"][0]  # fcg-rewrite
            if "delta" in choice and "tool_calls" in choice["delta"]:  # fcg-rewrite
                tool_calls = choice["delta"]["tool_calls"]  # fcg-rewrite
                if not tool_calls:  # fcg-rewrite
                    return ""  # fcg-rewrite
                tool_calls_text = ""  # fcg-rewrite
                for tool_call in tool_calls:  # fcg-rewrite
                    if "function" in tool_call:  # fcg-rewrite
                        func = tool_call["function"]  # fcg-rewrite
                        tool_calls_text += f"[工具调用] {func.get('name', '')}({func.get('arguments', '')}) "  # fcg-rewrite
                return tool_calls_text.strip()  # fcg-rewrite
    except Exception:  # fcg-rewrite
        pass
    return ""  # fcg-rewrite


def chunk_carries_tool_calls(chunk: dict) -> bool:  # fcg-rewrite
    try:
        if "choices" in chunk and chunk["choices"]:  # fcg-rewrite
            choice = chunk["choices"][0]  # fcg-rewrite
            if "delta" in choice and "tool_calls" in choice["delta"]:  # fcg-rewrite
                return bool(choice["delta"]["tool_calls"])  # fcg-rewrite
    except Exception:  # fcg-rewrite
        pass
    return False  # fcg-rewrite


def reshape_tool_call_sse(tc_buf: dict, finish_reason: str, resp_id: str, model_name: str) -> list:  # fcg-rewrite
    created = int(time.time())  # fcg-rewrite
    result = []  # fcg-rewrite

    def mk(delta, fr=None):  # fcg-rewrite
        chunk = {  # fcg-rewrite
            "id": resp_id,  # fcg-rewrite
            "object": "chat.completion.chunk",  # fcg-rewrite
            "created": created,  # fcg-rewrite
            "model": model_name,  # fcg-rewrite
            "choices": [{"index": 0, "delta": delta}],  # fcg-rewrite
        }
        if fr:
            chunk["choices"][0]["finish_reason"] = fr  # fcg-rewrite
        return f"data: {json.dumps(chunk)}\n\n"  # fcg-rewrite

    result.append(mk({"role": "assistant", "content": ""}))  # fcg-rewrite
    for idx in sorted(tc_buf.keys()):  # fcg-rewrite
        tc = tc_buf[idx]  # fcg-rewrite
        result.append(mk({"tool_calls": [{  # fcg-rewrite
            "index": idx,  # fcg-rewrite
            "id": tc["id"],  # fcg-rewrite
            "type": tc["type"],  # fcg-rewrite
            "function": {"name": tc["name"], "arguments": ""},  # fcg-rewrite
        }]}))
        args = tc["arguments"]  # fcg-rewrite
        for i in range(0, max(len(args), 1), 200):  # fcg-rewrite
            result.append(mk({"tool_calls": [{"index": idx, "function": {"arguments": args[i:i+200]}}]}))  # fcg-rewrite
    result.append(mk({}, fr=finish_reason or "tool_calls"))  # fcg-rewrite
    result.append("data: [DONE]\n\n")  # fcg-rewrite
    return result  # fcg-rewrite


def emit_content_chunk(request_id: str, content: str, model: str = "fangcunguard-security") -> dict:  # fcg-rewrite
    return {  # fcg-rewrite
        "id": f"chatcmpl-{request_id}",  # fcg-rewrite
        "object": "chat.completion.chunk",  # fcg-rewrite
        "created": int(time.time()),  # fcg-rewrite
        "model": model,  # fcg-rewrite
        "choices": [{"index": 0, "delta": {"content": content}}],  # fcg-rewrite
    }


def emit_stop_chunk(request_id: str, detection_result: dict = None, model: str = "fangcunguard-security") -> dict:  # fcg-rewrite
    chunk = {  # fcg-rewrite
        "id": f"chatcmpl-{request_id}",  # fcg-rewrite
        "object": "chat.completion.chunk",  # fcg-rewrite
        "created": int(time.time()),  # fcg-rewrite
        "model": model,  # fcg-rewrite
        "choices": [{"index": 0, "delta": {}, "finish_reason": "content_filter"}],  # fcg-rewrite
    }
    if detection_result:  # fcg-rewrite
        chunk["detection_info"] = {  # fcg-rewrite
            "suggest_action": detection_result.get("suggest_action"),  # fcg-rewrite
            "suggest_answer": detection_result.get("suggest_answer"),  # fcg-rewrite
            "overall_risk_level": detection_result.get("overall_risk_level"),  # fcg-rewrite
            "compliance_result": detection_result.get("compliance_result"),  # fcg-rewrite
            "security_result": detection_result.get("security_result"),  # fcg-rewrite
            "data_result": detection_result.get("data_result"),  # fcg-rewrite
            "request_id": detection_result.get("request_id"),  # fcg-rewrite
        }
    else:
        chunk["detection_info"] = {  # fcg-rewrite
            "suggest_action": "Reject",  # fcg-rewrite
            "suggest_answer": "Sorry, I cannot answer your question.",  # fcg-rewrite
            "overall_risk_level": "high_risk",  # fcg-rewrite
            "compliance_result": None,  # fcg-rewrite
            "security_result": None,  # fcg-rewrite
            "request_id": "unknown",  # fcg-rewrite
        }
    return chunk  # fcg-rewrite


def emit_suggested_answer_chunks(request_id: str, suggest_answer: str, model: str = "fangcunguard-security", chunk_size: int = 50):  # fcg-rewrite
    if not suggest_answer:  # fcg-rewrite
        logger.warning("emit_suggested_answer_chunks called with empty suggest_answer")  # fcg-rewrite
        return
    logger.info("emit_suggested_answer_chunks: suggest_answer length=%s, content=%s", len(suggest_answer), suggest_answer[:100])  # fcg-rewrite
    for i in range(0, len(suggest_answer), chunk_size):  # fcg-rewrite
        chunk_content = suggest_answer[i:i + chunk_size]  # fcg-rewrite
        yield f"data: {json.dumps(emit_content_chunk(request_id, chunk_content, model))}\n\n"  # fcg-rewrite


def get_provider_from_url(api_base_url: str) -> str:  # fcg-rewrite
    try:
        if "//" in api_base_url:  # fcg-rewrite
            return api_base_url.split("//")[1].split("/")[0].split(".")[0]  # fcg-rewrite
        return "unknown"  # fcg-rewrite
    except Exception:  # fcg-rewrite
        return "unknown"  # fcg-rewrite
