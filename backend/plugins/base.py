"""
Plugin base classes for FangcunGuard plugin system.
All plugins must inherit from FangcunPlugin or DetectionPlugin.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any, Dict
from pathlib import Path


class PluginType(str, Enum):
    DETECTION = "detection"
    INTEGRATION = "integration"
    UTILITY = "utility"


class DeploymentMode(str, Enum):
    BLACK_BOX = "black_box"      # Detection API (5001) only
    WHITE_BOX = "white_box"      # Proxy gateway (5002) required
    BOTH = "both"                # Supports both modes


@dataclass
class PluginMetadata:
    """Plugin metadata descriptor"""
    name: str
    version: str
    description: str
    author: str = "FangcunGuard"
    plugin_type: PluginType = PluginType.DETECTION
    deployment_mode: DeploymentMode = DeploymentMode.BOTH
    priority: int = 100  # Lower number = higher priority
    # Display fields for Tool Center UI
    display_name: str = ""           # Human-friendly name (e.g. "Agent 安全防护")
    display_name_en: str = ""        # English display name
    icon: str = "shield"             # Lucide icon name
    category: str = "security"       # Category: security / analysis / integration / utility
    tags: List[str] = field(default_factory=list)  # Feature tags
    documentation: str = ""          # Markdown documentation


class FangcunPlugin(ABC):
    """Base class for all FangcunGuard plugins"""

    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        ...

    async def initialize(self, app_context: Dict[str, Any]) -> None:
        """Initialize plugin (called once at startup)"""
        pass

    async def shutdown(self) -> None:
        """Shutdown plugin (called once at teardown)"""
        pass

    def get_routers(self) -> list:
        """Return FastAPI APIRouter instances to register"""
        return []

    def get_migrations_dir(self) -> Optional[Path]:
        """Return path to plugin's SQL migrations directory"""
        return None


class DetectionPlugin(FangcunPlugin):
    """Base class for detection plugins that hook into the detection pipeline"""

    async def on_input_check(self, ctx: Any) -> Optional[Any]:
        """Hook: Proxy input phase (before upstream call).
        White-box only: has access to tools, messages, etc.
        """
        return None

    async def on_output_check(self, ctx: Any) -> Optional[Any]:
        """Hook: Proxy output phase (after upstream response).
        White-box only: has access to tool_calls, response content, etc.
        """
        return None

    async def on_detection_check(self, ctx: Any) -> Optional[Any]:
        """Hook: Detection API phase (check_guardrails).
        Black-box: works via Detection API (5001).
        """
        return None

    async def on_stream_complete(self, ctx: Any) -> Optional[Any]:
        """Hook: Stream complete phase (after streaming ends).
        White-box only: has access to accumulated reasoning/tool_calls.
        """
        return None
