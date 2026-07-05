"""Typed API response payloads."""

from datetime import datetime  # fcg-rewrite
from typing import Any, Dict, List, Optional  # fcg-rewrite

from pydantic import BaseModel, ConfigDict, Field  # fcg-rewrite


def list_field():  # fcg-rewrite
    return Field(default_factory=list)  # fcg-rewrite


class RiskCategories(BaseModel):  # fcg-rewrite
    risk_level: str  # fcg-rewrite
    categories: List[str]  # fcg-rewrite


class ComplianceResult(RiskCategories):  # fcg-rewrite
    pass


class SecurityResult(RiskCategories):  # fcg-rewrite
    pass


class DataSecurityResult(RiskCategories):  # fcg-rewrite
    detected_entities: List[Dict[str, Any]] = list_field()  # fcg-rewrite
    anonymized_text: Optional[str] = None  # fcg-rewrite
    restore_mapping: Optional[Dict[str, str]] = None  # fcg-rewrite


class AgentSafetyResult(BaseModel):  # fcg-rewrite
    risk_level: str = "no_risk"  # fcg-rewrite
    categories: List[str] = list_field()  # fcg-rewrite
    tool_call_count: int = 0  # fcg-rewrite
    blocked_tools: List[str] = list_field()  # fcg-rewrite
    suspicious_arguments: List[Dict[str, Any]] = list_field()  # fcg-rewrite


class HallucinationResult(BaseModel):  # fcg-rewrite
    risk_level: str = "no_risk"  # fcg-rewrite
    categories: List[str] = list_field()  # fcg-rewrite
    groundedness_score: Optional[float] = None  # fcg-rewrite
    consistency_score: Optional[float] = None  # fcg-rewrite
    flagged_claims: List[str] = list_field()  # fcg-rewrite


class SkillAuditResponse(BaseModel):  # fcg-rewrite
    id: str
    risk_level: int = Field(..., description="Risk level: 0=normal, 1=low, 2=medium, 3=high")  # fcg-rewrite
    risk_label: str = Field(..., description="Risk label: normal, low_risk, medium_risk, high_risk")  # fcg-rewrite
    classification: str = Field(..., description="Classification model output (e.g., Safety: Safe)")  # fcg-rewrite
    analysis: str = Field(..., description="LLM analysis reasoning")  # fcg-rewrite
    suggest_action: str = Field(..., description="Suggested action: pass, warn, block")  # fcg-rewrite


class GuardrailResult(BaseModel):  # fcg-rewrite
    compliance: ComplianceResult  # fcg-rewrite
    security: SecurityResult  # fcg-rewrite
    data: DataSecurityResult  # fcg-rewrite
    agent_safety: Optional[AgentSafetyResult] = None  # fcg-rewrite
    hallucination: Optional[HallucinationResult] = None  # fcg-rewrite
    plugin_results: Optional[Dict[str, Any]] = None  # fcg-rewrite


class GuardrailResponse(BaseModel):  # fcg-rewrite
    id: str
    result: GuardrailResult  # fcg-rewrite
    overall_risk_level: str  # fcg-rewrite
    suggest_action: str  # fcg-rewrite
    suggest_answer: Optional[str] = None  # fcg-rewrite
    score: Optional[float] = None  # fcg-rewrite


