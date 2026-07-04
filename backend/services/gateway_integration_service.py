"""Security decisions exposed to external AI gateways."""

import json  # fcg-rewrite
import os  # fcg-rewrite
import uuid  # fcg-rewrite
from typing import Any, Dict, List, Optional, Tuple  # fcg-rewrite

from cryptography.fernet import Fernet  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import Tenant, UpstreamApiConfig  # fcg-rewrite
from services.ban_policy_service import BanPolicyManager  # fcg-rewrite
from services.data_leakage_disposal_service import LeakageMitigator  # fcg-rewrite
from services.detection_guardrail_service import detection_guardrail_service  # fcg-rewrite
from services.gateway_action_factory import GatewayActionFactory  # fcg-rewrite
from services.gateway_anonymization_service import GatewayAnonymizationCoordinator  # fcg-rewrite
from services.gateway_restore_session_store import GatewayRestoreSessionStore  # fcg-rewrite
from utils.bypass_token import BYPASS_TOKEN_HEADER, make_bypass_token  # fcg-rewrite
from utils.i18n_loader import get_translation  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
_cipher_suite = None  # fcg-rewrite


def _make_cipher() -> Fernet:  # fcg-rewrite
    global _cipher_suite  # fcg-rewrite
    if _cipher_suite is None:  # fcg-rewrite
        from config import settings  # fcg-rewrite

        path = f"{settings.data_dir}/proxy_encryption.key"  # fcg-rewrite
        os.makedirs(os.path.dirname(path), exist_ok=True)  # fcg-rewrite
        if os.path.exists(path):  # fcg-rewrite
            with open(path, "rb") as source:  # fcg-rewrite
                key = source.read()  # fcg-rewrite
        else:
            key = Fernet.generate_key()  # fcg-rewrite
            with open(path, "wb") as destination:  # fcg-rewrite
                destination.write(key)  # fcg-rewrite
        _cipher_suite = Fernet(key)  # fcg-rewrite
    return _cipher_suite  # fcg-rewrite


