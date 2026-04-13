from functools import lru_cache
import re
from typing import List, Optional, Pattern, Tuple

from config import settings


@lru_cache(maxsize=settings.scanner_regex_cache_size)
def get_compiled_regex(pattern: str) -> Optional[Pattern]:
    """
    Compile regex patterns with caching.

    Returns None for invalid patterns to avoid repeated compile attempts.
    """
    try:
        return re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error:
        return None


@lru_cache(maxsize=settings.scanner_keyword_cache_size)
def get_keyword_assets(definition: str) -> Tuple[List[str], Optional[Pattern]]:
    """
    Parse keyword definitions with caching.

    Returns:
        - keywords_lower: list of lowercase keywords
        - keyword_regex: compiled regex for large keyword sets, otherwise None
    """
    keywords = [k.strip() for k in definition.split(",") if k.strip()]
    if not keywords:
        return [], None

    keywords_lower = [k.lower() for k in keywords]

    if len(keywords) >= settings.scanner_keyword_regex_threshold:
        escaped = [re.escape(k) for k in keywords]
        try:
            keyword_regex = re.compile("|".join(escaped), re.IGNORECASE)
        except re.error:
            keyword_regex = None
        return keywords_lower, keyword_regex

    return keywords_lower, None