class DetectionResultResponse(BaseModel):  # fcg-rewrite
    id: int
    request_id: str  # fcg-rewrite
    content: str  # fcg-rewrite
    suggest_action: Optional[str]  # fcg-rewrite
    suggest_answer: Optional[str]  # fcg-rewrite
    hit_keywords: Optional[str]  # fcg-rewrite
    created_at: datetime  # fcg-rewrite
    ip_address: Optional[str]  # fcg-rewrite
    security_risk_level: str = "no_risk"  # fcg-rewrite
    security_categories: List[str] = list_field()  # fcg-rewrite
    compliance_risk_level: str = "no_risk"  # fcg-rewrite
    compliance_categories: List[str] = list_field()  # fcg-rewrite
    data_risk_level: str = "no_risk"  # fcg-rewrite
    data_categories: List[str] = list_field()  # fcg-rewrite
    agent_safety_risk_level: str = "no_risk"  # fcg-rewrite
    agent_safety_categories: List[str] = list_field()  # fcg-rewrite
    hallucination_risk_level: str = "no_risk"  # fcg-rewrite
    hallucination_categories: List[str] = list_field()  # fcg-rewrite
    groundedness_score: Optional[float] = None  # fcg-rewrite
    consistency_score: Optional[float] = None  # fcg-rewrite
    score: Optional[float] = None  # fcg-rewrite
    has_image: bool = False  # fcg-rewrite
    image_count: int = 0  # fcg-rewrite
    image_paths: List[str] = list_field()  # fcg-rewrite
    image_urls: List[str] = list_field()  # fcg-rewrite
    is_direct_model_access: bool = False  # fcg-rewrite


class NamedKeywordListResponse(BaseModel):  # fcg-rewrite
    id: int
    name: str  # fcg-rewrite
    keywords: List[str]  # fcg-rewrite
    description: Optional[str]  # fcg-rewrite
    is_active: bool  # fcg-rewrite
    created_at: datetime  # fcg-rewrite
    updated_at: datetime  # fcg-rewrite


class BlacklistResponse(NamedKeywordListResponse):  # fcg-rewrite
    pass


class WhitelistResponse(NamedKeywordListResponse):  # fcg-rewrite
    pass


class ResponseTemplateResponse(BaseModel):  # fcg-rewrite
    id: int
    tenant_id: Optional[str] = None  # fcg-rewrite
    application_id: Optional[str] = None  # fcg-rewrite
    category: Optional[str] = None  # fcg-rewrite
    scanner_type: Optional[str] = None  # fcg-rewrite
    scanner_identifier: Optional[str] = None  # fcg-rewrite
    scanner_name: Optional[str] = None  # fcg-rewrite
    risk_level: str  # fcg-rewrite
    template_content: Dict[str, str]  # fcg-rewrite
    is_default: bool  # fcg-rewrite
    is_active: bool  # fcg-rewrite
    created_at: datetime  # fcg-rewrite
    updated_at: datetime  # fcg-rewrite


class SensitivityThresholdResponse(BaseModel):  # fcg-rewrite
    high_sensitivity_threshold: float  # fcg-rewrite
    medium_sensitivity_threshold: float  # fcg-rewrite
    low_sensitivity_threshold: float  # fcg-rewrite
    sensitivity_trigger_level: str  # fcg-rewrite


class DashboardStats(BaseModel):  # fcg-rewrite
    total_requests: int  # fcg-rewrite
    security_risks: int  # fcg-rewrite
    compliance_risks: int  # fcg-rewrite
    data_leaks: int  # fcg-rewrite
    high_risk_count: int  # fcg-rewrite
    medium_risk_count: int  # fcg-rewrite
    low_risk_count: int  # fcg-rewrite
    safe_count: int  # fcg-rewrite
    risk_distribution: Dict[str, int]  # fcg-rewrite
    daily_trends: List[Dict[str, Any]]  # fcg-rewrite


class PaginatedResponse(BaseModel):  # fcg-rewrite
    items: List[Any]  # fcg-rewrite
    total: int  # fcg-rewrite
    page: int  # fcg-rewrite
    per_page: int  # fcg-rewrite
    pages: int  # fcg-rewrite


class ApiResponse(BaseModel):  # fcg-rewrite
    success: bool  # fcg-rewrite
    message: str  # fcg-rewrite
    data: Optional[Any] = None  # fcg-rewrite


class ProxyCompletionResponse(BaseModel):  # fcg-rewrite
    id: str
    object: str = "chat.completion"  # fcg-rewrite
    created: int  # fcg-rewrite
    model: str  # fcg-rewrite
    choices: List[Dict[str, Any]]  # fcg-rewrite
    usage: Optional[Dict[str, int]] = None  # fcg-rewrite


