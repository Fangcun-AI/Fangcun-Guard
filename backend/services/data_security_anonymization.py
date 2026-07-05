import asyncio  # fcg-rewrite
import concurrent.futures  # fcg-rewrite
import hashlib  # fcg-rewrite
import random  # fcg-rewrite
import re  # fcg-rewrite
import string  # fcg-rewrite
from typing import Any, Dict, List, Tuple  # fcg-rewrite


RISK_LEVEL_MAPPING = {  # fcg-rewrite
    "low": "low_risk",  # fcg-rewrite
    "medium": "medium_risk",  # fcg-rewrite
    "high": "high_risk",  # fcg-rewrite
}


def translate_replacement_template(template: str) -> str:  # fcg-rewrite
    """Normalize legacy $1 syntax to Python regex \\1 replacement syntax."""
    if re.search(r"\\[1-9]", template):  # fcg-rewrite
        return template  # fcg-rewrite

    result = template  # fcg-rewrite
    for index in range(9, 0, -1):  # fcg-rewrite
        result = result.replace(f"${index}", f"\\{index}")  # fcg-rewrite
    return result  # fcg-rewrite


class DataSecurityAnonymizer:  # fcg-rewrite
    """Detection and anonymization helpers for privacy-sensitive content."""

    def __init__(self, general_llm, logger):  # fcg-rewrite
        self.general_llm = general_llm  # fcg-rewrite
        self.logger = logger  # fcg-rewrite

    def match_pattern(self, text: str, entity_type: Dict[str, Any]) -> List[Dict[str, Any]]:  # fcg-rewrite
        matches: List[Dict[str, Any]] = []  # fcg-rewrite
        pattern = entity_type.get("pattern", "")  # fcg-rewrite
        if not pattern:  # fcg-rewrite
            return matches  # fcg-rewrite

        try:
            if "\\\\" in pattern:  # fcg-rewrite
                pattern = pattern.replace("\\\\", "\\")  # fcg-rewrite

            regex = re.compile(pattern)  # fcg-rewrite
            for match in regex.finditer(text):  # fcg-rewrite
                matches.append(  # fcg-rewrite
                    {
                        "entity_type": entity_type["entity_type"],  # fcg-rewrite
                        "entity_type_name": entity_type["entity_type_name"],  # fcg-rewrite
                        "start": match.start(),  # fcg-rewrite
                        "end": match.end(),  # fcg-rewrite
                        "text": match.group(),  # fcg-rewrite
                        "risk_level": entity_type["risk_level"],  # fcg-rewrite
                        "anonymization_method": entity_type["anonymization_method"],  # fcg-rewrite
                        "anonymization_config": entity_type["anonymization_config"],  # fcg-rewrite
                        "restore_code": entity_type.get("restore_code"),  # fcg-rewrite
                        "restore_code_hash": entity_type.get("restore_code_hash"),  # fcg-rewrite
                    }
                )
        except re.error as exc:  # fcg-rewrite
            self.logger.error(f"Invalid regex pattern for {entity_type['entity_type']}: {exc}")  # fcg-rewrite

        return matches  # fcg-rewrite

    def anonymize_text(  # fcg-rewrite
        self,
        text: str,  # fcg-rewrite
        detected_entities: List[Dict[str, Any]],  # fcg-rewrite
        entity_types: List[Dict[str, Any]],  # fcg-rewrite
    ) -> str:  # fcg-rewrite
        if not detected_entities:  # fcg-rewrite
            return text  # fcg-rewrite

        sorted_entities = sorted(  # fcg-rewrite
            self._filter_overlapping_entities(detected_entities),  # fcg-rewrite
            key=lambda item: (item["start"], len(item["text"])),  # fcg-rewrite
            reverse=True,  # fcg-rewrite
        )

        anonymized_text = text  # fcg-rewrite
        for entity in sorted_entities:  # fcg-rewrite
            replacement = self._build_replacement(entity)  # fcg-rewrite
            entity["anonymized_value"] = replacement  # fcg-rewrite
            anonymized_text = (  # fcg-rewrite
                anonymized_text[: entity["start"]]  # fcg-rewrite
                + replacement  # fcg-rewrite
                + anonymized_text[entity["end"] :]  # fcg-rewrite
            )
        return anonymized_text  # fcg-rewrite

    def anonymize_text_unified(  # fcg-rewrite
        self,
        text: str,  # fcg-rewrite
        detected_entities: List[Dict[str, Any]],  # fcg-rewrite
        entity_types: List[Dict[str, Any]],  # fcg-rewrite
    ) -> Tuple[str, Dict[str, str]]:  # fcg-rewrite
        if not detected_entities:  # fcg-rewrite
            return text, {}  # fcg-rewrite

        sorted_entities = sorted(  # fcg-rewrite
            self._filter_overlapping_entities(detected_entities),  # fcg-rewrite
            key=lambda item: (item["start"], len(item["text"])),  # fcg-rewrite
            reverse=True,  # fcg-rewrite
        )

        anonymized_text = text  # fcg-rewrite
        restore_mapping: Dict[str, str] = {}  # fcg-rewrite
        for entity in sorted_entities:  # fcg-rewrite
            replacement = self._build_replacement(entity)  # fcg-rewrite
            entity["anonymized_value"] = replacement  # fcg-rewrite
            anonymized_text = (  # fcg-rewrite
                anonymized_text[: entity["start"]]  # fcg-rewrite
                + replacement  # fcg-rewrite
                + anonymized_text[entity["end"] :]  # fcg-rewrite
            )

        return anonymized_text, restore_mapping  # fcg-rewrite

    def anonymize_text_with_restore(  # fcg-rewrite
        self,
        text: str,  # fcg-rewrite
        detected_entities: List[Dict[str, Any]],  # fcg-rewrite
        entity_type_configs: Dict[str, Any],  # fcg-rewrite
        existing_mapping: Dict[str, str] = None,  # fcg-rewrite
        existing_counters: Dict[str, int] = None,  # fcg-rewrite
    ) -> Tuple[str, Dict[str, str], Dict[str, int]]:  # fcg-rewrite
        from services.restore_anonymization_service import get_restore_anonymization_service  # fcg-rewrite

        if not detected_entities:  # fcg-rewrite
            return text, existing_mapping or {}, existing_counters or {}  # fcg-rewrite

        mapping = dict(existing_mapping) if existing_mapping else {}  # fcg-rewrite
        counters = dict(existing_counters) if existing_counters else {}  # fcg-rewrite
        restore_service = get_restore_anonymization_service()  # fcg-rewrite

        restore_entities = []  # fcg-rewrite
        normal_entities = []  # fcg-rewrite
        for entity in detected_entities:  # fcg-rewrite
            entity_type_code = entity.get("entity_type", "")  # fcg-rewrite
            config = entity_type_configs.get(entity_type_code, {})  # fcg-rewrite
            if (
                config.get("anonymization_method") != "genai_code"  # fcg-rewrite
                and config.get("restore_code")  # fcg-rewrite
                and config.get("restore_code_hash")  # fcg-rewrite
            ):
                restore_entities.append((entity, config))  # fcg-rewrite
            else:
                normal_entities.append(entity)  # fcg-rewrite

        anonymized_text = text  # fcg-rewrite
        processed_positions = set()  # fcg-rewrite

        for entity, config in sorted(  # fcg-rewrite
            restore_entities, key=lambda item: item[0]["start"], reverse=True  # fcg-rewrite
        ):
            start, end = entity["start"], entity["end"]  # fcg-rewrite
            if (start, end) in processed_positions:  # fcg-rewrite
                continue  # fcg-rewrite

            original_text = entity["text"]  # fcg-rewrite
            entity_type_code = entity["entity_type"]  # fcg-rewrite
            try:
                result_text, new_mapping, new_counters = restore_service.execute_restore_anonymization(  # fcg-rewrite
                    original_text,  # fcg-rewrite
                    entity_type_code,  # fcg-rewrite
                    config["restore_code"],  # fcg-rewrite
                    config["restore_code_hash"],  # fcg-rewrite
                    mapping,  # fcg-rewrite
                    counters,  # fcg-rewrite
                )
                mapping.update(new_mapping)  # fcg-rewrite
                counters.update(new_counters)  # fcg-rewrite
                anonymized_text = anonymized_text[:start] + result_text + anonymized_text[end:]  # fcg-rewrite
                processed_positions.add((start, end))  # fcg-rewrite
            except Exception as exc:  # fcg-rewrite
                self.logger.error(f"Restore anonymization failed for {entity_type_code}: {exc}")  # fcg-rewrite
                counter_key = entity_type_code.lower()  # fcg-rewrite
                counter = counters.get(counter_key, 0) + 1  # fcg-rewrite
                counters[counter_key] = counter  # fcg-rewrite
                placeholder = f"[{counter_key}_{counter}]"  # fcg-rewrite
                mapping[placeholder] = original_text  # fcg-rewrite
                anonymized_text = anonymized_text[:start] + placeholder + anonymized_text[end:]  # fcg-rewrite
                processed_positions.add((start, end))  # fcg-rewrite

        for entity in sorted(normal_entities, key=lambda item: item["start"], reverse=True):  # fcg-rewrite
            start, end = entity["start"], entity["end"]  # fcg-rewrite
            if (start, end) in processed_positions:  # fcg-rewrite
                continue  # fcg-rewrite

            entity_type_code = entity["entity_type"]  # fcg-rewrite
            counter_key = entity_type_code.lower()  # fcg-rewrite
            counter = counters.get(counter_key, 0) + 1  # fcg-rewrite
            counters[counter_key] = counter  # fcg-rewrite
            placeholder = f"[{counter_key}_{counter}]"  # fcg-rewrite
            mapping[placeholder] = entity["text"]  # fcg-rewrite
            anonymized_text = anonymized_text[:start] + placeholder + anonymized_text[end:]  # fcg-rewrite
            processed_positions.add((start, end))  # fcg-rewrite

        return anonymized_text, mapping, counters  # fcg-rewrite

    def test_anonymization(self, method: str, config: dict, test_input: str) -> dict:  # fcg-rewrite
        import time  # fcg-rewrite

        start_time = time.time()  # fcg-rewrite
        try:
            entity = {  # fcg-rewrite
                "entity_type": "TEST_ENTITY",  # fcg-rewrite
                "entity_type_name": "TEST_ENTITY",  # fcg-rewrite
                "text": test_input,  # fcg-rewrite
                "anonymization_method": method,  # fcg-rewrite
                "anonymization_config": config,  # fcg-rewrite
                "restore_code": config.get("genai_code", ""),  # fcg-rewrite
            }
            result = self._build_replacement(entity)  # fcg-rewrite
            processing_time_ms = (time.time() - start_time) * 1000  # fcg-rewrite
            return {  # fcg-rewrite
                "success": True,  # fcg-rewrite
                "result": result,  # fcg-rewrite
                "processing_time_ms": round(processing_time_ms, 2),  # fcg-rewrite
            }
        except Exception as exc:  # fcg-rewrite
            self.logger.error(f"Test anonymization failed: {exc}")  # fcg-rewrite
            return {  # fcg-rewrite
                "success": False,  # fcg-rewrite
                "result": f"Error: {str(exc)}",  # fcg-rewrite
                "processing_time_ms": (time.time() - start_time) * 1000,  # fcg-rewrite
            }

    def compare_risk_level(self, level1: str, level2: str) -> int:  # fcg-rewrite
        risk_order = {  # fcg-rewrite
            "no_risk": 0,  # fcg-rewrite
            "low": 1,  # fcg-rewrite
            "low_risk": 1,  # fcg-rewrite
            "medium": 2,  # fcg-rewrite
            "medium_risk": 2,  # fcg-rewrite
            "high": 3,  # fcg-rewrite
            "high_risk": 3,  # fcg-rewrite
        }
        score1 = risk_order.get(level1, 0)  # fcg-rewrite
        score2 = risk_order.get(level2, 0)  # fcg-rewrite
        if score1 > score2:  # fcg-rewrite
            return 1  # fcg-rewrite
        if score1 < score2:  # fcg-rewrite
            return -1  # fcg-rewrite
        return 0  # fcg-rewrite

    def _filter_overlapping_entities(  # fcg-rewrite
        self, detected_entities: List[Dict[str, Any]]  # fcg-rewrite
    ) -> List[Dict[str, Any]]:  # fcg-rewrite
        filtered_entities = []  # fcg-rewrite
        for index, entity1 in enumerate(detected_entities):  # fcg-rewrite
            is_contained = False  # fcg-rewrite
            for compare_index, entity2 in enumerate(detected_entities):  # fcg-rewrite
                if index == compare_index:  # fcg-rewrite
                    continue  # fcg-rewrite
                if (
                    entity1["start"] >= entity2["start"]  # fcg-rewrite
                    and entity1["end"] <= entity2["end"]  # fcg-rewrite
                    and len(entity1["text"]) < len(entity2["text"])  # fcg-rewrite
                ):
                    is_contained = True  # fcg-rewrite
                    break
                if (
                    entity1["start"] == entity2["start"]  # fcg-rewrite
                    and entity1["end"] == entity2["end"]  # fcg-rewrite
                    and entity1.get("anonymization_method") == "mask"  # fcg-rewrite
                    and entity2.get("anonymization_method") == "replace"  # fcg-rewrite
                ):
                    continue  # fcg-rewrite
                if (
                    entity1["start"] == entity2["start"]  # fcg-rewrite
                    and entity1["end"] == entity2["end"]  # fcg-rewrite
                    and entity1.get("anonymization_method") == "replace"  # fcg-rewrite
                    and entity2.get("anonymization_method") == "mask"  # fcg-rewrite
                ):
                    is_contained = True  # fcg-rewrite
                    break
                if (
                    entity1["start"] == entity2["start"]  # fcg-rewrite
                    and entity1["end"] == entity2["end"]  # fcg-rewrite
                    and index > compare_index  # fcg-rewrite
                ):
                    is_contained = True  # fcg-rewrite
                    break
            if not is_contained:  # fcg-rewrite
                filtered_entities.append(entity1)  # fcg-rewrite
        return filtered_entities  # fcg-rewrite

    def _build_replacement(self, entity: Dict[str, Any]) -> str:  # fcg-rewrite
        method = entity.get("anonymization_method", "replace")  # fcg-rewrite
        config = entity.get("anonymization_config", {})  # fcg-rewrite
        original_text = entity["text"]  # fcg-rewrite
        entity_type_code = entity["entity_type"]  # fcg-rewrite

        if method == "regex_replace":  # fcg-rewrite
            pattern = config.get("regex_pattern", "")  # fcg-rewrite
            replacement_template = config.get("replacement_template", "***")  # fcg-rewrite
            try:
                if pattern:  # fcg-rewrite
                    python_replacement = translate_replacement_template(replacement_template)  # fcg-rewrite
                    return re.sub(pattern, python_replacement, original_text)  # fcg-rewrite
                return "***"  # fcg-rewrite
            except re.error as exc:  # fcg-rewrite
                self.logger.warning(f"Regex replace error for {entity_type_code}: {exc}")  # fcg-rewrite
                return f"<{entity_type_code}>"  # fcg-rewrite

        if method in ("genai", "genai_natural"):  # fcg-rewrite
            anonymization_prompt = config.get("anonymization_prompt", "")  # fcg-rewrite
            if anonymization_prompt:  # fcg-rewrite
                return self._genai_anonymize_sync(  # fcg-rewrite
                    original_text,  # fcg-rewrite
                    anonymization_prompt,  # fcg-rewrite
                    entity.get("entity_type_name", entity_type_code),  # fcg-rewrite
                )
            return f"[REDACTED_{entity.get('entity_type_name', entity_type_code).upper().replace(' ', '_')}]"  # fcg-rewrite

        if method == "genai_code":  # fcg-rewrite
            restore_code = entity.get("restore_code")  # fcg-rewrite
            if restore_code:  # fcg-rewrite
                from services.restore_anonymization_service import (  # fcg-rewrite
                    get_restore_anonymization_service,  # fcg-rewrite
                )

                restore_service = get_restore_anonymization_service()  # fcg-rewrite
                try:
                    return restore_service.execute_genai_code(restore_code, original_text)  # fcg-rewrite
                except Exception as exc:  # fcg-rewrite
                    self.logger.error(  # fcg-rewrite
                        f"GenAI code execution failed for {entity_type_code}: {exc}"  # fcg-rewrite
                    )
            return f"<{entity_type_code}>"  # fcg-rewrite

        if method == "replace":  # fcg-rewrite
            return config.get("replacement", f"<{entity_type_code}>")  # fcg-rewrite
        if method == "mask":  # fcg-rewrite
            return self._mask_string(  # fcg-rewrite
                original_text,  # fcg-rewrite
                config.get("mask_char", "*"),  # fcg-rewrite
                config.get("keep_prefix", 0),  # fcg-rewrite
                config.get("keep_suffix", 0),  # fcg-rewrite
            )
        if method == "hash":  # fcg-rewrite
            return self._hash_string(original_text)  # fcg-rewrite
        if method == "encrypt":  # fcg-rewrite
            return f"<ENCRYPTED_{hashlib.md5(original_text.encode()).hexdigest()[:8]}>"  # fcg-rewrite
        if method == "shuffle":  # fcg-rewrite
            return self._shuffle_string(original_text)  # fcg-rewrite
        if method == "random":  # fcg-rewrite
            return self._random_replacement(original_text)  # fcg-rewrite
        return f"<{entity_type_code}>"  # fcg-rewrite

    def _mask_string(  # fcg-rewrite
        self, text: str, mask_char: str = "*", keep_prefix: int = 0, keep_suffix: int = 0  # fcg-rewrite
    ) -> str:  # fcg-rewrite
        if len(text) <= keep_prefix + keep_suffix:  # fcg-rewrite
            return text  # fcg-rewrite
        prefix = text[:keep_prefix] if keep_prefix > 0 else ""  # fcg-rewrite
        suffix = text[-keep_suffix:] if keep_suffix > 0 else ""  # fcg-rewrite
        middle_length = len(text) - keep_prefix - keep_suffix  # fcg-rewrite
        return prefix + mask_char * middle_length + suffix  # fcg-rewrite

    def _hash_string(self, text: str) -> str:  # fcg-rewrite
        return hashlib.sha256(text.encode()).hexdigest()[:16]  # fcg-rewrite

    def _shuffle_string(self, text: str) -> str:  # fcg-rewrite
        chars = list(text)  # fcg-rewrite
        random.shuffle(chars)  # fcg-rewrite
        return "".join(chars)  # fcg-rewrite

    def _random_replacement(self, text: str) -> str:  # fcg-rewrite
        replacement = ""  # fcg-rewrite
        for char in text:  # fcg-rewrite
            if char.isdigit():  # fcg-rewrite
                replacement += random.choice(string.digits)  # fcg-rewrite
            elif char.isalpha():  # fcg-rewrite
                replacement += random.choice(  # fcg-rewrite
                    string.ascii_uppercase if char.isupper() else string.ascii_lowercase  # fcg-rewrite
                )
            else:
                replacement += char  # fcg-rewrite
        return replacement  # fcg-rewrite

    def _genai_anonymize_sync(self, text: str, prompt: str, entity_type_name: str) -> str:  # fcg-rewrite
        try:
            messages = [  # fcg-rewrite
                {
                    "role": "system",  # fcg-rewrite
                    "content": "You are a data anonymization assistant. Your task is to anonymize sensitive data according to the given instruction. Return ONLY the anonymized result, nothing else. Do not include any explanation or prefix.",  # fcg-rewrite
                },
                {
                    "role": "user",  # fcg-rewrite
                    "content": f"Original sensitive data: {text}\nAnonymization instruction: {prompt}\n\nReturn the anonymized result only:",  # fcg-rewrite
                },
            ]

            try:
                loop = asyncio.get_event_loop()  # fcg-rewrite
                if loop.is_running():  # fcg-rewrite
                    with concurrent.futures.ThreadPoolExecutor() as executor:  # fcg-rewrite
                        future = executor.submit(asyncio.run, self.general_llm.chat(messages))  # fcg-rewrite
                        result = future.result(timeout=30)  # fcg-rewrite
                else:
                    result = loop.run_until_complete(self.general_llm.chat(messages))  # fcg-rewrite
            except RuntimeError:  # fcg-rewrite
                result = asyncio.run(self.general_llm.chat(messages))  # fcg-rewrite

            if result:  # fcg-rewrite
                cleaned_result = result.strip().strip("\"'")  # fcg-rewrite
                if cleaned_result:  # fcg-rewrite
                    return cleaned_result  # fcg-rewrite

            return f"[REDACTED_{entity_type_name.upper().replace(' ', '_')}]"  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            self.logger.error(f"GenAI anonymization failed for {entity_type_name}: {exc}")  # fcg-rewrite
            return f"[REDACTED_{entity_type_name.upper().replace(' ', '_')}]"  # fcg-rewrite
