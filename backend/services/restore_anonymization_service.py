"""Generate and execute restore-aware anonymization rules."""

import hashlib
import logging
import re
from typing import Any, Dict, Optional, Tuple

from services.general_llm_service import general_llm_service
from services.restore_code_executor import CodeExecutionError, RestoreCodeExecutor
from services.restore_streaming_buffer import StreamingRestoreBuffer  # compatibility export

logger = logging.getLogger(__name__)
_SAFE_IMPORTS = ("re", "string", "random", "hashlib", "time", "datetime", "base64", "uuid", "math")
_UNSAFE = (
    r"\bimport\s+", r"\bfrom\s+\w+\s+import", r"__\w+__", r"\beval\s*\(",
    r"\bexec\s*\(", r"\bcompile\s*\(", r"\bopen\s*\(", r"\bos\.", r"\bsys\.",
    r"\bsubprocess", r"\bsocket\.", r"\brequests\.", r"\bhttpx\.", r"\bgetattr\s*\(",
    r"\bsetattr\s*\(", r"\bdelattr\s*\(", r"\bglobals\s*\(", r"\blocals\s*\(",
    r"\bbreakpoint\s*\(", r"\.read\s*\(", r"\.write\s*\(", r"\bglobal\s+",
)


class CodeGenerationError(Exception):
    pass


class RestoreAnonymizationService:
    def __init__(self):
        self.general_llm = general_llm_service
        self.code_executor = RestoreCodeExecutor()

    async def _generate(self, prompt: str) -> str:
        messages = [
            {"role": "system", "content": "Return only a small Python anonymization routine. Do not include imports or markdown."},
            {"role": "user", "content": prompt},
        ]
        try:
            code = self._parse_code_response(await self.general_llm.chat(messages))
        except Exception as error:
            raise CodeGenerationError(f"Code generation failed: {error}") from error
        if not self._validate_code_safety(code):
            raise CodeGenerationError("Generated code contains unsafe operations")
        return code

    async def generate_restore_code(
        self,
        entity_type_code: str,
        entity_type_name: str,
        natural_description: str,
        sample_data: str = None,
    ) -> Dict[str, Any]:
        code = await self._generate(
            self._build_code_generation_prompt(entity_type_code, entity_type_name, natural_description, sample_data)
        )
        return {
            "code": code,
            "code_hash": hashlib.sha256(code.encode()).hexdigest(),
            "placeholder_format": f"[{entity_type_code.lower()}_N]",
        }

    async def generate_genai_anonymization_code(
        self, natural_description: str, sample_data: str = None
    ) -> Dict[str, Any]:
        return {"code": await self._generate(self._build_genai_code_prompt(natural_description, sample_data))}

    def execute_genai_code(self, code: str, text: str) -> str:
        self._require_safe(code)
        try:
            return self.code_executor.safe_execute_simple(code, text)
        except Exception as error:
            raise CodeExecutionError(f"Code execution failed: {error}") from error

    def execute_restore_anonymization(
        self,
        text: str,
        entity_type_code: str,
        restore_code: str,
        restore_code_hash: str,
        existing_mapping: Dict[str, str] = None,
        existing_counters: Dict[str, int] = None,
    ) -> Tuple[str, Dict[str, str], Dict[str, int]]:
        if hashlib.sha256(restore_code.encode()).hexdigest() != restore_code_hash:
            raise CodeExecutionError("Code integrity check failed - hash mismatch")
        self._require_safe(restore_code)
        result = self.code_executor.safe_execute(
            restore_code, text, entity_type_code, existing_mapping or {}, existing_counters or {}
        )
        return result["anonymized_text"], result["mapping"], result["counters"]

    def test_restore_anonymization(self, text: str, entity_type_code: str, restore_code: str) -> Dict[str, Any]:
        if not self._validate_code_safety(restore_code):
            return {"success": False, "error": "Code contains unsafe operations"}
        try:
            result = self.code_executor.safe_execute(restore_code, text, entity_type_code, {}, {})
            return {
                "success": True,
                "anonymized_text": result["anonymized_text"],
                "mapping": result["mapping"],
                "placeholder_count": len(result["mapping"]),
            }
        except Exception as error:
            return {"success": False, "error": str(error)}

    @staticmethod
    def restore_text(anonymized_text: str, mapping: Dict[str, str]) -> str:
        for placeholder, original in (mapping or {}).items():
            anonymized_text = anonymized_text.replace(placeholder, original)
        return anonymized_text

    @staticmethod
    def _build_genai_code_prompt(natural_description: str, sample_data: str = None) -> str:
        sample = f"\nSample input:\n{sample_data}" if sample_data else ""
        return (
            "Define anonymize(text) for this requirement:\n"
            f"{natural_description}{sample}\n"
            "Return a string. Handle empty input. Imports are forbidden; common utility modules are preloaded."
        )

    @staticmethod
    def _build_code_generation_prompt(
        entity_type_code: str, entity_type_name: str, natural_description: str, sample_data: str = None
    ) -> str:
        code = entity_type_code.lower()
        sample = f"\nSample: {sample_data}" if sample_data else ""
        return (
            f"Anonymize {entity_type_name} values in input_text. Requirement: {natural_description}.{sample}\n"
            f"Replace matches with [{code}_N], continuing existing_counters['{code}']. "
            "Store placeholder originals in result['mapping'], transformed text in result['anonymized_text'], "
            "and updated counters in result['counters']. Use re if needed. Imports, I/O, network calls, "
            "dunder access, and global state are forbidden."
        )

    @staticmethod
    def _parse_code_response(response: str) -> str:
        code = response.strip()
        if code.startswith("```"):
            code = code.split("\n", 1)[1] if "\n" in code else ""
        if code.endswith("```"):
            code = code[:-3]
        lines = []
        for line in code.strip().splitlines():
            statement = line.strip()
            if any(statement == f"import {module}" or statement.startswith(f"from {module} import") for module in _SAFE_IMPORTS):
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    @staticmethod
    def _validate_code_safety(code: str) -> bool:
        return not any(re.search(pattern, code, re.IGNORECASE) for pattern in _UNSAFE)

    def _require_safe(self, code: str) -> None:
        if not self._validate_code_safety(code):
            raise CodeExecutionError("Code contains unsafe operations")


_service_instance: Optional[RestoreAnonymizationService] = None


def get_restore_anonymization_service() -> RestoreAnonymizationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = RestoreAnonymizationService()
    return _service_instance
