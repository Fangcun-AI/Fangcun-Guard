import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from utils.logger import setup_logger

logger = setup_logger()

_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

QWEN3GUARD_CATEGORY_MAP = {
    "jailbreak": "S9",
    "prompt injection": "S9",
    "prompt attack": "S9",
    "violence": "S3",
    "violent crimes": "S3",
    "violent crime": "S3",
    "sexual content": "S7",
    "sexual": "S7",
    "pornography": "S7",
    "hate speech": "S8",
    "hate": "S8",
    "discrimination": "S8",
    "self-harm": "S16",
    "self harm": "S16",
    "suicide": "S16",
    "child safety": "S4",
    "harm to minors": "S4",
    "child abuse": "S4",
    "minors": "S4",
    "weapons": "S5",
    "wmd": "S5",
    "weapons of mass destruction": "S5",
    "politics": "S2",
    "political": "S2",
    "sensitive political": "S2",
    "non-violent crime": "S6",
    "fraud": "S6",
    "crime": "S6",
    "privacy": "S11",
    "personal information": "S11",
    "pii": "S11",
    "professional advice": "S19",
    "medical advice": "S19",
    "legal advice": "S19",
    "threats": "S18",
    "threat": "S18",
    "harassment": "S17",
    "bullying": "S17",
    "profanity": "S10",
    "offensive language": "S10",
    "sexual crimes": "S15",
    "intellectual property": "S13",
    "copyright": "S13",
    "commercial": "S12",
}


def drop_think_tags(text: str) -> str:
    visible = _THINK_TAG_RE.sub("", text)
    if "<think>" in visible:
        visible = visible.split("<think>", 1)[0]
    return visible.strip()


def _unsafe_tags(response: str) -> Tuple[str, ...]:
    lines = response.splitlines()
    if not lines or lines[0].strip() != "unsafe" or len(lines) < 2:
        return ()
    return tuple(
        dict.fromkeys(tag.strip() for tag in lines[1].split(",") if tag.strip())
    )


@dataclass(frozen=True)
class ParsedScannerVerdict:
    safe: bool
    matched_tags: Tuple[str, ...] = ()
    match_details: Optional[str] = None


class ScannerResponseParser:
    """Translate model protocol variants into stable scanner results."""

    def aggregate_window_results(self, scanners: List[Dict], window_results: List, result_cls):
        matches = {
            scanner["tag"]: {"windows": [], "sensitivity": None} for scanner in scanners
        }
        for result in window_results:
            if isinstance(result, Exception):
                logger.error(f"Window detection exception: {result}")
                continue
            window_index, model_response, sensitivity_score = result
            for tag in _unsafe_tags(drop_think_tags(model_response)):
                if tag not in matches:
                    continue
                matches[tag]["windows"].append(window_index)
                current = matches[tag]["sensitivity"]
                if sensitivity_score is not None and (
                    current is None or sensitivity_score > current
                ):
                    matches[tag]["sensitivity"] = sensitivity_score

        total_windows = len(window_results)
        results = []
        for scanner in scanners:
            info = matches[scanner["tag"]]
            details = None
            if info["windows"]:
                details = f"Matched in {len(info['windows'])}/{total_windows} windows"
                if info["sensitivity"] is not None:
                    details += f", max sensitivity: {info['sensitivity']:.4f}"
            results.append(self._result(scanner, result_cls, bool(info["windows"]), details))
        return results

    def parse_model_response(
        self,
        scanners: List[Dict],
        model_response: str,
        sensitivity_score: Optional[float],
        result_cls,
        response_format: Optional[str] = None,
    ) -> List:
        response = drop_think_tags(model_response)
        if response_format in ("llamaguard4", "wildguard"):
            return self.parse_generic_safe_unsafe(scanners, response, sensitivity_score, result_cls)

        qwen_verdict = self.try_parse_qwen3guard_format(response)
        if qwen_verdict is not None:
            safe, tags = qwen_verdict
            return self._results_for_tags(
                scanners, () if safe else tags, result_cls, sensitivity_score
            )
        if response == "safe":
            return self._results_for_tags(scanners, (), result_cls, sensitivity_score)
        if response.startswith("unsafe"):
            tags = _unsafe_tags(response)
            logger.info(f"Model returned matched tags: {tags}")
            return self._results_for_tags(scanners, tags, result_cls, sensitivity_score)

        logger.warning(f"Unexpected model response format: {response}")
        return self._results_for_tags(scanners, (), result_cls, sensitivity_score)

    def parse_generic_safe_unsafe(
        self,
        scanners: List[Dict],
        response: str,
        sensitivity_score: Optional[float],
        result_cls,
    ) -> List:
        normalized = response.casefold().strip()
        matched = not (normalized.startswith("safe") and not normalized.startswith("unsafe"))
        details = f"External model flagged unsafe. Response: {response[:200]}" if matched else None
        return [self._result(scanner, result_cls, matched, details) for scanner in scanners]

    def try_parse_qwen3guard_format(
        self, response: str
    ) -> Optional[Tuple[bool, List[str]]]:
        lines = [line.strip() for line in response.splitlines() if line.strip()]
        if not lines or not lines[0].casefold().startswith("safety:"):
            return None
        if lines[0].split(":", 1)[1].strip().casefold() in ("safe", "controversial"):
            return True, []

        tags = set()
        for line in lines[1:]:
            if not line.casefold().startswith("categories:"):
                continue
            categories = line.split(":", 1)[1].split(",")
            for category in categories:
                tags.add(self._qwen_category_tag(category.strip().casefold()))
        return False, sorted(tags)

    def _results_for_tags(
        self,
        scanners: List[Dict],
        tags: Iterable[str],
        result_cls,
        sensitivity_score: Optional[float],
    ) -> List:
        matched_tags = set(tags)
        details = f"Sensitivity: {sensitivity_score}"
        return [
            self._result(
                scanner,
                result_cls,
                scanner["tag"] in matched_tags,
                details if scanner["tag"] in matched_tags else None,
            )
            for scanner in scanners
        ]

    @staticmethod
    def _result(scanner: Dict, result_cls, matched: bool, details: Optional[str]):
        return result_cls(
            scanner_tag=scanner["tag"],
            scanner_name=scanner["name"],
            scanner_type="genai",
            risk_level=scanner["risk_level"],
            matched=matched,
            match_details=details,
        )

    @staticmethod
    def _qwen_category_tag(category: str) -> str:
        if category in QWEN3GUARD_CATEGORY_MAP:
            return QWEN3GUARD_CATEGORY_MAP[category]
        for known_category, tag in QWEN3GUARD_CATEGORY_MAP.items():
            if known_category in category or category in known_category:
                return tag
        logger.info(f"Unknown Qwen3Guard category '{category}', defaulting to S9")
        return "S9"