class GatewayBridge:  # fcg-rewrite
    def __init__(self, db: Session):  # fcg-rewrite
        self.db = db  # fcg-rewrite
        self.disposal_service = LeakageMitigator(db)  # fcg-rewrite
        self.session_store = GatewayRestoreSessionStore()  # fcg-rewrite
        self.anonymization = GatewayAnonymizationCoordinator(self.session_store)  # fcg-rewrite
        self.action_factory = GatewayActionFactory()  # fcg-rewrite

    def _lang(self, tenant_id: Optional[str]) -> str:  # fcg-rewrite
        if not tenant_id:  # fcg-rewrite
            return "en"  # fcg-rewrite
        try:
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()  # fcg-rewrite
            return tenant.language if tenant and tenant.language else "en"  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.warning("Unable to read language for tenant %s: %s", tenant_id, error)  # fcg-rewrite
            return "en"  # fcg-rewrite

    def _get_language(self, tenant_id: Optional[str]) -> str:  # fcg-rewrite
        return self._lang(tenant_id)  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _risk_summary(result: dict, *, inbound: bool) -> dict:  # fcg-rewrite
        data = result.get("data_result") or {}  # fcg-rewrite
        compliance = result.get("compliance_result") or {}  # fcg-rewrite
        security = result.get("security_result") or {}  # fcg-rewrite
        summary = {  # fcg-rewrite
            "data_risk": {  # fcg-rewrite
                "risk_level": data.get("risk_level", "no_risk"),  # fcg-rewrite
                "categories": data.get("categories", []),  # fcg-rewrite
            },
            "compliance_risk": {  # fcg-rewrite
                "risk_level": compliance.get("risk_level", "no_risk"),  # fcg-rewrite
                "categories": compliance.get("categories", []),  # fcg-rewrite
            },
            "security_risk": {  # fcg-rewrite
                "risk_level": security.get("risk_level", "no_risk"),  # fcg-rewrite
                "categories": security.get("categories", []),  # fcg-rewrite
            },
            "overall_risk_level": result.get("overall_risk_level", "no_risk"),  # fcg-rewrite
        }
        if inbound:  # fcg-rewrite
            summary.update(  # fcg-rewrite
                blacklist_hit=result.get("suggest_action") == "reject" and not data.get("risk_level"),  # fcg-rewrite
                blacklist_keywords=[],  # fcg-rewrite
                whitelist_hit=result.get("suggest_action", "pass") == "pass"  # fcg-rewrite
                and summary["overall_risk_level"] == "no_risk",  # fcg-rewrite
                matched_scanners=[],  # fcg-rewrite
            )
            summary["data_risk"]["entity_count"] = len(data.get("detected_entities", []))  # fcg-rewrite
        return summary  # fcg-rewrite

    async def _inspect(self, messages, tenant_id: str, request_id: str, application_id: str):  # fcg-rewrite
        return await detection_guardrail_service.inspect_message_batch(  # fcg-rewrite
            messages=messages, tenant_id=tenant_id, request_id=request_id, application_id=application_id  # fcg-rewrite
        )

    def _general_risk_action(self, result: dict, application_id: str, direction: str = "input"):  # fcg-rewrite
        compliance = result.get("compliance_result") or {}  # fcg-rewrite
        security = result.get("security_result") or {}  # fcg-rewrite
        if not (compliance.get("categories") or security.get("categories")):  # fcg-rewrite
            return None  # fcg-rewrite
        return self.disposal_service.get_general_risk_action(  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            risk_level=result.get("overall_risk_level", "no_risk"),  # fcg-rewrite
            **({"direction": direction} if direction != "input" else {}),  # fcg-rewrite
        )

    def _general_risk_response(self, action, request_id, language, summary, result, *, outbound=False):  # fcg-rewrite
        if action not in {"block", "replace"}:  # fcg-rewrite
            return None  # fcg-rewrite
        fallback = (  # fcg-rewrite
            "responseBlockedSecurity" if outbound and action == "block"  # fcg-rewrite
            else "cannotProvideInformation" if outbound  # fcg-rewrite
            else "securityPolicyBlocked" if action == "block"  # fcg-rewrite
            else "cannotAssist"  # fcg-rewrite
        )
        message = result.get("suggest_answer") or get_translation(language, "guardrail", fallback)  # fcg-rewrite
        if action == "block":  # fcg-rewrite
            return self._create_block_response(request_id, "security_risk", message, summary)  # fcg-rewrite
        return self._create_replace_response(request_id, message, summary)  # fcg-rewrite

    async def gate_inbound_traffic(  # fcg-rewrite
        self,
        application_id: str,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        messages: List[Dict[str, Any]],  # fcg-rewrite
        stream: bool = False,  # fcg-rewrite
        client_ip: Optional[str] = None,  # fcg-rewrite
        user_id: Optional[str] = None,  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        request_id, language = f"gw-{uuid.uuid4().hex[:12]}", self._lang(tenant_id)  # fcg-rewrite
        try:
            if user_id:  # fcg-rewrite
                ban = await BanPolicyManager.check_user_banned(tenant_id, user_id)  # fcg-rewrite
                if ban:
                    message = get_translation(language, "guardrail", "userBannedUntil").format(  # fcg-rewrite
                        ban_until=ban.get("ban_until", "indefinitely")  # fcg-rewrite
                    )
                    return self._create_block_response(request_id, "user_banned", message, {"banned": True, "user_id": user_id})  # fcg-rewrite
            if client_ip and await BanPolicyManager.check_ip_banned(tenant_id, client_ip):  # fcg-rewrite
                return self._create_block_response(  # fcg-rewrite
                    request_id, "ip_banned", get_translation(language, "guardrail", "ipAddressBanned"),  # fcg-rewrite
                    {"banned": True, "client_ip": client_ip},  # fcg-rewrite
                )
            result = await self._inspect(messages, tenant_id, request_id, application_id)  # fcg-rewrite
            summary = self._risk_summary(result, inbound=True)  # fcg-rewrite
            response = self._general_risk_response(  # fcg-rewrite
                self._general_risk_action(result, application_id), request_id, language, summary, result  # fcg-rewrite
            )
            if response:  # fcg-rewrite
                return response  # fcg-rewrite
            data = result.get("data_result") or {}  # fcg-rewrite
            entities = data.get("detected_entities", [])  # fcg-rewrite
            if data.get("risk_level", "no_risk") != "no_risk" and entities:  # fcg-rewrite
                action = self.disposal_service.get_disposal_action(  # fcg-rewrite
                    application_id=application_id, risk_level=data["risk_level"], direction="input"  # fcg-rewrite
                )
                if action == "block":  # fcg-rewrite
                    return self._create_block_response(  # fcg-rewrite
                        request_id, "data_leakage_policy",  # fcg-rewrite
                        get_translation(language, "guardrail", "sensitiveDataPolicyViolation"), summary,  # fcg-rewrite
                    )
                if action == "switch_private_model":  # fcg-rewrite
                    model = self.disposal_service.get_private_model(application_id=application_id, tenant_id=tenant_id)  # fcg-rewrite
                    if model:  # fcg-rewrite
                        return self._create_switch_model_response(request_id, model, summary, tenant_id)  # fcg-rewrite
                    return self._create_block_response(  # fcg-rewrite
                        request_id, "no_private_model",  # fcg-rewrite
                        get_translation(language, "guardrail", "noPrivateModelConfigured"), summary,  # fcg-rewrite
                    )
                if action in {"anonymize", "anonymize_restore"}:  # fcg-rewrite
                    changed, session_id, mapping = self._anonymize_messages(  # fcg-rewrite
                        messages, entities, application_id, tenant_id, action  # fcg-rewrite
                    )
                    return {  # fcg-rewrite
                        "action": "anonymize", "request_id": request_id, "detection_result": summary,  # fcg-rewrite
                        "anonymized_messages": changed, "session_id": session_id, "restore_mapping": mapping,  # fcg-rewrite
                    }
            return {"action": "pass", "request_id": request_id, "detection_result": summary}  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Inbound gateway inspection %s failed: %s", request_id, error)  # fcg-rewrite
            return {"action": "pass", "request_id": request_id, "detection_result": {"error": str(error), "overall_risk_level": "unknown"}}  # fcg-rewrite

    async def gate_outbound_traffic(  # fcg-rewrite
        self,
        application_id: str,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        content: str,  # fcg-rewrite
        session_id: Optional[str] = None,  # fcg-rewrite
        restore_mapping: Optional[Dict[str, str]] = None,  # fcg-rewrite
        is_streaming: bool = False,  # fcg-rewrite
        chunk_index: int = 0,  # fcg-rewrite
        input_messages: Optional[List[Dict[str, Any]]] = None,  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        request_id, language = f"gw-out-{uuid.uuid4().hex[:12]}", self._lang(tenant_id)  # fcg-rewrite
        try:
            session = self._get_session(session_id) if session_id and not restore_mapping else None  # fcg-rewrite
            mapping = restore_mapping or (session or {}).get("mapping")  # fcg-rewrite
            restored = self._restore_content(content, mapping) if mapping else content  # fcg-rewrite
            messages = [*(input_messages or []), {"role": "assistant", "content": restored}]  # fcg-rewrite
            result = await self._inspect(messages, tenant_id, request_id, application_id)  # fcg-rewrite
            summary = self._risk_summary(result, inbound=False)  # fcg-rewrite
            response = self._general_risk_response(  # fcg-rewrite
                self._general_risk_action(result, application_id, "output"),  # fcg-rewrite
                request_id, language, summary, result, outbound=True,  # fcg-rewrite
            )
            if response:  # fcg-rewrite
                return response  # fcg-rewrite
            data = result.get("data_result") or {}  # fcg-rewrite
            entities = data.get("detected_entities", [])  # fcg-rewrite
            if data.get("risk_level", "no_risk") != "no_risk" and entities:  # fcg-rewrite
                action = self.disposal_service.get_disposal_action(  # fcg-rewrite
                    application_id=application_id, risk_level=data["risk_level"], direction="output"  # fcg-rewrite
                )
                if action == "block":  # fcg-rewrite
                    return self._create_block_response(  # fcg-rewrite
                        request_id, "data_leakage_policy",  # fcg-rewrite
                        get_translation(language, "guardrail", "responseBlockedDataLeakage"), summary,  # fcg-rewrite
                    )
                if action == "anonymize":  # fcg-rewrite
                    return {  # fcg-rewrite
                        "action": "anonymize", "request_id": request_id, "detection_result": summary,  # fcg-rewrite
                        "anonymized_content": self._anonymize_output_content(restored, entities),  # fcg-rewrite
                    }
            if mapping:  # fcg-rewrite
                return {"action": "restore", "request_id": request_id, "detection_result": summary, "restored_content": restored, "buffer_pending": ""}  # fcg-rewrite
            return {"action": "pass", "request_id": request_id, "detection_result": summary, "content": content}  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Outbound gateway inspection %s failed: %s", request_id, error)  # fcg-rewrite
            return {"action": "pass", "request_id": request_id, "detection_result": {"error": str(error)}, "content": content}  # fcg-rewrite

    def _anonymize_messages(  # fcg-rewrite
        self, messages, detected_entities, application_id, tenant_id, action="anonymize_restore"  # fcg-rewrite
    ) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[Dict[str, str]]]:  # fcg-rewrite
        return self.anonymization.anonymize_messages(messages, detected_entities, application_id, tenant_id, action)  # fcg-rewrite

    def _create_session(self, mapping: Dict[str, str], tenant_id: str) -> str:  # fcg-rewrite
        return self.session_store.create_session(mapping, tenant_id)  # fcg-rewrite

    def _get_session(self, session_id: str) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        return self.session_store.get_session(session_id)  # fcg-rewrite

    def _cleanup_expired_sessions(self):  # fcg-rewrite
        self.session_store.cleanup_expired_sessions()  # fcg-rewrite

    def _restore_content(self, content: str, mapping: Dict[str, str]) -> str:  # fcg-rewrite
        return self.anonymization.restore_content(content, mapping)  # fcg-rewrite

    def _anonymize_output_content(self, content: str, detected_entities: List[Dict[str, Any]]) -> str:  # fcg-rewrite
        return self.anonymization.anonymize_output_content(content, detected_entities)  # fcg-rewrite

    def _create_block_response(self, request_id, reason, message, detection_result):  # fcg-rewrite
        return self.action_factory.create_block_response(request_id, reason, message, detection_result)  # fcg-rewrite

    def _create_replace_response(self, request_id, message, detection_result):  # fcg-rewrite
        return self.action_factory.create_replace_response(request_id, message, detection_result)  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _decrypt_api_key(private_model: UpstreamApiConfig) -> str:  # fcg-rewrite
        try:
            return _make_cipher().decrypt(private_model.api_key_encrypted.encode()).decode() if private_model.api_key_encrypted else ""  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Unable to decrypt private model API key: %s", error)  # fcg-rewrite
            return ""  # fcg-rewrite

    async def _proxy_to_private_model(  # fcg-rewrite
        self, request_id: str, private_model: UpstreamApiConfig, messages: List[Dict[str, Any]],  # fcg-rewrite
        tenant_id: str, stream: bool = False, original_request_body: Optional[Dict[str, Any]] = None,  # fcg-rewrite
    ) -> Optional[Dict[str, Any]]:  # fcg-rewrite
        import httpx  # fcg-rewrite

        if stream:  # fcg-rewrite
            return None  # fcg-rewrite
        try:
            base, key = private_model.api_base_url.rstrip("/"), self._decrypt_api_key(private_model)  # fcg-rewrite
            model_name = private_model.default_private_model_name  # fcg-rewrite
            headers = {"Content-Type": "application/json", BYPASS_TOKEN_HEADER: make_bypass_token(tenant_id, request_id)}  # fcg-rewrite
            if key:
                headers["Authorization"] = f"Bearer {key}"  # fcg-rewrite
            async with httpx.AsyncClient(timeout=120.0) as client:  # fcg-rewrite
                if not model_name:  # fcg-rewrite
                    available = await client.get(f"{base}/models", headers=headers)  # fcg-rewrite
                    if available.status_code == 200 and available.json().get("data"):  # fcg-rewrite
                        model_name = available.json()["data"][0].get("id")  # fcg-rewrite
                body = {"model": model_name or "gpt-4", "messages": messages, "stream": False}  # fcg-rewrite
                for field in ("temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty"):  # fcg-rewrite
                    if original_request_body and field in original_request_body:  # fcg-rewrite
                        body[field] = original_request_body[field]  # fcg-rewrite
                response = await client.post(f"{base}/chat/completions", json=body, headers=headers)  # fcg-rewrite
                if response.status_code != 200:  # fcg-rewrite
                    return None  # fcg-rewrite
                return {  # fcg-rewrite
                    "action": "proxy_response", "request_id": request_id,  # fcg-rewrite
                    "proxy_response": {"code": 200, "content_type": "application/json", "body": json.dumps(response.json())},  # fcg-rewrite
                }
        except Exception as error:  # fcg-rewrite
            logger.error("Private model proxy %s failed: %s", request_id, error)  # fcg-rewrite
            return None  # fcg-rewrite

    def _create_switch_model_response(self, request_id, private_model, detection_result, tenant_id):  # fcg-rewrite
        return {  # fcg-rewrite
            "action": "switch_private_model", "request_id": request_id, "detection_result": detection_result,  # fcg-rewrite
            "private_model": {  # fcg-rewrite
                "api_base_url": private_model.api_base_url, "api_key": self._decrypt_api_key(private_model),  # fcg-rewrite
                "model_name": private_model.default_private_model_name or "gpt-4", "provider": private_model.provider,  # fcg-rewrite
                "higress_cluster": private_model.higress_cluster,  # fcg-rewrite
            },
            "bypass_token": make_bypass_token(tenant_id, request_id), "bypass_header": BYPASS_TOKEN_HEADER,  # fcg-rewrite
        }


def wire_gateway_bridge(db: Session) -> GatewayBridge:  # fcg-rewrite
    return GatewayBridge(db)  # fcg-rewrite
