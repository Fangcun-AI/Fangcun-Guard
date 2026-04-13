"""
Agent safety Pydantic models (moved from models/responses.py and routers/agent_safety_api.py)
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class AgentSafetyResult(BaseModel):
    """Agent safety detection result"""
    risk_level: str = "no_risk"
    categories: List[str] = []
    tool_call_count: int = 0
    blocked_tools: List[str] = []
    suspicious_arguments: List[Dict[str, Any]] = []
    definition_scan_findings: List[Dict[str, Any]] = []


class AgentSafetyPolicyUpdate(BaseModel):
    enabled: bool = False
    tool_whitelist: Optional[List[str]] = None
    tool_blacklist: List[str] = []
    max_tool_calls_per_request: int = Field(20, ge=0, le=1000)
    enable_argument_inspection: bool = True
    argument_patterns: List[str] = []
    enable_reasoning_safety: bool = False
    enable_tool_definition_scan: bool = True
    tool_violation_action: str = Field('block', pattern='^(block|warn|log)$')
    reasoning_violation_action: str = Field('warn', pattern='^(block|warn|log)$')
    tool_definition_scan_action: str = Field('warn', pattern='^(block|warn|log)$')


class AgentSafetyPolicyResponse(BaseModel):
    id: str
    application_id: str
    enabled: bool
    tool_whitelist: Optional[List[str]]
    tool_blacklist: List[str]
    max_tool_calls_per_request: int
    enable_argument_inspection: bool
    argument_patterns: List[str]
    enable_reasoning_safety: bool
    enable_tool_definition_scan: bool
    tool_violation_action: str
    reasoning_violation_action: str
    tool_definition_scan_action: str
    created_at: datetime
    updated_at: datetime
