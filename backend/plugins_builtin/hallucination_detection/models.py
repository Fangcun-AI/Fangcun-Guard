"""
Hallucination detection Pydantic models (moved from models/responses.py and routers/agent_safety_api.py)
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class HallucinationResult(BaseModel):
    """Hallucination detection result"""
    risk_level: str = "no_risk"
    categories: List[str] = []
    groundedness_score: Optional[float] = None
    consistency_score: Optional[float] = None
    flagged_claims: List[str] = []


class HallucinationPolicyUpdate(BaseModel):
    enabled: bool = False
    enable_groundedness: bool = True
    enable_consistency: bool = True
    groundedness_threshold: float = Field(0.7, ge=0.0, le=1.0)
    consistency_threshold: float = Field(0.7, ge=0.0, le=1.0)
    source_context_field: str = Field('system_message', pattern='^(system_message|extra_body\\.context|extra_body\\.documents)$')
    violation_action: str = Field('flag', pattern='^(block|flag|warn|log)$')


class HallucinationPolicyResponse(BaseModel):
    id: str
    application_id: str
    enabled: bool
    enable_groundedness: bool
    enable_consistency: bool
    groundedness_threshold: float
    consistency_threshold: float
    source_context_field: str
    violation_action: str
    created_at: datetime
    updated_at: datetime
