import re
from typing import Dict


class StreamingRestoreBuffer:
    """
    Sliding window buffer for detecting and restoring placeholders in streaming output.
    Supports both old format [entity_type_N] and new format __entity_type_N__.
    """

    def __init__(self, mapping: Dict[str, str], max_placeholder_length: int = 50):
        self.mapping = mapping
        self.buffer = ""
        self.max_placeholder_length = max_placeholder_length
        self.placeholder_pattern = re.compile(r"(__[a-z_]+_\d+__|\[[a-zA-Z_]+_\d+\])")

    def process_chunk(self, chunk: str) -> str:
        self.buffer += chunk

        restored = self.buffer
        for placeholder, original in self.mapping.items():
            restored = restored.replace(placeholder, original)

        last_double_underscore = restored.rfind("__")
        last_bracket = restored.rfind("[")
        potential_start = max(last_double_underscore, last_bracket)

        if potential_start != -1:
            tail = restored[potential_start:]
            is_incomplete = False

            if last_double_underscore == potential_start:
                underscore_count = tail.count("__")
                if underscore_count % 2 == 1:
                    is_incomplete = True
            elif last_bracket == potential_start and "]" not in tail:
                is_incomplete = True

            if is_incomplete:
                if len(tail) <= self.max_placeholder_length:
                    output = restored[:potential_start]
                    self.buffer = tail
                    return output
                self.buffer = ""
                return restored

        self.buffer = ""
        return restored

    def flush(self) -> str:
        result = self.buffer
        for placeholder, original in self.mapping.items():
            result = result.replace(placeholder, original)
        self.buffer = ""
        return result

    def has_pending_content(self) -> bool:
        return len(self.buffer) > 0