class ProxyModelListResponse(BaseModel):  # fcg-rewrite
    object: str = "list"  # fcg-rewrite
    data: List[Dict[str, Any]]  # fcg-rewrite


class KnowledgeBaseResponse(BaseModel):  # fcg-rewrite
    id: int
    category: Optional[str] = None  # fcg-rewrite
    scanner_type: Optional[str] = None  # fcg-rewrite
    scanner_identifier: Optional[str] = None  # fcg-rewrite
    scanner_name: Optional[str] = None  # fcg-rewrite
    name: str  # fcg-rewrite
    description: Optional[str]  # fcg-rewrite
    file_path: str  # fcg-rewrite
    vector_file_path: Optional[str]  # fcg-rewrite
    total_qa_pairs: int  # fcg-rewrite
    similarity_threshold: float  # fcg-rewrite
    is_active: bool  # fcg-rewrite
    is_global: bool  # fcg-rewrite
    is_disabled_by_me: bool = False  # fcg-rewrite
    created_at: datetime  # fcg-rewrite
    updated_at: datetime  # fcg-rewrite


class KnowledgeBaseFileInfo(BaseModel):  # fcg-rewrite
    original_file_exists: bool  # fcg-rewrite
    vector_file_exists: bool  # fcg-rewrite
    original_file_size: int  # fcg-rewrite
    vector_file_size: int  # fcg-rewrite
    total_qa_pairs: int  # fcg-rewrite


class SimilarQuestionResult(BaseModel):  # fcg-rewrite
    questionid: str  # fcg-rewrite
    question: str  # fcg-rewrite
    answer: str  # fcg-rewrite
    similarity_score: float  # fcg-rewrite
    rank: int  # fcg-rewrite


class DataSecurityEntityTypeResponse(BaseModel):  # fcg-rewrite
    id: str
    entity_type: str  # fcg-rewrite
    display_name: str  # fcg-rewrite
    risk_level: str  # fcg-rewrite
    pattern: str  # fcg-rewrite
    anonymization_method: str  # fcg-rewrite
    anonymization_config: Dict[str, Any]  # fcg-rewrite
    check_input: bool  # fcg-rewrite
    check_output: bool  # fcg-rewrite
    is_active: bool  # fcg-rewrite
    is_global: bool  # fcg-rewrite
    created_at: datetime  # fcg-rewrite
    updated_at: datetime  # fcg-rewrite


class DifyModerationResponse(BaseModel):  # fcg-rewrite
    model_config = ConfigDict(exclude_none=True)  # fcg-rewrite
    result: Optional[str] = None  # fcg-rewrite
    flagged: Optional[bool] = None  # fcg-rewrite
    action: Optional[str] = None  # fcg-rewrite
    preset_response: Optional[str] = None  # fcg-rewrite
    inputs: Optional[Dict[str, Any]] = None  # fcg-rewrite
    query: Optional[str] = None  # fcg-rewrite
    text: Optional[str] = None  # fcg-rewrite


class ScannerResponse(BaseModel):  # fcg-rewrite
    id: str
    tag: str  # fcg-rewrite
    name: str  # fcg-rewrite
    description: Optional[str]  # fcg-rewrite
    scanner_type: str  # fcg-rewrite
    definition: str  # fcg-rewrite
    default_risk_level: str  # fcg-rewrite
    default_scan_prompt: bool  # fcg-rewrite
    default_scan_response: bool  # fcg-rewrite


class PackageBase(BaseModel):  # fcg-rewrite
    id: str
    package_code: str  # fcg-rewrite
    package_name: str  # fcg-rewrite
    author: str  # fcg-rewrite
    description: Optional[str]  # fcg-rewrite
    version: str  # fcg-rewrite
    package_type: str  # fcg-rewrite
    scanner_count: int  # fcg-rewrite
    price: Optional[float] = None  # fcg-rewrite
    price_display: Optional[str] = None  # fcg-rewrite
    bundle: Optional[str] = None  # fcg-rewrite


