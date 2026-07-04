"""Guard pipeline helpers for the OpenAI-compatible proxy router."""

import asyncio  # fcg-rewrite

from database.connection import get_db  # fcg-rewrite
from services.ban_policy_service import BanPolicyManager  # fcg-rewrite
from services.data_leakage_disposal_service import LeakageMitigator  # fcg-rewrite
from services.detection_guardrail_service import detection_guardrail_service  # fcg-rewrite
from services.proxy_streaming import GuardExecutionMode, resolve_detection_mode  # fcg-rewrite
from services.unified_anonymization_service import get_unified_anonymization_service  # fcg-rewrite
from utils.i18n_loader import get_translation  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite


logger = setup_logger()  # fcg-rewrite


def redact_user_messages(messages: list, detected_entities: list) -> list:  # fcg-rewrite
    """Anonymize sensitive data in user messages using configured methods."""
    if not detected_entities:  # fcg-rewrite
        return messages  # fcg-rewrite
    anonymization_service = get_unified_anonymization_service()  # fcg-rewrite
    anonymized_messages, _ = anonymization_service.anonymize_messages(  # fcg-rewrite
        messages=messages,  # fcg-rewrite
        detected_entities=detected_entities,  # fcg-rewrite
        action="anonymize",  # fcg-rewrite
    )
    logger.debug("Anonymized user messages: %s entities using configured methods", len(detected_entities))  # fcg-rewrite
    return anonymized_messages  # fcg-rewrite


def redact_user_messages_restorable(messages: list, detected_entities: list, application_id: str, db) -> tuple:  # fcg-rewrite
    """Anonymize sensitive data with placeholders that can be restored later."""
    if not detected_entities:  # fcg-rewrite
        return messages, {}  # fcg-rewrite
    anonymization_service = get_unified_anonymization_service()  # fcg-rewrite
    anonymized_messages, restore_mapping = anonymization_service.anonymize_messages(  # fcg-rewrite
        messages=messages,  # fcg-rewrite
        detected_entities=detected_entities,  # fcg-rewrite
        action="anonymize_restore",  # fcg-rewrite
        application_id=application_id,  # fcg-rewrite
    )
    if restore_mapping:  # fcg-rewrite
        logger.debug("Anonymized with restore: %s placeholders created", len(restore_mapping))  # fcg-rewrite
    return anonymized_messages, restore_mapping or {}  # fcg-rewrite


async def run_input_guard_checks(model_config, input_messages: list, tenant_id: str, request_id: str, user_id: str = None, application_id: str = None):  # fcg-rewrite
    guard_mode = resolve_detection_mode(model_config, "input")  # fcg-rewrite
    if guard_mode == GuardExecutionMode.ASYNC_BYPASS:  # fcg-rewrite
        return await _execute_async_input_guard(input_messages, tenant_id, request_id, model_config, user_id, application_id)  # fcg-rewrite
    return await _execute_sync_input_guard(model_config, input_messages, tenant_id, request_id, user_id, application_id)  # fcg-rewrite


async def run_output_guard_checks(model_config, input_messages: list, response_content: str, tenant_id: str, request_id: str, user_id: str = None, application_id: str = None):  # fcg-rewrite
    guard_mode = resolve_detection_mode(model_config, "output")  # fcg-rewrite
    if guard_mode == GuardExecutionMode.ASYNC_BYPASS:  # fcg-rewrite
        return await _execute_async_output_guard(input_messages, response_content, tenant_id, request_id, model_config, user_id, application_id)  # fcg-rewrite
    return await _execute_sync_output_guard(model_config, input_messages, response_content, tenant_id, request_id, user_id, application_id)  # fcg-rewrite


async def _execute_async_input_guard(input_messages: list, tenant_id: str, request_id: str, model_config=None, user_id: str = None, application_id: str = None):  # fcg-rewrite
    asyncio.create_task(_async_record_input_guard(input_messages, tenant_id, request_id, model_config, user_id, application_id))  # fcg-rewrite
    return {"blocked": False, "detection_id": f"{request_id}_input_async", "suggest_answer": None}  # fcg-rewrite


