"""Typed API request payloads and validation rules."""

import re
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator, validator

_ROLES = {"user", "system", "assistant", "tool", "function"}
_SCANNER_TYPES = {"blacklist", "whitelist", "official_scanner", "marketplace_scanner", "custom_scanner"}
_RISK_LEVELS = {"no_risk", "low_risk", "medium_risk", "high_risk"}
_OVERRIDE_RISKS = {"low_risk", "medium_risk", "high_risk"}
_CATEGORIES = {f"S{index}" for index in range(1, 22)}
_EMAIL = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _choice(value, allowed, label):
    if value is not None and value not in allowed:
        raise ValueError(f"{label} must be one of: {sorted(allowed)}")
    return value


def _required_text(value: str, label: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{label} cannot be empty")
    if len(value) > 1_000_000:
        raise ValueError(f"{label} too long (max 1000000 characters)")
    return value.strip()


class ImageUrl(BaseModel):
    url: str


class ContentPart(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[ImageUrl] = None

    @validator("type")
    def check_type(cls, value):
        return _choice(value, {"text", "image_url"}, "type")


class Message(BaseModel):
    role: str
    content: Optional[Union[str, List[ContentPart]]] = None

    @validator("role")
    def check_role(cls, value):
        return _choice(value, _ROLES, "role")

    @validator("content", pre=True)
    def check_content(cls, value):
        if value is None or isinstance(value, list):
            return value
        if not isinstance(value, str):
            raise ValueError("content must be string, list of content parts, or null")
        if len(value) > 1_000_000:
            raise ValueError("content too long (max 1000000 characters)")
        if not value.strip():
            return value
        return value.strip()


class SkillOperation(BaseModel):
    index: int
    action: str
    target: str
    details: Optional[str] = None


class SkillAuditRequest(BaseModel):
    skill_name: str
    skill_description: str
    operations: List[SkillOperation]
    current_operation: str
    skill_metadata: Optional[Dict[str, Any]] = None

    @validator("operations")
    def require_operations(cls, value):
        if not value:
            raise ValueError("operations cannot be empty")
        return value


class GuardrailRequest(BaseModel):
    model: str
    messages: List[Message]
    max_tokens: Optional[int] = None
    extra_body: Optional[Dict[str, Any]] = None

    @validator("messages")
    def require_messages(cls, value):
        if not value:
            raise ValueError("messages cannot be empty")
        return value


class KeywordListRequest(BaseModel):
    name: str
    keywords: List[str]
    description: Optional[str] = None
    is_active: bool = True

    @validator("keywords")
    def clean_keywords(cls, value):
        if not value:
            raise ValueError("keywords cannot be empty")
        return [keyword.strip() for keyword in value if keyword.strip()]


class BlacklistRequest(KeywordListRequest):
    pass


class WhitelistRequest(KeywordListRequest):
    pass


class ScannerTarget(BaseModel):
    category: Optional[str] = None
    scanner_type: Optional[str] = None
    scanner_identifier: Optional[str] = None

    @validator("scanner_type")
    def check_scanner_type(cls, value):
        return _choice(value, _SCANNER_TYPES, "scanner_type")

    @model_validator(mode="after")
    def require_target(self):
        if not self.category and not (self.scanner_type and self.scanner_identifier):
            raise ValueError("Must provide either 'category' or both 'scanner_type' and 'scanner_identifier'")
        return self


class ResponseTemplateRequest(ScannerTarget):
    risk_level: str
    template_content: Dict[str, str]
    is_default: bool = False
    is_active: bool = True

    @validator("category")
    def check_category(cls, value):
        return _choice(value, _CATEGORIES | {"default"}, "category")

    @validator("risk_level")
    def normalize_risk(cls, value):
        normalized = value.replace(" ", "_")
        return _choice(normalized, _RISK_LEVELS, "risk_level")

    @validator("template_content")
    def require_translation(cls, value):
        if not value or not (value.get("en") or value.get("zh")):
            raise ValueError("template_content must contain at least 'en' or 'zh'")
        return value


class ProxyCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    user: Optional[str] = None


class ProxyModelConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    config_name: str
    api_base_url: str
    api_key: str
    model_name: str
    enabled: Optional[bool] = True
    block_on_input_risk: Optional[bool] = False
    block_on_output_risk: Optional[bool] = False
    enable_reasoning_detection: Optional[bool] = True
    stream_chunk_size: Optional[int] = Field(50, ge=1, le=500)


class InputGuardrailRequest(BaseModel):
    input: str
    model: Optional[str] = "Qwen3Guard-Gen-8B"
    xxai_app_user_id: Optional[str] = None

    @validator("input")
    def check_input(cls, value):
        return _required_text(value, "input")


class OutputGuardrailRequest(BaseModel):
    input: str
    output: str
    xxai_app_user_id: Optional[str] = None

    @validator("input")
    def check_input(cls, value):
        return _required_text(value, "input")

    @validator("output")
    def check_output(cls, value):
        return _required_text(value, "output")


class ConfidenceThresholdRequest(BaseModel):
    high_confidence_threshold: float = Field(..., ge=0.0, le=1.0)
    medium_confidence_threshold: float = Field(..., ge=0.0, le=1.0)
    low_confidence_threshold: float = Field(..., ge=0.0, le=1.0)
    confidence_trigger_level: str = Field(..., pattern="^(low|medium|high)$")


class KnowledgeBaseRequest(ScannerTarget):
    name: str
    description: Optional[str] = None
    similarity_threshold: float = Field(0.7, ge=0, le=1)
    is_active: bool = True
    is_global: Optional[bool] = False

    @validator("category")
    def check_category(cls, value):
        return _choice(value, _CATEGORIES, "category")

    @validator("name")
    def check_name(cls, value):
        value = _required_text(value, "name")
        if len(value) > 255:
            raise ValueError("name too long (max 255 characters)")
        return value


class DifyModerationParams(BaseModel):
    app_id: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    query: Optional[str] = None
    text: Optional[str] = None


class DifyModerationRequest(BaseModel):
    point: str
    params: Optional[DifyModerationParams] = None

    @validator("point")
    def check_point(cls, value):
        return _choice(value, {"ping", "app.moderation.input", "app.moderation.output"}, "point")


class PackageUploadRequest(BaseModel):
    package_data: dict
    price: Optional[float] = Field(None, ge=0)
    bundle: Optional[str] = None
    language: Optional[str] = "en"


class PackageUpdateRequest(BaseModel):
    package_name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    price: Optional[float] = None
    price_display: Optional[str] = None
    bundle: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class ScannerConfigUpdateRequest(BaseModel):
    is_enabled: Optional[bool] = None
    risk_level: Optional[str] = None
    scan_prompt: Optional[bool] = None
    scan_response: Optional[bool] = None

    @validator("risk_level")
    def check_risk(cls, value):
        return _choice(value, _OVERRIDE_RISKS, "risk_level")


class ScannerConfigBulkUpdateItem(ScannerConfigUpdateRequest):
    scanner_id: str


class ScannerConfigBulkUpdateRequest(BaseModel):
    updates: List[ScannerConfigBulkUpdateItem]


class CustomScannerCreateRequest(BaseModel):
    scanner_type: str = Field(..., pattern="^(genai|regex|keyword)$")
    name: str = Field(..., min_length=1, max_length=200)
    definition: str = Field(..., min_length=1, max_length=2000)
    description: Optional[str] = Field(None, max_length=500)
    risk_level: str = Field(..., pattern="^(high_risk|medium_risk|low_risk)$")
    scan_prompt: bool = True
    scan_response: bool = True
    notes: Optional[str] = Field(None, max_length=1000)


class CustomScannerUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    definition: Optional[str] = Field(None, min_length=1, max_length=2000)
    description: Optional[str] = Field(None, max_length=500)
    risk_level: Optional[str] = Field(None, pattern="^(high_risk|medium_risk|low_risk)$")
    scan_prompt: Optional[bool] = None
    scan_response: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)
    is_enabled: Optional[bool] = None


class PurchaseRequestCreate(BaseModel):
    package_id: str
    email: str
    message: Optional[str] = Field(None, max_length=1000)

    @validator("email")
    def check_email(cls, value):
        if not _EMAIL.match(value):
            raise ValueError("Invalid email format")
        return value


class PurchaseApprovalRequest(BaseModel):
    rejection_reason: Optional[str] = Field(None, max_length=500)
