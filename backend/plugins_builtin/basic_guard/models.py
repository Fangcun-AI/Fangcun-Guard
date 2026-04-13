"""
Basic guard Pydantic models.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any
from datetime import datetime


class BasicGuardResult(BaseModel):
    """Basic guard streaming safety detection result"""
    risk_level: str = "no_risk"
    categories: List[str] = []
    details: List[Dict[str, Any]] = []
    content_length: int = 0
    reasoning_length: int = 0


class BasicGuardPolicyUpdate(BaseModel):
    enabled: bool = True
    enable_content_pattern_check: bool = True
    enable_reasoning_divergence_check: bool = True
    enable_output_anomaly_check: bool = True
    max_repetition_ratio: float = Field(0.4, ge=0.0, le=1.0, description="Max allowed ratio of repeated content")
    min_content_length: int = Field(10, ge=0, description="Minimum content length to trigger detection")
    violation_action: str = Field('warn', pattern='^(block|warn|log)$')
    # Prompt injection detection
    enable_prompt_injection_check: bool = True
    prompt_injection_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Score threshold for injection detection")
    prompt_injection_action: str = Field('block', pattern='^(block|warn|log)$')
    scan_user_messages: bool = True
    scan_system_messages: bool = True


class BasicGuardPolicyResponse(BaseModel):
    id: str
    application_id: str
    enabled: bool
    enable_content_pattern_check: bool
    enable_reasoning_divergence_check: bool
    enable_output_anomaly_check: bool
    max_repetition_ratio: float
    min_content_length: int
    violation_action: str
    # Prompt injection detection
    enable_prompt_injection_check: bool
    prompt_injection_threshold: float
    prompt_injection_action: str
    scan_user_messages: bool
    scan_system_messages: bool
    created_at: datetime
    updated_at: datetime
