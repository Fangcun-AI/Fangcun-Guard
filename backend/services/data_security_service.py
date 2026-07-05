"""
Data security service - sensitive data detection and de-sensitization based on regular expressions
"""

import json  # fcg-rewrite
import re  # fcg-rewrite
from typing import Any, Dict, List, Optional, Tuple  # fcg-rewrite

from sqlalchemy import and_  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import DataSecurityEntityType  # fcg-rewrite
from services.data_security_anonymization import (  # fcg-rewrite
    RISK_LEVEL_MAPPING,  # fcg-rewrite
    DataSecurityAnonymizer,  # fcg-rewrite
    translate_replacement_template,  # fcg-rewrite
)
from services.data_security_entity_store import DataSecurityEntityStore  # fcg-rewrite
from services.format_detection_service import format_detection_service  # fcg-rewrite
from services.general_llm_service import general_llm_service  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


def _clean_llm_json(result: str) -> Dict[str, Any]:  # fcg-rewrite
    cleaned = result.strip()  # fcg-rewrite
    if cleaned.startswith("```"):  # fcg-rewrite
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]  # fcg-rewrite
    if cleaned.endswith("```"):  # fcg-rewrite
        cleaned = cleaned[:-3]  # fcg-rewrite
    return json.loads(cleaned.strip())  # fcg-rewrite


