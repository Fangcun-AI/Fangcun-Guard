"""Format-aware content chunking for model-backed inspections."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
import json
import re
from typing import Any, Callable, Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class ContentSegment:
    content: str
    segment_index: int
    original_start: int
    original_end: int
    metadata: Dict[str, Any]


class SegmentationService:
    """Split large payloads while preserving a useful amount of structure."""

    DEFAULT_MAX_SEGMENT_SIZE = 4000
    DEFAULT_MIN_SEGMENT_SIZE = 100

    def __init__(self, max_segment_size: int = None, min_segment_size: int = None):
        self.max_segment_size = max_segment_size or self.DEFAULT_MAX_SEGMENT_SIZE
        self.min_segment_size = min_segment_size or self.DEFAULT_MIN_SEGMENT_SIZE
        if self.max_segment_size <= 0:
            raise ValueError("max_segment_size must be positive")
        if self.min_segment_size < 0:
            raise ValueError("min_segment_size cannot be negative")

    def segment_content(
        self,
        text: str,
        format_type: str,
        format_metadata: Dict[str, Any],
    ) -> List[ContentSegment]:
        if len(text) <= self.max_segment_size:
            return self._materialize([text], format_type)

        chunker = {
            "json": self._segment_json,
            "yaml": self._segment_yaml,
            "csv": self._segment_csv,
            "markdown": self._segment_markdown,
        }.get(format_type, self._segment_plain_text)
        chunks = chunker(text)
        return self._materialize(chunks, format_type)

    def _segment_json(self, text: str) -> List[str]:
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return self._segment_plain_text(text)

        if isinstance(value, list):
            units = list(value)
            return self._pack_structured_units(
                units,
                serializer=lambda items: json.dumps(items, ensure_ascii=False, indent=2),
            )
        if isinstance(value, dict):
            units = list(value.items())
            return self._pack_structured_units(
                units,
                serializer=lambda items: json.dumps(dict(items), ensure_ascii=False, indent=2),
            )
        return self._segment_plain_text(text)

    def _segment_yaml(self, text: str) -> List[str]:
        try:
            import yaml

            value = yaml.safe_load(text)
        except Exception:
            return self._segment_plain_text(text)

        if isinstance(value, list):
            return self._pack_structured_units(
                list(value),
                serializer=lambda items: yaml.safe_dump(
                    items,
                    allow_unicode=True,
                    sort_keys=False,
                ).strip(),
            )
        if isinstance(value, dict):
            return self._pack_structured_units(
                list(value.items()),
                serializer=lambda items: yaml.safe_dump(
                    dict(items),
                    allow_unicode=True,
                    sort_keys=False,
                ).strip(),
            )
        return self._segment_plain_text(text)

    def _segment_csv(self, text: str) -> List[str]:
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
            rows = list(csv.reader(StringIO(text), dialect))
        except csv.Error:
            return self._segment_plain_text(text)
        if len(rows) < 2:
            return self._segment_plain_text(text)

        header = rows[0]
        header_line = self._render_csv_rows([header], dialect).rstrip("\r\n")
        data_lines = [
            self._render_csv_rows([row], dialect).rstrip("\r\n")
            for row in rows[1:]
        ]
        return self._pack_text_units(
            data_lines,
            prefix=f"{header_line}\n",
            separator="\n",
            hard_wrap=False,
        )

    def _segment_markdown(self, text: str) -> List[str]:
        sections: List[str] = []
        current: List[str] = []
        for line in text.splitlines():
            if re.match(r"^#{1,6}\s+", line) and current:
                sections.append("\n".join(current).strip())
                current = []
            current.append(line)
        if current:
            sections.append("\n".join(current).strip())
        return self._pack_text_units(sections, separator="\n\n")

    def _segment_plain_text(self, text: str) -> List[str]:
        paragraphs = [paragraph for paragraph in re.split(r"\n\s*\n", text) if paragraph]
        if not paragraphs:
            paragraphs = [text]
        return self._pack_text_units(paragraphs, separator="\n\n")

    def _pack_structured_units(
        self,
        units: Sequence[Any],
        *,
        serializer: Callable[[Sequence[Any]], str],
    ) -> List[str]:
        batches: List[List[Any]] = []
        current_batch: List[Any] = []
        for unit in units:
            candidate = [*current_batch, unit]
            if current_batch and len(serializer(candidate)) > self.max_segment_size:
                batches.append(current_batch)
                current_batch = [unit]
            else:
                current_batch = candidate
        if current_batch:
            batches.append(current_batch)

        # A single structured unit may exceed the preferred budget. Preserve a
        # parseable payload in that case instead of slicing through syntax.
        return [serializer(batch) for batch in batches]

    def _pack_text_units(
        self,
        units: Iterable[str],
        *,
        prefix: str = "",
        separator: str,
        hard_wrap: bool = True,
    ) -> List[str]:
        chunks: List[str] = []
        current = prefix
        for unit in units:
            rendered_unit = str(unit)
            candidate = f"{current}{separator if current != prefix else ''}{rendered_unit}"
            if current != prefix and len(candidate) > self.max_segment_size:
                chunks.extend(self._hard_wrap(current) if hard_wrap else [current])
                current = f"{prefix}{rendered_unit}"
            else:
                current = candidate
        if current:
            chunks.extend(self._hard_wrap(current) if hard_wrap else [current])
        return chunks

    def _hard_wrap(self, text: str) -> List[str]:
        return [
            text[offset : offset + self.max_segment_size]
            for offset in range(0, len(text), self.max_segment_size)
        ] or [""]

    def _materialize(self, chunks: Sequence[str], format_type: str) -> List[ContentSegment]:
        segments: List[ContentSegment] = []
        cursor = 0
        for index, chunk in enumerate(chunks):
            segments.append(
                ContentSegment(
                    content=chunk,
                    segment_index=index,
                    original_start=cursor,
                    original_end=cursor + len(chunk),
                    metadata={"format": format_type},
                )
            )
            cursor += len(chunk)
        return segments

    @staticmethod
    def _render_csv_rows(rows: Sequence[Sequence[str]], dialect) -> str:
        stream = StringIO()
        writer = csv.writer(stream, dialect=dialect)
        writer.writerows(rows)
        return stream.getvalue()


segmentation_service = SegmentationService()
