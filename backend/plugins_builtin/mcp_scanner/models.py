"""
MCP Scanner data models.
"""

from enum import Enum
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class McpThreatCategory(str, Enum):
    """Threat categories for MCP server scanning"""
    # Tool poisoning
    TOOL_POISONING = "tool_poisoning"
    HIDDEN_INSTRUCTIONS = "hidden_instructions"
    DESCRIPTION_MANIPULATION = "description_manipulation"
    # Prompt injection
    PROMPT_INJECTION = "prompt_injection"
    CONTEXT_POLLUTION = "context_pollution"
    PARAMETER_INJECTION = "parameter_injection"
    # Data exfiltration
    DATA_EXFILTRATION = "data_exfiltration"
    SENSITIVE_DATA_EXPOSURE = "sensitive_data_exposure"
    CALLBACK_EXFILTRATION = "callback_exfiltration"
    # Resource threats
    MALICIOUS_URI = "malicious_uri"
    MIME_MISMATCH = "mime_mismatch"
    RESOURCE_INJECTION = "resource_injection"
    # Server instruction threats
    INSTRUCTION_INJECTION = "instruction_injection"
    BEHAVIOR_MANIPULATION = "behavior_manipulation"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    # Supply chain
    SUPPLY_CHAIN_RISK = "supply_chain_risk"
    KNOWN_VULNERABILITY = "known_vulnerability"
    # Obfuscation
    OBFUSCATION = "obfuscation"
    ENCODING_EVASION = "encoding_evasion"
    # Capability risks
    DANGEROUS_CAPABILITY = "dangerous_capability"
    CROSS_TOOL_ATTACK_CHAIN = "cross_tool_attack_chain"
    CAPABILITY_MISMATCH = "capability_mismatch"


class FindingSeverity(str, Enum):
    """Severity levels for findings"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class McpItemType(str, Enum):
    """Type of MCP item being scanned"""
    TOOL = "tool"
    PROMPT = "prompt"
    RESOURCE = "resource"
    INSTRUCTION = "instruction"


class McpFinding(BaseModel):
    """Individual security finding for an MCP server item"""
    server_name: str
    item_name: str
    item_type: str = McpItemType.TOOL
    engine: str
    category: str
    severity: str
    title: str
    description: str
    evidence: str = ""
    remediation: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    field_path: str = ""


class McpScannerResult(BaseModel):
    """Aggregated MCP scan result"""
    risk_level: str = "no_risk"
    categories: List[str] = []
    findings: List[McpFinding] = []
    servers_scanned: int = 0
    servers_flagged: int = 0
    tools_scanned: int = 0
    prompts_scanned: int = 0
    resources_scanned: int = 0
    max_severity: str = "info"
    scan_duration_ms: float = 0.0
    engine_summary: Dict[str, int] = {}


class McpScannerPolicyUpdate(BaseModel):
    """Policy update request"""
    enabled: bool = False
    # Engine toggles
    enable_yara_rules: bool = True
    enable_llm_semantic: bool = False
    enable_behavior_analysis: bool = True
    llm_auto_trigger_on_medium: bool = True
    # Scan scope toggles
    enable_tool_scan: bool = True
    enable_prompt_scan: bool = True
    enable_resource_scan: bool = True
    enable_instruction_scan: bool = True
    enable_supply_chain: bool = False
    # Policy mode
    policy_mode: str = Field('balanced', pattern='^(strict|balanced|permissive)$')
    # Per-severity actions
    critical_action: str = Field('block', pattern='^(block|warn|log)$')
    high_action: str = Field('warn', pattern='^(block|warn|log)$')
    medium_action: str = Field('log', pattern='^(block|warn|log)$')
    low_action: str = Field('log', pattern='^(block|warn|log)$')
    # Custom YARA rules (JSON array of rule strings)
    custom_yara_rules: List[str] = []
    # Trusted MCP servers (skip scanning)
    trusted_servers: List[str] = []


class McpScannerPolicyResponse(BaseModel):
    """Policy response"""
    id: str
    application_id: str
    enabled: bool
    enable_yara_rules: bool
    enable_llm_semantic: bool
    enable_behavior_analysis: bool
    llm_auto_trigger_on_medium: bool
    enable_tool_scan: bool
    enable_prompt_scan: bool
    enable_resource_scan: bool
    enable_instruction_scan: bool
    enable_supply_chain: bool
    policy_mode: str
    critical_action: str
    high_action: str
    medium_action: str
    low_action: str
    custom_yara_rules: List[str]
    trusted_servers: List[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class McpServerScanRequest(BaseModel):
    """Request for scanning MCP server data"""
    servers: List[Dict[str, Any]]
    policy_mode: Optional[str] = Field(None, pattern='^(strict|balanced|permissive)$')
    enable_llm: Optional[bool] = None


class McpServerScanResponse(BaseModel):
    """Response for MCP server scan"""
    request_id: str
    result: McpScannerResult
    scan_timestamp: datetime
