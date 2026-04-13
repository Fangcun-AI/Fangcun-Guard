"""
Hook context and result definitions for the plugin system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any


class HookPhase(str, Enum):
    INPUT = "input"                    # Proxy input (before upstream call)
    OUTPUT = "output"                  # Proxy output (after upstream response)
    DETECTION = "detection"            # Detection API (check_guardrails)
    STREAM_COMPLETE = "stream_complete" # Stream finished (accumulated content available)


@dataclass
class HookContext:
    """Context passed to plugin hooks"""
    phase: HookPhase
    request_id: str
    tenant_id: str
    application_id: Optional[str] = None
    messages: Optional[List[Dict]] = None           # Original messages
    content: str = ""                                # Current content for detection
    extra_body: Optional[Dict] = None                # Extra parameters from request
    tools: Optional[List[Dict]] = None               # Tool definitions (input phase)
    tool_calls: Optional[List[Dict]] = None          # Tool calls (output phase)
    reasoning_content: Optional[str] = None          # Reasoning trace (stream_complete)
    detection_direction: Optional[str] = None        # "input" or "output" (detection phase)
    existing_results: Dict[str, Any] = field(default_factory=dict)  # Results from prior plugins
    output_blocked: bool = False                     # Whether output was already blocked


@dataclass
class HookResult:
    """Result returned from a plugin hook"""
    plugin_name: str = ""
    risk_level: str = "no_risk"                      # no_risk | low_risk | medium_risk | high_risk
    categories: List[str] = field(default_factory=list)
    action: Optional[str] = None                     # None=no action | "block" | "warn" | "log"
    blocked_message: Optional[str] = None            # Replacement message when action=block
    metadata: Dict[str, Any] = field(default_factory=dict)  # Plugin-specific data (stored in logs)