async def _async_record_input_guard(input_messages: list, tenant_id: str, request_id: str, model_config=None, user_id: str = None, application_id: str = None):  # fcg-rewrite
    try:
        detection_result = await detection_guardrail_service.inspect_message_batch(  # fcg-rewrite
            messages=input_messages,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            request_id=f"{request_id}_input_async",  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
        )
        if detection_result.get("suggest_action") in ["reject", "replace"]:  # fcg-rewrite
            logger.info("Asynchronous input detection found risk but not blocked - request %s", request_id)  # fcg-rewrite
            logger.info("Detection result: %s", detection_result)  # fcg-rewrite
        if user_id and detection_result.get("overall_risk_level") in ["medium_risk", "high_risk"]:  # fcg-rewrite
            asyncio.create_task(  # fcg-rewrite
                BanPolicyManager.check_and_apply_ban_policy(  # fcg-rewrite
                    tenant_id=tenant_id,  # fcg-rewrite
                    user_id=user_id,  # fcg-rewrite
                    risk_level=detection_result.get("overall_risk_level"),  # fcg-rewrite
                    detection_result_id=detection_result.get("request_id"),  # fcg-rewrite
                    language="zh",  # fcg-rewrite
                )
            )
    except Exception as exc:  # fcg-rewrite
        logger.error("Background input detection failed: %s", exc)  # fcg-rewrite