class PrivacyEngine:  # fcg-rewrite
    """Facade for runtime detection, anonymization, and entity type management."""

    def __init__(self, db: Session):  # fcg-rewrite
        self.db = db  # fcg-rewrite
        self.general_llm = general_llm_service  # fcg-rewrite
        self.entity_store = DataSecurityEntityStore(db, logger)  # fcg-rewrite
        self.anonymizer = DataSecurityAnonymizer(self.general_llm, logger)  # fcg-rewrite

    async def detect_sensitive_data(  # fcg-rewrite
        self,
        text: str,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        direction: str = "input",  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        enable_format_detection: bool = True,  # fcg-rewrite
        enable_smart_segmentation: bool = True,  # fcg-rewrite
    ) -> Dict[str, Any]:  # fcg-rewrite
        format_type = "plain_text"  # fcg-rewrite
        format_metadata: Dict[str, Any] = {}  # fcg-rewrite
        if enable_format_detection:  # fcg-rewrite
            try:
                format_type, format_metadata = format_detection_service.detect_format(text)  # fcg-rewrite
                logger.info(f"Detected format: {format_type}")  # fcg-rewrite
            except Exception as exc:  # fcg-rewrite
                logger.warning(f"Format detection failed: {exc}, falling back to plain_text")  # fcg-rewrite

        entity_types = self._get_user_entity_types(tenant_id, direction, application_id)  # fcg-rewrite
        if not entity_types:  # fcg-rewrite
            return {  # fcg-rewrite
                "risk_level": "no_risk",  # fcg-rewrite
                "categories": [],  # fcg-rewrite
                "detected_entities": [],  # fcg-rewrite
                "anonymized_text": text,  # fcg-rewrite
                "format_info": {  # fcg-rewrite
                    "format_type": format_type,  # fcg-rewrite
                    "metadata": format_metadata,  # fcg-rewrite
                },
            }

        regex_entity_types = [  # fcg-rewrite
            entity_type  # fcg-rewrite
            for entity_type in entity_types  # fcg-rewrite
            if entity_type.get("recognition_method", "regex") == "regex"  # fcg-rewrite
        ]
        logger.info(f"Entity types: {len(regex_entity_types)} regex")  # fcg-rewrite

        detected_entities: List[Dict[str, Any]] = []  # fcg-rewrite
        highest_risk_level = "no_risk"  # fcg-rewrite
        detected_categories = set()  # fcg-rewrite

        for entity_type in regex_entity_types:  # fcg-rewrite
            pattern_preview = (  # fcg-rewrite
                entity_type.get("pattern", "")[:80] if entity_type.get("pattern") else "NO PATTERN"  # fcg-rewrite
            )
            logger.info(  # fcg-rewrite
                f"Regex checking entity type: {entity_type.get('entity_type')} with pattern: {pattern_preview}"  # fcg-rewrite
            )
            matches = self._match_pattern(text, entity_type)  # fcg-rewrite
            logger.info(  # fcg-rewrite
                f"Regex result for {entity_type.get('entity_type')}: {len(matches)} matches"  # fcg-rewrite
            )
            if matches:  # fcg-rewrite
                detected_entities.extend(matches)  # fcg-rewrite
                detected_categories.add(entity_type["entity_type"])  # fcg-rewrite
                entity_risk = entity_type.get("risk_level", "medium")  # fcg-rewrite
                if self._compare_risk_level(entity_risk, highest_risk_level) > 0:  # fcg-rewrite
                    highest_risk_level = RISK_LEVEL_MAPPING.get(entity_risk, "medium_risk")  # fcg-rewrite

        anonymized_text, restore_mapping = self._anonymize_text_unified(  # fcg-rewrite
            text, detected_entities, entity_types  # fcg-rewrite
        )

        return {  # fcg-rewrite
            "risk_level": highest_risk_level,  # fcg-rewrite
            "categories": list(detected_categories),  # fcg-rewrite
            "detected_entities": detected_entities,  # fcg-rewrite
            "anonymized_text": anonymized_text,  # fcg-rewrite
            "restore_mapping": restore_mapping if restore_mapping else None,  # fcg-rewrite
            "format_info": {  # fcg-rewrite
                "format_type": format_type,  # fcg-rewrite
                "metadata": format_metadata,  # fcg-rewrite
            },
        }

    def _get_user_entity_types(  # fcg-rewrite
        self, tenant_id: str, direction: str, application_id: Optional[str] = None  # fcg-rewrite
    ) -> List[Dict[str, Any]]:  # fcg-rewrite
        return self.entity_store.get_detection_entity_types(tenant_id, direction, application_id)  # fcg-rewrite

    def _match_pattern(self, text: str, entity_type: Dict[str, Any]) -> List[Dict[str, Any]]:  # fcg-rewrite
        return self.anonymizer.match_pattern(text, entity_type)  # fcg-rewrite

    def _anonymize_text(  # fcg-rewrite
        self,
        text: str,  # fcg-rewrite
        detected_entities: List[Dict[str, Any]],  # fcg-rewrite
        entity_types: List[Dict[str, Any]],  # fcg-rewrite
    ) -> str:  # fcg-rewrite
        return self.anonymizer.anonymize_text(text, detected_entities, entity_types)  # fcg-rewrite

    def _anonymize_text_unified(  # fcg-rewrite
        self,
        text: str,  # fcg-rewrite
        detected_entities: List[Dict[str, Any]],  # fcg-rewrite
        entity_types: List[Dict[str, Any]],  # fcg-rewrite
    ) -> Tuple[str, Dict[str, str]]:  # fcg-rewrite
        return self.anonymizer.anonymize_text_unified(text, detected_entities, entity_types)  # fcg-rewrite

    def anonymize_text_with_restore(  # fcg-rewrite
        self,
        text: str,  # fcg-rewrite
        detected_entities: List[Dict[str, Any]],  # fcg-rewrite
        entity_type_configs: Dict[str, Any],  # fcg-rewrite
        existing_mapping: Dict[str, str] = None,  # fcg-rewrite
        existing_counters: Dict[str, int] = None,  # fcg-rewrite
    ) -> Tuple[str, Dict[str, str], Dict[str, int]]:  # fcg-rewrite
        return self.anonymizer.anonymize_text_with_restore(  # fcg-rewrite
            text,
            detected_entities,  # fcg-rewrite
            entity_type_configs,  # fcg-rewrite
            existing_mapping,  # fcg-rewrite
            existing_counters,  # fcg-rewrite
        )

    async def generate_anonymization_regex(  # fcg-rewrite
        self, description: str, entity_type: str, sample_data: str = None  # fcg-rewrite
    ) -> dict:  # fcg-rewrite
        sample = f"\nExample input: {sample_data}" if sample_data else ""  # fcg-rewrite
        parsed, error = await self._request_json(  # fcg-rewrite
            "anonymization regex",  # fcg-rewrite
            f"""Design one Python regular expression replacement.  # fcg-rewrite
Sensitive type: {entity_type}
Masking rule: {description}{sample}
Use capture groups and Python backreferences such as \\1. Use * for hidden text.
Reply as JSON with regex_pattern, replacement_template, and explanation.""",
        )
        if error:  # fcg-rewrite
            return {"success": False, "regex_pattern": "", "replacement_template": "***", "explanation": error}  # fcg-rewrite
        return {  # fcg-rewrite
            "success": True,  # fcg-rewrite
            "regex_pattern": parsed.get("regex_pattern", ""),  # fcg-rewrite
            "replacement_template": parsed.get("replacement_template", "***"),  # fcg-rewrite
            "explanation": parsed.get("explanation", ""),  # fcg-rewrite
        }

    async def generate_recognition_regex(  # fcg-rewrite
        self, description: str, entity_type: str, sample_data: str = None  # fcg-rewrite
    ) -> dict:  # fcg-rewrite
        sample = f"\nPositive example: {sample_data}" if sample_data else ""  # fcg-rewrite
        parsed, error = await self._request_json(  # fcg-rewrite
            "recognition regex",  # fcg-rewrite
            f"""Produce a precise regex for detecting sensitive values.  # fcg-rewrite
Sensitive type: {entity_type}
Detection rule: {description}{sample}
Balance common variants against false positives.
Reply as JSON with regex_pattern and explanation.""",
        )
        if error:  # fcg-rewrite
            return {"success": False, "regex_pattern": "", "explanation": error}  # fcg-rewrite
        return {"success": True, "regex_pattern": parsed.get("regex_pattern", ""), "explanation": parsed.get("explanation", "")}  # fcg-rewrite

    async def generate_entity_type_code(self, entity_type_name: str) -> dict:  # fcg-rewrite
        parsed, error = await self._request_json(  # fcg-rewrite
            "entity type code",  # fcg-rewrite
            f"""Create a concise identifier for this sensitive-data type: {entity_type_name}  # fcg-rewrite
Use uppercase English letters and underscores only. Prefer two to four words.
Reply as JSON with entity_type_code.""",
        )
        if error:  # fcg-rewrite
            return {"success": False, "entity_type_code": "", "error": error}  # fcg-rewrite
        code = parsed.get("entity_type_code", "")  # fcg-rewrite
        if code and re.match(r"^[A-Z][A-Z_]*[A-Z]$|^[A-Z]+$", code):  # fcg-rewrite
            return {"success": True, "entity_type_code": code}  # fcg-rewrite
        fixed_code = re.sub(r"_+", "_", re.sub(r"[^A-Z_]", "", code.upper().replace(" ", "_"))).strip("_")  # fcg-rewrite
        return (  # fcg-rewrite
            {"success": True, "entity_type_code": fixed_code}  # fcg-rewrite
            if fixed_code  # fcg-rewrite
            else {"success": False, "entity_type_code": "", "error": "Generated code format is invalid"}  # fcg-rewrite
        )

    async def _request_json(self, label: str, prompt: str):  # fcg-rewrite
        try:
            response = await self.general_llm.chat(  # fcg-rewrite
                [
                    {"role": "system", "content": "Return one valid JSON object without markdown."},  # fcg-rewrite
                    {"role": "user", "content": prompt},  # fcg-rewrite
                ]
            )
            if not response:  # fcg-rewrite
                return None, "No response from AI model"  # fcg-rewrite
            return _clean_llm_json(response), None  # fcg-rewrite
        except json.JSONDecodeError as error:  # fcg-rewrite
            logger.warning("Failed to parse %s response as JSON: %s", label, error)  # fcg-rewrite
            return None, f"Failed to parse response: {error}"  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            logger.error("Generate %s failed: %s", label, error)  # fcg-rewrite
            return None, f"Error: {error}"  # fcg-rewrite

    def test_recognition_regex(self, pattern: str, test_input: str) -> dict:  # fcg-rewrite
        import time  # fcg-rewrite

        start_time = time.time()  # fcg-rewrite
        try:
            if not pattern:  # fcg-rewrite
                return {  # fcg-rewrite
                    "success": False,  # fcg-rewrite
                    "matched": False,  # fcg-rewrite
                    "matches": [],  # fcg-rewrite
                    "error": "Pattern is empty",  # fcg-rewrite
                    "processing_time_ms": (time.time() - start_time) * 1000,  # fcg-rewrite
                }

            regex = re.compile(pattern)  # fcg-rewrite
            matches = regex.findall(test_input)  # fcg-rewrite
            if matches and isinstance(matches[0], tuple):  # fcg-rewrite
                matches = [match.group(0) for match in regex.finditer(test_input)]  # fcg-rewrite

            return {  # fcg-rewrite
                "success": True,  # fcg-rewrite
                "matched": len(matches) > 0,  # fcg-rewrite
                "matches": matches,  # fcg-rewrite
                "match_count": len(matches),  # fcg-rewrite
                "processing_time_ms": (time.time() - start_time) * 1000,  # fcg-rewrite
            }
        except re.error as exc:  # fcg-rewrite
            return {  # fcg-rewrite
                "success": False,  # fcg-rewrite
                "matched": False,  # fcg-rewrite
                "matches": [],  # fcg-rewrite
                "error": f"Invalid regex pattern: {str(exc)}",  # fcg-rewrite
                "processing_time_ms": (time.time() - start_time) * 1000,  # fcg-rewrite
            }
        except Exception as exc:  # fcg-rewrite
            return {  # fcg-rewrite
                "success": False,  # fcg-rewrite
                "matched": False,  # fcg-rewrite
                "matches": [],  # fcg-rewrite
                "error": f"Error: {str(exc)}",  # fcg-rewrite
                "processing_time_ms": (time.time() - start_time) * 1000,  # fcg-rewrite
            }

    def test_anonymization(self, method: str, config: dict, test_input: str) -> dict:  # fcg-rewrite
        return self.anonymizer.test_anonymization(method, config, test_input)  # fcg-rewrite

    def _compare_risk_level(self, level1: str, level2: str) -> int:  # fcg-rewrite
        return self.anonymizer.compare_risk_level(level1, level2)  # fcg-rewrite

    def create_entity_type(  # fcg-rewrite
        self,
        tenant_id: str,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        entity_type: str = None,  # fcg-rewrite
        entity_type_name: str = None,  # fcg-rewrite
        risk_level: str = None,  # fcg-rewrite
        pattern: str = None,  # fcg-rewrite
        entity_definition: str = None,  # fcg-rewrite
        recognition_method: str = "regex",  # fcg-rewrite
        anonymization_method: str = "replace",  # fcg-rewrite
        anonymization_config: Optional[Dict[str, Any]] = None,  # fcg-rewrite
        check_input: bool = True,  # fcg-rewrite
        check_output: bool = True,  # fcg-rewrite
        is_global: bool = False,  # fcg-rewrite
        source_type: str = "custom",  # fcg-rewrite
        template_id: Optional[str] = None,  # fcg-rewrite
        restore_natural_desc: Optional[str] = None,  # fcg-rewrite
    ) -> DataSecurityEntityType:  # fcg-rewrite
        return self.entity_store.create_entity_type(  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            entity_type=entity_type,  # fcg-rewrite
            entity_type_name=entity_type_name,  # fcg-rewrite
            risk_level=risk_level,  # fcg-rewrite
            pattern=pattern,  # fcg-rewrite
            entity_definition=entity_definition,  # fcg-rewrite
            recognition_method=recognition_method,  # fcg-rewrite
            anonymization_method=anonymization_method,  # fcg-rewrite
            anonymization_config=anonymization_config,  # fcg-rewrite
            check_input=check_input,  # fcg-rewrite
            check_output=check_output,  # fcg-rewrite
            is_global=is_global,  # fcg-rewrite
            source_type=source_type,  # fcg-rewrite
            template_id=template_id,  # fcg-rewrite
            restore_natural_desc=restore_natural_desc,  # fcg-rewrite
        )

    def update_entity_type(  # fcg-rewrite
        self,
        entity_type_id: str,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        **kwargs,  # fcg-rewrite
    ) -> Optional[DataSecurityEntityType]:  # fcg-rewrite
        return self.entity_store.update_entity_type(  # fcg-rewrite
            entity_type_id, tenant_id, application_id, **kwargs  # fcg-rewrite
        )

    def delete_entity_type(  # fcg-rewrite
        self, entity_type_id: str, tenant_id: str, application_id: Optional[str] = None  # fcg-rewrite
    ) -> bool:  # fcg-rewrite
        return self.entity_store.delete_entity_type(entity_type_id, tenant_id, application_id)  # fcg-rewrite

    def get_entity_types(  # fcg-rewrite
        self,
        tenant_id: str,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        risk_level: Optional[str] = None,  # fcg-rewrite
        is_active: Optional[bool] = None,  # fcg-rewrite
    ) -> List[DataSecurityEntityType]:  # fcg-rewrite
        return self.entity_store.get_entity_types(  # fcg-rewrite
            tenant_id, application_id, risk_level, is_active  # fcg-rewrite
        )

    def disable_entity_type_for_application(  # fcg-rewrite
        self, tenant_id: str, application_id: str, entity_type: str  # fcg-rewrite
    ) -> bool:  # fcg-rewrite
        return self.entity_store.disable_entity_type_for_application(  # fcg-rewrite
            tenant_id, application_id, entity_type  # fcg-rewrite
        )

    def enable_entity_type_for_application(  # fcg-rewrite
        self, tenant_id: str, application_id: str, entity_type: str  # fcg-rewrite
    ) -> bool:  # fcg-rewrite
        return self.entity_store.enable_entity_type_for_application(  # fcg-rewrite
            tenant_id, application_id, entity_type  # fcg-rewrite
        )

    def get_application_disabled_entity_types(  # fcg-rewrite
        self, tenant_id: str, application_id: str  # fcg-rewrite
    ) -> List[str]:  # fcg-rewrite
        return self.entity_store.get_application_disabled_entity_types(  # fcg-rewrite
            tenant_id, application_id  # fcg-rewrite
        )

    def disable_entity_type_for_tenant(self, tenant_id: str, entity_type: str) -> bool:  # fcg-rewrite
        return self.entity_store.disable_entity_type_for_tenant(tenant_id, entity_type)  # fcg-rewrite

    def enable_entity_type_for_tenant(self, tenant_id: str, entity_type: str) -> bool:  # fcg-rewrite
        return self.entity_store.enable_entity_type_for_tenant(tenant_id, entity_type)  # fcg-rewrite

    def get_tenant_disabled_entity_types(self, tenant_id: str) -> List[str]:  # fcg-rewrite
        return self.entity_store.get_tenant_disabled_entity_types(tenant_id)  # fcg-rewrite

    def ensure_application_has_system_copies(self, tenant_id: str, application_id: str) -> int:  # fcg-rewrite
        return self.entity_store.ensure_application_has_system_copies(tenant_id, application_id)  # fcg-rewrite

    def ensure_tenant_has_system_copies(self, tenant_id: str) -> int:  # fcg-rewrite
        return self.entity_store.ensure_tenant_has_system_copies(tenant_id)  # fcg-rewrite