class PackageResponse(PackageBase):  # fcg-rewrite
    license: str  # fcg-rewrite
    created_at: Optional[str]  # fcg-rewrite
    updated_at: Optional[str]  # fcg-rewrite
    archived: bool = False  # fcg-rewrite
    archived_at: Optional[str] = None  # fcg-rewrite
    archive_reason: Optional[str] = None  # fcg-rewrite


class PackageDetailResponse(PackageBase):  # fcg-rewrite
    license: str  # fcg-rewrite
    scanners: List[Dict[str, Any]]  # fcg-rewrite
    created_at: Optional[str]  # fcg-rewrite
    updated_at: Optional[str]  # fcg-rewrite


class MarketplacePackageResponse(PackageBase):  # fcg-rewrite
    price_display: Optional[str]  # fcg-rewrite
    purchase_status: Optional[str]  # fcg-rewrite
    purchased: bool  # fcg-rewrite
    purchase_requested: bool  # fcg-rewrite
    created_at: Optional[str]  # fcg-rewrite


class ScannerConfigResponse(BaseModel):  # fcg-rewrite
    id: str
    tag: str  # fcg-rewrite
    name: str  # fcg-rewrite
    description: Optional[str]  # fcg-rewrite
    scanner_type: str  # fcg-rewrite
    package_name: str  # fcg-rewrite
    package_id: Optional[str]  # fcg-rewrite
    is_custom: bool  # fcg-rewrite
    is_enabled: bool  # fcg-rewrite
    risk_level: str  # fcg-rewrite
    scan_prompt: bool  # fcg-rewrite
    scan_response: bool  # fcg-rewrite
    default_risk_level: str  # fcg-rewrite
    default_scan_prompt: bool  # fcg-rewrite
    default_scan_response: bool  # fcg-rewrite
    has_risk_level_override: bool  # fcg-rewrite
    has_scan_prompt_override: bool  # fcg-rewrite
    has_scan_response_override: bool  # fcg-rewrite


class CustomScannerResponse(ScannerResponse):  # fcg-rewrite
    custom_scanner_id: str  # fcg-rewrite
    notes: Optional[str]  # fcg-rewrite
    created_by: str  # fcg-rewrite
    created_at: Optional[str]  # fcg-rewrite
    updated_at: Optional[str]  # fcg-rewrite
    is_enabled: bool = True  # fcg-rewrite


class PurchaseResponse(BaseModel):  # fcg-rewrite
    id: str
    package_id: str  # fcg-rewrite
    package_name: Optional[str]  # fcg-rewrite
    package_code: Optional[str]  # fcg-rewrite
    status: str  # fcg-rewrite
    request_email: str  # fcg-rewrite
    request_message: Optional[str]  # fcg-rewrite
    rejection_reason: Optional[str]  # fcg-rewrite
    approved_at: Optional[str]  # fcg-rewrite
    created_at: Optional[str]  # fcg-rewrite


class PurchasePendingResponse(BaseModel):  # fcg-rewrite
    id: str
    tenant_id: str  # fcg-rewrite
    tenant_email: Optional[str]  # fcg-rewrite
    package_id: str  # fcg-rewrite
    package_name: Optional[str]  # fcg-rewrite
    package_code: Optional[str]  # fcg-rewrite
    request_email: str  # fcg-rewrite
    request_message: Optional[str]  # fcg-rewrite
    created_at: Optional[str]  # fcg-rewrite


class PackageStatisticsResponse(BaseModel):  # fcg-rewrite
    package_id: str  # fcg-rewrite
    package_name: str  # fcg-rewrite
    total_purchases: int  # fcg-rewrite
    approved_purchases: int  # fcg-rewrite
    pending_purchases: int  # fcg-rewrite
    scanner_count: int  # fcg-rewrite