async def _execute_sync_input_guard(model_config, input_messages: list, tenant_id: str, request_id: str, user_id: str = None, application_id: str = None):  # fcg-rewrite
    try:
        detection_result = await detection_guardrail_service.inspect_message_batch(  # fcg-rewrite
            messages=input_messages,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            request_id=f"{request_id}_input_sync",  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
        )
        detection_id = detection_result.get("request_id")  # fcg-rewrite

        if user_id and detection_result.get("overall_risk_level") in ["medium_risk", "high_risk"]:  # fcg-rewrite
            await BanPolicyManager.check_and_apply_ban_policy(  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                user_id=user_id,  # fcg-rewrite
                risk_level=detection_result.get("overall_risk_level"),  # fcg-rewrite
                detection_result_id=detection_id,  # fcg-rewrite
                language="zh",  # fcg-rewrite
                application_id=application_id,  # fcg-rewrite
            )

        data_risk_level = detection_result.get("data_result", {}).get("risk_level", "no_risk")  # fcg-rewrite
        compliance_risk = detection_result.get("compliance_result", {}).get("risk_level", "no_risk") if detection_result.get("compliance_result") else "no_risk"  # fcg-rewrite
        security_risk = detection_result.get("security_result", {}).get("risk_level", "no_risk") if detection_result.get("security_result") else "no_risk"  # fcg-rewrite

        risk_priority = {"no_risk": 0, "low_risk": 1, "medium_risk": 2, "high_risk": 3}  # fcg-rewrite
        general_risk_level = "no_risk"  # fcg-rewrite
        for level in [compliance_risk, security_risk]:  # fcg-rewrite
            if risk_priority.get(level, 0) > risk_priority.get(general_risk_level, 0):  # fcg-rewrite
                general_risk_level = level  # fcg-rewrite

        disposal_action = "pass"  # fcg-rewrite
        modified_messages = input_messages  # fcg-rewrite
        modified_model_config = model_config  # fcg-rewrite
        restore_mapping = {}  # fcg-rewrite
        disposal_service = None  # fcg-rewrite
        dlp_blocked = False  # fcg-rewrite
        general_blocked = False  # fcg-rewrite

        if data_risk_level != "no_risk" and application_id:  # fcg-rewrite
            try:
                db = next(get_db())  # fcg-rewrite
                disposal_service = LeakageMitigator(db)  # fcg-rewrite
                disposal_action = disposal_service.get_disposal_action(application_id, data_risk_level)  # fcg-rewrite
                logger.info("Data leakage detected (risk=%s), disposal_action=%s", data_risk_level, disposal_action)  # fcg-rewrite

                if disposal_action == "block":  # fcg-rewrite
                    dlp_blocked = True  # fcg-rewrite
                    try:
                        dlp_block_message = get_translation("en", "guardrail", "sensitiveDataPolicyViolation")  # fcg-rewrite
                    except Exception:  # fcg-rewrite
                        dlp_block_message = "Request blocked by FangcunGuard due to sensitive data policy violation."  # fcg-rewrite
                elif disposal_action == "switch_private_model":  # fcg-rewrite
                    private_model = disposal_service.get_private_model(application_id, tenant_id)  # fcg-rewrite
                    if private_model:  # fcg-rewrite
                        modified_model_config = private_model  # fcg-rewrite
                        logger.info("Switched to private model: %s (using original text)", private_model.config_name)  # fcg-rewrite
                    else:
                        logger.warning("No private model available, blocking request instead")  # fcg-rewrite
                        dlp_blocked = True  # fcg-rewrite
                        try:
                            dlp_block_message = get_translation("en", "guardrail", "sensitiveDataPolicyViolation")  # fcg-rewrite
                        except Exception:  # fcg-rewrite
                            dlp_block_message = "Request blocked by FangcunGuard due to sensitive data policy violation."  # fcg-rewrite
                elif disposal_action == "anonymize":  # fcg-rewrite
                    detected_entities = detection_result.get("data_result", {}).get("detected_entities", [])  # fcg-rewrite
                    if detected_entities:  # fcg-rewrite
                        modified_messages = redact_user_messages(input_messages, detected_entities)  # fcg-rewrite
                        logger.info("Anonymized %s user messages for data safety", len([m for m in input_messages if m.get("role") == "user"]))  # fcg-rewrite
                        data_restore_mapping = detection_result.get("data_result", {}).get("restore_mapping", {})  # fcg-rewrite
                        if data_restore_mapping:  # fcg-rewrite
                            from services.request_context import AnonymizationContext  # fcg-rewrite

                            AnonymizationContext.set_mapping(data_restore_mapping)  # fcg-rewrite
                            logger.info("Saved restore_mapping with %s entries for output restoration", len(data_restore_mapping))  # fcg-rewrite
                elif disposal_action == "anonymize_restore":  # fcg-rewrite
                    detected_entities = detection_result.get("data_result", {}).get("detected_entities", [])  # fcg-rewrite
                    if detected_entities:  # fcg-rewrite
                        modified_messages, restore_mapping = redact_user_messages_restorable(input_messages, detected_entities, application_id, db)  # fcg-rewrite
                        if restore_mapping:  # fcg-rewrite
                            from services.request_context import AnonymizationContext  # fcg-rewrite

                            AnonymizationContext.set_mapping(restore_mapping)  # fcg-rewrite
                            logger.info("Anonymized with restore: %s placeholders created", len(restore_mapping))  # fcg-rewrite
            except Exception as exc:  # fcg-rewrite
                logger.error("Data leakage disposal failed: %s", exc, exc_info=True)  # fcg-rewrite

        suggest_answer = detection_result.get("suggest_answer")  # fcg-rewrite
        if general_risk_level != "no_risk" and application_id:  # fcg-rewrite
            try:
                if not disposal_service:  # fcg-rewrite
                    db = next(get_db())  # fcg-rewrite
                    disposal_service = LeakageMitigator(db)  # fcg-rewrite
                general_action = disposal_service.get_general_risk_action(application_id, general_risk_level)  # fcg-rewrite
                logger.info("General risk action for %s: %s", general_risk_level, general_action)  # fcg-rewrite
                if general_action in ["block", "replace"]:  # fcg-rewrite
                    general_blocked = True  # fcg-rewrite
                    general_block_message = suggest_answer or "Request blocked by FangcunGuard due to policy violation."  # fcg-rewrite
            except Exception as exc:  # fcg-rewrite
                logger.error("Error getting general risk action: %s", exc, exc_info=True)  # fcg-rewrite
                if general_risk_level == "high_risk":  # fcg-rewrite
                    general_blocked = True  # fcg-rewrite
                    general_block_message = suggest_answer or "Request blocked by FangcunGuard due to policy violation."  # fcg-rewrite

        if dlp_blocked or general_blocked:  # fcg-rewrite
            if dlp_blocked and general_blocked:  # fcg-rewrite
                if risk_priority.get(data_risk_level, 0) >= risk_priority.get(general_risk_level, 0):  # fcg-rewrite
                    final_message = dlp_block_message  # fcg-rewrite
                    logger.warning("Request blocked due to DLP risk (%s) - request %s", data_risk_level, request_id)  # fcg-rewrite
                else:
                    final_message = general_block_message  # fcg-rewrite
                    logger.warning("Request blocked due to general risk (%s) - request %s", general_risk_level, request_id)  # fcg-rewrite
            elif dlp_blocked:  # fcg-rewrite
                final_message = dlp_block_message  # fcg-rewrite
                logger.warning("Request blocked due to DLP risk (%s) - request %s", data_risk_level, request_id)  # fcg-rewrite
            else:
                final_message = general_block_message  # fcg-rewrite
                logger.warning("Request blocked due to general risk (%s) - request %s", general_risk_level, request_id)  # fcg-rewrite

            result = detection_result.copy()  # fcg-rewrite
            result["blocked"] = True  # fcg-rewrite
            result["detection_id"] = detection_id  # fcg-rewrite
            result["suggest_answer"] = final_message  # fcg-rewrite
            result["disposal_action"] = "block" if dlp_blocked else "replace"  # fcg-rewrite
            return result  # fcg-rewrite

        return {  # fcg-rewrite
            "blocked": False,  # fcg-rewrite
            "detection_id": detection_id,  # fcg-rewrite
            "suggest_answer": None,  # fcg-rewrite
            "modified_messages": modified_messages,  # fcg-rewrite
            "modified_model_config": modified_model_config,  # fcg-rewrite
            "disposal_action": disposal_action,  # fcg-rewrite
            "restore_mapping": restore_mapping,  # fcg-rewrite
        }
    except Exception as exc:  # fcg-rewrite
        logger.error("Synchronous input detection failed: %s", exc, exc_info=True)  # fcg-rewrite
        logger.error("Detection failed for tenant_id=%s, application_id=%s, messages=%s", tenant_id, application_id, input_messages)  # fcg-rewrite
        return {  # fcg-rewrite
            "blocked": False,  # fcg-rewrite
            "detection_id": f"{request_id}_input_error",  # fcg-rewrite
            "suggest_answer": None,  # fcg-rewrite
            "modified_messages": input_messages,  # fcg-rewrite
            "modified_model_config": model_config,  # fcg-rewrite
        }