def get_default_entity_types_config() -> List[Dict[str, Any]]:  # fcg-rewrite
    return [  # fcg-rewrite
        {
            "entity_type": "ID_CARD_NUMBER_SYS",  # fcg-rewrite
            "entity_type_name": "ID Card Number",  # fcg-rewrite
            "risk_level": "high",  # fcg-rewrite
            "pattern": r"[1-8]\d{5}(19|20)\d{2}((0[1-9])|(1[0-2]))((0[1-9])|([12]\d)|(3[01]))\d{3}[\dxX]",  # fcg-rewrite
            "anonymization_method": "mask",  # fcg-rewrite
            "anonymization_config": {"mask_char": "*", "keep_prefix": 3, "keep_suffix": 4},  # fcg-rewrite
            "check_input": True,  # fcg-rewrite
            "check_output": True,  # fcg-rewrite
        },
        {
            "entity_type": "PHONE_NUMBER_SYS",  # fcg-rewrite
            "entity_type_name": "Phone Number",  # fcg-rewrite
            "risk_level": "medium",  # fcg-rewrite
            "pattern": r"1[3-9]\d{9}",  # fcg-rewrite
            "anonymization_method": "mask",  # fcg-rewrite
            "anonymization_config": {"mask_char": "*", "keep_prefix": 3, "keep_suffix": 4},  # fcg-rewrite
            "check_input": True,  # fcg-rewrite
            "check_output": True,  # fcg-rewrite
        },
        {
            "entity_type": "EMAIL_SYS",  # fcg-rewrite
            "entity_type_name": "Email",  # fcg-rewrite
            "risk_level": "low",  # fcg-rewrite
            "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # fcg-rewrite
            "anonymization_method": "mask",  # fcg-rewrite
            "anonymization_config": {"mask_char": "*", "keep_prefix": 2, "keep_suffix": 0},  # fcg-rewrite
            "check_input": True,  # fcg-rewrite
            "check_output": True,  # fcg-rewrite
        },
        {
            "entity_type": "BANK_CARD_NUMBER_SYS",  # fcg-rewrite
            "entity_type_name": "Bank Card Number",  # fcg-rewrite
            "risk_level": "high",  # fcg-rewrite
            "pattern": r"\d{16,19}",  # fcg-rewrite
            "anonymization_method": "mask",  # fcg-rewrite
            "anonymization_config": {"mask_char": "*", "keep_prefix": 4, "keep_suffix": 4},  # fcg-rewrite
            "check_input": True,  # fcg-rewrite
            "check_output": True,  # fcg-rewrite
        },
        {
            "entity_type": "PASSPORT_NUMBER_SYS",  # fcg-rewrite
            "entity_type_name": "Passport Number",  # fcg-rewrite
            "risk_level": "high",  # fcg-rewrite
            "pattern": r"[EGP]\d{8}",  # fcg-rewrite
            "anonymization_method": "mask",  # fcg-rewrite
            "anonymization_config": {"mask_char": "*", "keep_prefix": 1, "keep_suffix": 2},  # fcg-rewrite
            "check_input": True,  # fcg-rewrite
            "check_output": True,  # fcg-rewrite
        },
        {
            "entity_type": "IP_ADDRESS_SYS",  # fcg-rewrite
            "entity_type_name": "IP Address",  # fcg-rewrite
            "risk_level": "low",  # fcg-rewrite
            "pattern": r"(?:\d{1,3}\.){3}\d{1,3}",  # fcg-rewrite
            "anonymization_method": "replace",  # fcg-rewrite
            "anonymization_config": {"replacement": "<IP_ADDRESS>"},  # fcg-rewrite
            "check_input": True,  # fcg-rewrite
            "check_output": True,  # fcg-rewrite
        },
    ]


