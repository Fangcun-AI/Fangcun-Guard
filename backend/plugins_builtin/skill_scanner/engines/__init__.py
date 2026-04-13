"""
Skill Scanner detection engines.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class ScanEngine(ABC):
    """Base class for all skill scanner engines"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine identifier"""
        ...

    @abstractmethod
    async def scan(self, tools: List[Dict[str, Any]], policy) -> List:
        """Scan tool definitions and return findings"""
        ...