async def _execute_async_output_guard(input_messages: list, response_content: str, tenant_id: str, request_id: str, model_config=None, user_id: str = None, application_id: str = None):  # fcg-rewrite
    asyncio.create_task(_async_record_output_guard(input_messages, response_content, tenant_id, request_id, model_config, user_id, application_id))  # fcg-rewrite
    return {  # fcg-rewrite
        "blocked": False,  # fcg-rewrite
        "detection_id": f"{request_id}_output_async",  # fcg-rewrite
        "suggest_answer": None,  # fcg-rewrite
        "response_content": response_content,  # fcg-rewrite
    }


async def _async_record_output_guard(input_messages: list, response_content: str, tenant_id: str, request_id: str, model_config=None, user_id: str = None, application_id: str = None):  # fcg-rewrite
    try:
        detection_messages = input_messages.copy()  # fcg-rewrite
        detection_messages.append({"role": "assistant", "content": response_content})  # fcg-rewrite
        detection_result = await detection_guardrail_service.inspect_message_batch(  # fcg-rewrite
            messages=detection_messages,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            request_id=f"{request_id}_output_async",  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
        )
        detection_id = detection_result.get("request_id")  # fcg-rewrite
        if user_id and detection_result.get("overall_risk_level") in ["medium_risk", "high_risk"]:  # fcg-rewrite
            asyncio.create_task(  # fcg-rewrite
                BanPolicyManager.check_and_apply_ban_policy(  # fcg-rewrite
                    tenant_id=tenant_id,  # fcg-rewrite
                    user_id=user_id,  # fcg-rewrite
                    risk_level=detection_result.get("overall_risk_level"),  # fcg-rewrite
                    detection_result_id=detection_id,  # fcg-rewrite
                    language="zh",  # fcg-rewrite
                )
            )
        if detection_result.get("suggest_action") in ["reject", "replace"]:  # fcg-rewrite
            logger.info("Asynchronous output detection found risk but not blocked - request %s", request_id)  # fcg-rewrite
            logger.info("Detection result: %s", detection_result)  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.error("Background output detection failed: %s", exc)  # fcg-rewrite