def create_global_entity_types(db: Session, admin_tenant_id: str) -> int:  # fcg-rewrite
    service = PrivacyEngine(db)  # fcg-rewrite
    created_count = 0  # fcg-rewrite
    for entity_data in get_default_entity_types_config():  # fcg-rewrite
        try:
            existing = db.query(DataSecurityEntityType).filter(  # fcg-rewrite
                and_(
                    DataSecurityEntityType.entity_type == entity_data["entity_type"],  # fcg-rewrite
                    DataSecurityEntityType.source_type == "system_template",  # fcg-rewrite
                )
            ).first()  # fcg-rewrite
            if existing:  # fcg-rewrite
                continue  # fcg-rewrite

            service.create_entity_type(  # fcg-rewrite
                tenant_id=admin_tenant_id,  # fcg-rewrite
                entity_type=entity_data["entity_type"],  # fcg-rewrite
                entity_type_name=entity_data["entity_type_name"],  # fcg-rewrite
                risk_level=entity_data["risk_level"],  # fcg-rewrite
                pattern=entity_data["pattern"],  # fcg-rewrite
                anonymization_method=entity_data["anonymization_method"],  # fcg-rewrite
                anonymization_config=entity_data["anonymization_config"],  # fcg-rewrite
                check_input=entity_data["check_input"],  # fcg-rewrite
                check_output=entity_data["check_output"],  # fcg-rewrite
                is_global=True,  # fcg-rewrite
                source_type="system_template",  # fcg-rewrite
            )
            created_count += 1  # fcg-rewrite
            logger.info(f"Created system template entity type: {entity_data['entity_type']}")  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(  # fcg-rewrite
                f"Failed to create system template entity type {entity_data['entity_type']}: {exc}"  # fcg-rewrite
            )
    return created_count  # fcg-rewrite


def create_user_default_entity_types(db: Session, tenant_id: str) -> int:  # fcg-rewrite
    logger.info(f"Skipping entity type creation for tenant {tenant_id} - using global defaults")  # fcg-rewrite
    return 0  # fcg-rewrite
