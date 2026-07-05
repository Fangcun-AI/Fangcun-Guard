"""Structured-content profiling for data leakage inspection."""

from __future__ import annotations

import csv
from io import StringIO
import json
import re
from typing import Any, Dict, List, Optional, Tuple


FormatResult = Tuple[str, Dict[str, Any]]
MARKDOWN_HEADER = re.compile(r"^(#{1,6})\s+(.+)$")
MARKDOWN_MARKERS = (
    re.compile(r"```"),
    re.compile(r"\[[^\]]+\]\([^)]+\)"),
    re.compile(r"^\s*[-*+]\s+", re.MULTILINE),
    re.compile(r"^\s*\d+\.\s+", re.MULTILINE),
)


class FormatProbe:
    """Classify content and expose privacy-relevant structural metadata."""

    SENSITIVE_KEY_PATTERNS = frozenset(
        {
            "access_key",
            "account_number",
            "address",
            "api_key",
            "auth",
            "balance",
            "birthdate",
            "card_number",
            "credential",
            "cvv",
            "diagnosis",
            "driver_license",
            "email",
            "health",
            "id_card",
            "income",
            "insurance",
            "license",
            "medical",
            "mobile",
            "national_id",
            "passport",
            "password",
            "patient",
            "phone",
            "private_key",
            "routing_number",
            "salary",
            "secret",
            "social_security",
            "tax",
            "token",
        }
    )

    def detect_format(self, text: str) -> FormatResult:
        if not text or not text.strip():
            return "plain_text", {}

        stripped = text.strip()
        for format_name, profiler in (
            ("json", self._profile_json),
            ("yaml", self._profile_yaml),
            ("csv", self._profile_csv),
            ("markdown", self._profile_markdown),
        ):
            metadata = profiler(stripped)
            if metadata is not None:
                return format_name, metadata
        return "plain_text", {"line_count": len(stripped.splitlines())}

    def _profile_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            value = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None
        return self._profile_value(value, "json")

    def _profile_yaml(self, text: str) -> Optional[Dict[str, Any]]:
        if "\n" not in text and ":" not in text and "- " not in text:
            return None
        if any(MARKDOWN_HEADER.match(line.strip()) for line in text.splitlines()):
            return None
        try:
            import yaml

            value = yaml.safe_load(text)
        except Exception:
            return None

        # YAML accepts almost any scalar. Treat only structured values as YAML
        # so ordinary prose remains plain text.
        if not isinstance(value, (dict, list)):
            return None
        return self._profile_value(value, "yaml")

    def _profile_csv(self, text: str) -> Optional[Dict[str, Any]]:
        if "\n" not in text:
            return None
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
            rows = list(csv.reader(StringIO(text), dialect))
        except (csv.Error, UnicodeError):
            return None

        if len(rows) < 2 or len(rows[0]) < 2:
            return None
        column_count = len(rows[0])
        if any(len(row) != column_count for row in rows[1:]):
            return None

        sensitive_columns = [
            {"index": index, "name": header}
            for index, header in enumerate(rows[0])
            if self._is_potentially_sensitive_key(header)
        ]
        return {
            "type": "csv",
            "row_count": len(rows) - 1,
            "column_count": column_count,
            "headers": rows[0],
            "sensitive_columns": sensitive_columns,
            "has_sensitive_fields": bool(sensitive_columns),
        }

    def _profile_markdown(self, text: str) -> Optional[Dict[str, Any]]:
        headers = []
        for line_number, line in enumerate(text.splitlines()):
            match = MARKDOWN_HEADER.match(line.strip())
            if match:
                headers.append(
                    {
                        "level": len(match.group(1)),
                        "title": match.group(2).strip(),
                        "line": line_number,
                    }
                )

        if not headers and not any(marker.search(text) for marker in MARKDOWN_MARKERS):
            return None
        return {
            "type": "markdown",
            "header_count": len(headers),
            "headers": headers,
            "max_header_level": max((header["level"] for header in headers), default=0),
            "has_code_blocks": "```" in text,
        }

    def _profile_value(self, value: Any, format_name: str, path: str = "") -> Dict[str, Any]:
        if isinstance(value, dict):
            keys: Dict[str, Any] = {}
            sensitive_paths: List[str] = []
            for key, child_value in value.items():
                key_text = str(key)
                child_path = f"{path}.{key_text}" if path else key_text
                is_sensitive = self._is_potentially_sensitive_key(key_text)
                if is_sensitive:
                    sensitive_paths.append(child_path)

                if isinstance(child_value, (dict, list)):
                    nested = self._profile_value(child_value, format_name, child_path)
                    keys[key_text] = {
                        "is_sensitive": is_sensitive,
                        "type": "object" if isinstance(child_value, dict) else "array",
                        "nested": nested,
                    }
                    sensitive_paths.extend(nested.get("sensitive_paths", []))
                else:
                    keys[key_text] = {
                        "is_sensitive": is_sensitive,
                        "type": type(child_value).__name__,
                        "value_length": len(str(child_value)) if child_value is not None else 0,
                    }
            return {
                "type": format_name,
                "structure": "object",
                "key_count": len(keys),
                "keys": keys,
                "sensitive_paths": sensitive_paths,
                "has_sensitive_fields": bool(sensitive_paths),
            }

        if isinstance(value, list):
            if not value:
                return {
                    "type": format_name,
                    "structure": "array",
                    "element_count": 0,
                    "sensitive_paths": [],
                }
            first_value = value[0]
            nested = self._profile_value(first_value, format_name, path)
            return {
                "type": format_name,
                "structure": "array",
                "element_count": len(value),
                "element_type": type(first_value).__name__,
                "element_structure": nested if isinstance(first_value, (dict, list)) else None,
                "sensitive_paths": nested.get("sensitive_paths", []),
            }

        return {
            "type": format_name,
            "structure": "primitive",
            "value_type": type(value).__name__,
        }

    def _is_potentially_sensitive_key(self, key: str) -> bool:
        compact_key = self._compact_key(key)
        return any(self._compact_key(pattern) in compact_key for pattern in self.SENSITIVE_KEY_PATTERNS)

    def get_sensitive_field_paths(self, metadata: Dict[str, Any]) -> List[str]:
        return metadata.get("sensitive_paths", [])

    def should_focus_on_fields(self, metadata: Dict[str, Any]) -> bool:
        return bool(metadata.get("has_sensitive_fields", False))

    @staticmethod
    def _compact_key(key: str) -> str:
        return re.sub(r"[_\-\s]", "", key.casefold())


format_detection_service = FormatProbe()