async def _execute_sync_output_guard(model_config, input_messages: list, response_content: str, tenant_id: str, request_id: str, user_id: str = None, application_id: str = None):  # fcg-rewrite
    try:
        logger.info("[%s] Starting sync output detection, application_id=%s", request_id, application_id)  # fcg-rewrite
        logger.info("[%s] Output content to detect: %s...", request_id, response_content[:200])  # fcg-rewrite
        detection_messages = input_messages.copy()  # fcg-rewrite
        detection_messages.append({"role": "assistant", "content": response_content})  # fcg-rewrite
        detection_result = await detection_guardrail_service.inspect_message_batch(  # fcg-rewrite
            messages=detection_messages,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            request_id=f"{request_id}_output_sync",  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
        )

        detection_id = detection_result.get("request_id")  # fcg-rewrite
        logger.info(  # fcg-rewrite
            "[%s] Output detection result: overall_risk=%s, suggest_action=%s, security_risk=%s, compliance_risk=%s",  # fcg-rewrite
            request_id,  # fcg-rewrite
            detection_result.get("overall_risk_level"),  # fcg-rewrite
            detection_result.get("suggest_action"),  # fcg-rewrite
            detection_result.get("security_result", {}).get("risk_level"),  # fcg-rewrite
            detection_result.get("compliance_result", {}).get("risk_level"),  # fcg-rewrite
        )

        if user_id and detection_result.get("overall_risk_level") in ["medium_risk", "high_risk"]:  # fcg-rewrite
            await BanPolicyManager.check_and_apply_ban_policy(  # fcg-rewrite
                tenant_id=tenant_id,  # fcg-rewrite
                user_id=user_id,  # fcg-rewrite
                risk_level=detection_result.get("overall_risk_level"),  # fcg-rewrite
                detection_result_id=detection_id,  # fcg-rewrite
                language="zh",  # fcg-rewrite
                application_id=application_id,  # fcg-rewrite
            )

        data_risk_level = detection_result.get("data_result", {}).get("risk_level", "no_risk")  # fcg-rewrite
        compliance_risk = detection_result.get("compliance_result", {}).get("risk_level", "no_risk") if detection_result.get("compliance_result") else "no_risk"  # fcg-rewrite
        security_risk = detection_result.get("security_result", {}).get("risk_level", "no_risk") if detection_result.get("security_result") else "no_risk"  # fcg-rewrite

        risk_priority = {"no_risk": 0, "low_risk": 1, "medium_risk": 2, "high_risk": 3}  # fcg-rewrite
        general_risk_level = "no_risk"  # fcg-rewrite
        for level in [compliance_risk, security_risk]:  # fcg-rewrite
            if risk_priority.get(level, 0) > risk_priority.get(general_risk_level, 0):  # fcg-rewrite
                general_risk_level = level  # fcg-rewrite

        final_content = response_content  # fcg-rewrite
        disposal_action = "pass"  # fcg-rewrite
        disposal_service = None  # fcg-rewrite
        dlp_blocked = False  # fcg-rewrite
        general_blocked = False  # fcg-rewrite

        if data_risk_level != "no_risk" and application_id:  # fcg-rewrite
            try:
                db = next(get_db())  # fcg-rewrite
                disposal_service = LeakageMitigator(db)  # fcg-rewrite
                disposal_action = disposal_service.get_disposal_action(application_id, data_risk_level, direction="output")  # fcg-rewrite
                logger.info("Output data leakage detected (risk=%s), disposal_action=%s", data_risk_level, disposal_action)  # fcg-rewrite
                if disposal_action == "block":  # fcg-rewrite
                    dlp_blocked = True  # fcg-rewrite
                    try:
                        dlp_block_message = get_translation("en", "guardrail", "sensitiveDataPolicyViolation")  # fcg-rewrite
                    except Exception:  # fcg-rewrite
                        dlp_block_message = "Request blocked by FangcunGuard due to sensitive data policy violation."  # fcg-rewrite
                elif disposal_action == "anonymize":  # fcg-rewrite
                    anonymized_text = detection_result.get("data_result", {}).get("anonymized_text")  # fcg-rewrite
                    if anonymized_text:  # fcg-rewrite
                        final_content = anonymized_text  # fcg-rewrite
                        logger.info("Anonymized output content for data safety")  # fcg-rewrite
                elif disposal_action == "switch_private_model":  # fcg-rewrite
                    logger.info("switch_private_model not applicable for output, treating as pass")  # fcg-rewrite
                    disposal_action = "pass"  # fcg-rewrite
            except Exception as exc:  # fcg-rewrite
                logger.error("Output data leakage disposal failed: %s", exc, exc_info=True)  # fcg-rewrite

        suggest_answer = detection_result.get("suggest_answer")  # fcg-rewrite
        if general_risk_level != "no_risk" and application_id:  # fcg-rewrite
            try:
                if not disposal_service:  # fcg-rewrite
                    db = next(get_db())  # fcg-rewrite
                    disposal_service = LeakageMitigator(db)  # fcg-rewrite
                general_action = disposal_service.get_general_risk_action(application_id, general_risk_level, direction="output")  # fcg-rewrite
                logger.info("[%s] Output general risk: level=%s, action=%s, suggest_answer=%s", request_id, general_risk_level, general_action, suggest_answer[:100] if suggest_answer else None)  # fcg-rewrite
                if general_action in ["block", "replace"]:  # fcg-rewrite
                    general_blocked = True  # fcg-rewrite
                    general_block_message = suggest_answer or "Sorry, the generated content contains inappropriate information."  # fcg-rewrite
            except Exception as exc:  # fcg-rewrite
                logger.error("Error getting output general risk action: %s", exc, exc_info=True)  # fcg-rewrite
                if general_risk_level == "high_risk":  # fcg-rewrite
                    general_blocked = True  # fcg-rewrite
                    general_block_message = suggest_answer or "Sorry, the generated content contains inappropriate information."  # fcg-rewrite

        if dlp_blocked or general_blocked:  # fcg-rewrite
            if dlp_blocked and general_blocked:  # fcg-rewrite
                if risk_priority.get(data_risk_level, 0) >= risk_priority.get(general_risk_level, 0):  # fcg-rewrite
                    final_message = dlp_block_message  # fcg-rewrite
                    logger.warning("Response blocked due to DLP risk (%s) - request %s", data_risk_level, request_id)  # fcg-rewrite
                else:
                    final_message = general_block_message  # fcg-rewrite
                    logger.warning("Response blocked due to general risk (%s) - request %s", general_risk_level, request_id)  # fcg-rewrite
            elif dlp_blocked:  # fcg-rewrite
                final_message = dlp_block_message  # fcg-rewrite
                logger.warning("Response blocked due to DLP risk (%s) - request %s", data_risk_level, request_id)  # fcg-rewrite
            else:
                final_message = general_block_message  # fcg-rewrite
                logger.warning("Response blocked due to general risk (%s) - request %s", general_risk_level, request_id)  # fcg-rewrite

            return {  # fcg-rewrite
                "blocked": True,  # fcg-rewrite
                "detection_id": detection_id,  # fcg-rewrite
                "suggest_answer": final_message,  # fcg-rewrite
                "response_content": final_message,  # fcg-rewrite
                "disposal_action": "block" if dlp_blocked else "replace",  # fcg-rewrite
            }

        return {  # fcg-rewrite
            "blocked": False,  # fcg-rewrite
            "detection_id": detection_id,  # fcg-rewrite
            "suggest_answer": None,  # fcg-rewrite
            "response_content": final_content,  # fcg-rewrite
            "disposal_action": disposal_action,  # fcg-rewrite
        }
    except Exception as exc:  # fcg-rewrite
        logger.error("Synchronous output detection failed: %s", exc)  # fcg-rewrite
        return {  # fcg-rewrite
            "blocked": False,  # fcg-rewrite
            "detection_id": f"{request_id}_output_error",  # fcg-rewrite
            "suggest_answer": None,  # fcg-rewrite
            "response_content": response_content,  # fcg-rewrite
        }
