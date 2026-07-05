"""Database-backed keyword checks for management and compatibility callers."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from database.models import Blacklist, Whitelist
from services.keyword_matching import normalize_keywords
from utils.logger import setup_logger


logger = setup_logger()
KeywordCheck = Tuple[bool, Optional[str], List[str]]
NO_KEYWORD_MATCH: KeywordCheck = (False, None, [])


class KeywordIndex:
    """Perform immediate keyword checks without the runtime cache."""

    def __init__(self, db: Session):
        self.db = db

    def check_blacklist(self, content: str) -> KeywordCheck:
        return self._check_active_lists(Blacklist, content)

    def check_whitelist(self, content: str) -> KeywordCheck:
        return self._check_active_lists(Whitelist, content)

    def _check_active_lists(self, model, content: str) -> KeywordCheck:
        try:
            records = self.db.query(model).filter_by(is_active=True).all()
        except Exception as exc:
            logger.error("Keyword list query failed for %s: %s", model.__name__, exc)
            return NO_KEYWORD_MATCH

        folded_content = content.casefold()
        for record in records:
            hits = [keyword for keyword in normalize_keywords(record.keywords) if keyword in folded_content]
            if hits:
                logger.info("%s hit: %s, keywords: %s", model.__name__, record.name, hits)
                return True, record.name, hits
        return NO_KEYWORD_MATCH

    def extract_sensitive_info(self, content: str) -> List[str]:
        findings: List[str] = []
        for label, pattern in SENSITIVE_VALUE_PATTERNS:
            findings.extend(f"{label}: {match.group(0)}" for match in pattern.finditer(content))
        return findings


SENSITIVE_VALUE_PATTERNS = (
    ("Phone number", re.compile(r"1[3-9]\d{9}")),
    ("ID number", re.compile(r"\d{17}[\dXx]|\d{15}")),
    ("Email address", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("IP address", re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")),
    ("Bank card number", re.compile(r"\b\d{16,19}\b")),
)
