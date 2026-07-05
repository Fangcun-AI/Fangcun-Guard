"""
MCP Scanner detection engines.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class McpScanner(ABC):
    """Base class for all MCP scanner engines"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine identifier"""
        ...

    @abstractmethod
    async def scan(self, items: List[Dict[str, Any]], policy) -> List:
        """Scan MCP items and return findings"""
        ...
