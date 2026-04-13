"""
Skill Scanner data models.
"""

from enum import Enum
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ThreatCategory(str, Enum):
    """Threat categories for skill/tool definition scanning"""
    # Prompt injection
    PROMPT_INJECTION = "prompt_injection"
    DESCRIPTION_MANIPULATION = "description_manipulation"
    # Command/code execution
    COMMAND_INJECTION = "command_injection"
    CODE_EXECUTION = "code_execution"
    # Data exfiltration
    DATA_EXFILTRATION = "data_exfiltration"
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"
    # Obfuscation
    OBFUSCATION = "obfuscation"
    HIDDEN_FUNCTIONALITY = "hidden_functionality"
    # Structural issues
    OVERLY_PERMISSIVE = "overly_permissive"
    MISSING_VALIDATION = "missing_validation"
    POOR_DESCRIPTION = "poor_description"
    # Dangerous capabilities
    FILESYSTEM_ACCESS = "filesystem_access"
    NETWORK_ACCESS = "network_access"
    DANGEROUS_COMBINATION = "dangerous_combination"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    # Meta
    EXCESSIVE_SCOPE = "excessive_scope"
    SCHEMA_VIOLATION = "schema_violation"


class FindingSeverity(str, Enum):
    """Severity levels for findings"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Finding(BaseModel):
    """Individual security finding for a tool definition"""
    tool_name: str
    engine: str
    category: str
    severity: str
    title: str
    description: str
    evidence: str = ""
    remediation: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    field_path: str = ""


class SkillScannerResult(BaseModel):
    """Aggregated scan result"""
    risk_level: str = "no_risk"
    categories: List[str] = []
    findings: List[Finding] = []
    tools_scanned: int = 0
    tools_flagged: int = 0
    max_severity: str = "info"
    scan_duration_ms: float = 0.0
    phase1_findings: int = 0
    phase2_findings: int = 0
    engine_summary: Dict[str, int] = {}


class SkillScannerPolicyUpdate(BaseModel):
    """Policy update request"""
    enabled: bool = False
    enable_static_pattern: bool = True
    enable_structural_validation: bool = True
    enable_capability_risk: bool = True
    enable_llm_semantic: bool = False
    llm_auto_trigger_on_medium: bool = True
    policy_mode: str = Field('balanced', pattern='^(strict|balanced|permissive)$')
    critical_action: str = Field('block', pattern='^(block|warn|log)$')
    high_action: str = Field('warn', pattern='^(block|warn|log)$')
    medium_action: str = Field('log', pattern='^(block|warn|log)$')
    low_action: str = Field('log', pattern='^(block|warn|log)$')
    custom_patterns: List[str] = []
    dangerous_capability_keywords: List[str] = []


class SkillScannerPolicyResponse(BaseModel):
    """Policy response"""
    id: str
    application_id: str
    enabled: bool
    enable_static_pattern: bool
    enable_structural_validation: bool
    enable_capability_risk: bool
    enable_llm_semantic: bool
    llm_auto_trigger_on_medium: bool
    policy_mode: str
    critical_action: str
    high_action: str
    medium_action: str
    low_action: str
    custom_patterns: List[str]
    dangerous_capability_keywords: List[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


