from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint, Float, Numeric  # fcg-rewrite
from sqlalchemy.dialects.postgresql import UUID  # fcg-rewrite
import uuid  # fcg-rewrite
from sqlalchemy.sql import func  # fcg-rewrite
from sqlalchemy.orm import relationship  # fcg-rewrite
from database.connection import Base  # fcg-rewrite

class Tenant(Base):  # fcg-rewrite
    """租户表 (原用户表)"""
    __tablename__ = "tenants"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    email = Column(String(255), unique=True, nullable=False, index=True)  # fcg-rewrite
    password_hash = Column(String(128), nullable=False)  # fcg-rewrite
    is_active = Column(Boolean, default=False)  # After email verification, activate  # fcg-rewrite
    is_verified = Column(Boolean, default=False)  # Whether the email has been verified  # fcg-rewrite
    is_super_admin = Column(Boolean, default=False)  # Whether to be a super admin  # fcg-rewrite
    api_key = Column(String(64), unique=True, nullable=False, index=True)  # Deprecated: kept for backward compatibility, use api_keys table instead  # fcg-rewrite
    model_api_key = Column(String(64), unique=True, nullable=True, index=True)  # API key for direct model access (format: sk-xxai-model-{52 chars})  # fcg-rewrite
    log_direct_model_access = Column(Boolean, default=False, nullable=False)  # Whether to log direct model access calls (default: False for privacy)  # fcg-rewrite
    language = Column(String(10), default='en', nullable=False)  # User language preference  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    applications = relationship("Application", back_populates="tenant", cascade="all, delete-orphan")  # fcg-rewrite
    detection_results = relationship("DetectionResult", back_populates="tenant")  # fcg-rewrite
    test_models = relationship("TestModelConfig", back_populates="tenant")  # fcg-rewrite
    blacklists = relationship("Blacklist", back_populates="tenant")  # fcg-rewrite
    whitelists = relationship("Whitelist", back_populates="tenant")  # fcg-rewrite
    response_templates = relationship("ResponseTemplate", back_populates="tenant")  # fcg-rewrite
    risk_config = relationship("RiskTypeConfig", back_populates="tenant", uselist=False)  # fcg-rewrite

class Application(Base):  # fcg-rewrite
    """Application table - Each tenant can have multiple applications"""
    __tablename__ = "applications"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    name = Column(String(100), nullable=False)  # fcg-rewrite
    description = Column(Text)  # fcg-rewrite
    is_active = Column(Boolean, default=True, nullable=False, index=True)  # fcg-rewrite
    # Source of application creation: 'manual' (UI/API) or 'auto_discovery' (gateway consumer)
    source = Column(String(32), default='manual', nullable=False)  # fcg-rewrite
    # External identifier for auto-discovered apps (e.g., gateway consumer name)
    external_id = Column(String(255), nullable=True, index=True)  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant", back_populates="applications")  # fcg-rewrite
    api_keys = relationship("ApiKey", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite
    blacklists = relationship("Blacklist", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite
    whitelists = relationship("Whitelist", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite
    response_templates = relationship("ResponseTemplate", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite
    risk_config = relationship("RiskTypeConfig", back_populates="application", uselist=False, cascade="all, delete-orphan")  # fcg-rewrite
    ban_policies = relationship("BanPolicy", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite
    knowledge_bases = relationship("KnowledgeBase", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite
    data_security_entity_types = relationship("DataSecurityEntityType", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite
    # Note: upstream_api_configs relationship removed - Security Gateway configs are tenant-level, not application-specific
    test_models = relationship("TestModelConfig", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite
    rate_limits = relationship("TenantRateLimit", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite
    detection_results = relationship("DetectionResult", back_populates="application")  # fcg-rewrite
    user_ban_records = relationship("UserBanRecord", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite
    user_risk_triggers = relationship("UserRiskTrigger", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite
    appeal_config = relationship("AppealConfig", back_populates="application", uselist=False, cascade="all, delete-orphan")  # fcg-rewrite
    appeal_records = relationship("AppealRecord", back_populates="application", cascade="all, delete-orphan")  # fcg-rewrite

    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('tenant_id', 'name', name='uq_applications_tenant_name'),  # fcg-rewrite
    )


class ApiKey(Base):  # fcg-rewrite
    """API Key table - Each application can have multiple API keys"""
    __tablename__ = "api_keys"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    key = Column(String(64), unique=True, nullable=False, index=True)  # fcg-rewrite
    name = Column(String(100))  # fcg-rewrite
    is_active = Column(Boolean, default=True, nullable=False, index=True)  # fcg-rewrite
    last_used_at = Column(DateTime(timezone=True))  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application", back_populates="api_keys")  # fcg-rewrite


class EmailVerification(Base):  # fcg-rewrite
    """Email verification table"""
    __tablename__ = "email_verifications"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    email = Column(String(255), nullable=False, index=True)  # fcg-rewrite
    verification_code = Column(String(6), nullable=False)  # fcg-rewrite
    expires_at = Column(DateTime(timezone=True), nullable=False)  # fcg-rewrite
    is_used = Column(Boolean, default=False)  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite

class PasswordResetToken(Base):  # fcg-rewrite
    """Password reset token table"""
    __tablename__ = "password_reset_tokens"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    email = Column(String(255), nullable=False, index=True)  # fcg-rewrite
    reset_token = Column(String(64), unique=True, nullable=False, index=True)  # fcg-rewrite
    expires_at = Column(DateTime(timezone=True), nullable=False)  # fcg-rewrite
    is_used = Column(Boolean, default=False, index=True)  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite

class DetectionResult(Base):  # fcg-rewrite
    """Detection result table"""
    __tablename__ = "detection_results"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    request_id = Column(String(64), unique=True, nullable=False, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Associated tenant  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True)  # Associated application (nullable for historical data)  # fcg-rewrite
    content = Column(Text, nullable=False)  # fcg-rewrite
    suggest_action = Column(String(20))  # 'pass', 'reject', 'replace'  # fcg-rewrite
    suggest_answer = Column(Text)  # Suggest answer content  # fcg-rewrite
    hit_keywords = Column(Text)  # Hit keywords (blacklist/whitelist)  # fcg-rewrite
    model_response = Column(Text)  # Original model response  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    ip_address = Column(String(45))  # fcg-rewrite
    user_agent = Column(Text)  # fcg-rewrite
    # Separated security and compliance detection results
    security_risk_level = Column(String(20), default='no_risk')  # Security risk level  # fcg-rewrite
    security_categories = Column(JSON, default=list)  # Security categories  # fcg-rewrite
    compliance_risk_level = Column(String(20), default='no_risk')  # Compliance risk level  # fcg-rewrite
    compliance_categories = Column(JSON, default=list)  # Compliance categories  # fcg-rewrite
    # Data security detection results
    data_risk_level = Column(String(20), default='no_risk')  # Data leakage risk level  # fcg-rewrite
    data_categories = Column(JSON, default=list)  # Data leakage categories  # fcg-rewrite
    # Multimodal related fields
    has_image = Column(Boolean, default=False, index=True)  # Whether contains image  # fcg-rewrite
    image_count = Column(Integer, default=0)  # Image count  # fcg-rewrite
    image_paths = Column(JSON, default=list)  # Saved image file path list  # fcg-rewrite
    # Direct model access flag
    is_direct_model_access = Column(Boolean, default=False, index=True)  # Whether this is a direct model access call (not a guardrail check)  # fcg-rewrite
    # Agent safety detection results
    agent_safety_risk_level = Column(String(20), default='no_risk')  # fcg-rewrite
    agent_safety_categories = Column(JSON, default=list)  # fcg-rewrite
    # Hallucination detection results
    hallucination_risk_level = Column(String(20), default='no_risk')  # fcg-rewrite
    hallucination_categories = Column(JSON, default=list)  # fcg-rewrite
    groundedness_score = Column(Float, nullable=True)  # fcg-rewrite
    consistency_score = Column(Float, nullable=True)  # fcg-rewrite
    # Generic plugin results (JSON, stores data from all detection plugins)
    plugin_results = Column(JSON, nullable=True)  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant", back_populates="detection_results")  # fcg-rewrite
    application = relationship("Application", back_populates="detection_results")  # fcg-rewrite

class Blacklist(Base):  # fcg-rewrite
    """Blacklist table"""
    __tablename__ = "blacklist"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Associated tenant (kept for backward compatibility)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # Associated application  # fcg-rewrite
    name = Column(String(100), nullable=False)  # Blacklist library name  # fcg-rewrite
    keywords = Column(JSON, nullable=False)  # Keywords list  # fcg-rewrite
    description = Column(Text)  # Description  # fcg-rewrite
    is_active = Column(Boolean, default=True, index=True)  # Whether enabled  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant", back_populates="blacklists")  # fcg-rewrite
    application = relationship("Application", back_populates="blacklists")  # fcg-rewrite

class Whitelist(Base):  # fcg-rewrite
    """Whitelist table"""
    __tablename__ = "whitelist"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Associated tenant (kept for backward compatibility)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # Associated application  # fcg-rewrite
    name = Column(String(100), nullable=False)  # Whitelist library name  # fcg-rewrite
    keywords = Column(JSON, nullable=False)  # Keywords list  # fcg-rewrite
    description = Column(Text)  # Description  # fcg-rewrite
    is_active = Column(Boolean, default=True, index=True)  # Whether enabled  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant", back_populates="whitelists")  # fcg-rewrite
    application = relationship("Application", back_populates="whitelists")  # fcg-rewrite

class ResponseTemplate(Base):  # fcg-rewrite
    """Response template table - supports all scanner types"""
    __tablename__ = "response_templates"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    # Allow null: When it is a system-level default template, tenant_id is null
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True)  # Associated tenant (can be null for global templates)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True)  # Associated application (nullable for global templates)  # fcg-rewrite

    # Legacy field: Risk category (S1-S21, default) - kept for backward compatibility
    category = Column(String(50), nullable=True, index=True)  # fcg-rewrite

    # New fields for unified scanner support
    scanner_type = Column(String(50), nullable=True, index=True)  # Scanner type: blacklist, whitelist, official_scanner, marketplace_scanner, custom_scanner  # fcg-rewrite
    scanner_identifier = Column(String(255), nullable=True)  # Scanner identifier: blacklist name, whitelist name, or scanner tag (S1, S2, S100, etc.)  # fcg-rewrite
    scanner_name = Column(String(255), nullable=True)  # Scanner human-readable name for display (e.g., "Bank Fraud", "Travel Discussion")  # fcg-rewrite

    risk_level = Column(String(20), nullable=False)  # Risk level  # fcg-rewrite
    template_content = Column(JSON, nullable=False)  # Multilingual response template content: {"en": "...", "zh": "...", ...}  # fcg-rewrite
    is_default = Column(Boolean, default=False)  # Whether it is a default template  # fcg-rewrite
    is_active = Column(Boolean, default=True)  # Whether enabled  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant", back_populates="response_templates")  # fcg-rewrite
    application = relationship("Application", back_populates="response_templates")  # fcg-rewrite

class TenantSwitch(Base):  # fcg-rewrite
    """Tenant switch record table (for super admin to switch tenant perspective)"""
    __tablename__ = "tenant_switches"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    admin_tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)  # Admin tenant ID  # fcg-rewrite
    target_tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)  # Target tenant ID  # fcg-rewrite
    switch_time = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    session_token = Column(String(128), unique=True, nullable=False)  # Switch session token  # fcg-rewrite
    expires_at = Column(DateTime(timezone=True), nullable=False)  # fcg-rewrite
    is_active = Column(Boolean, default=True)  # fcg-rewrite

class SystemConfig(Base):  # fcg-rewrite
    """System config table"""
    __tablename__ = "system_config"  # fcg-rewrite
    
    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    config_key = Column(String(100), unique=True, nullable=False)  # fcg-rewrite
    config_value = Column(Text)  # fcg-rewrite
    description = Column(Text)  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

class LoginAttempt(Base):  # fcg-rewrite
    """Login attempt record table (for anti-brute force)"""
    __tablename__ = "login_attempts"  # fcg-rewrite
    
    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    email = Column(String(255), nullable=False, index=True)  # fcg-rewrite
    ip_address = Column(String(45), nullable=False, index=True)  # Support IPv6  # fcg-rewrite
    user_agent = Column(Text)  # fcg-rewrite
    success = Column(Boolean, default=False, index=True)  # fcg-rewrite
    attempted_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)  # fcg-rewrite

class RiskTypeConfig(Base):  # fcg-rewrite
    """Risk type switch config table"""
    __tablename__ = "risk_type_config"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Kept for backward compatibility  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)  # Associated application (unique constraint moved here)  # fcg-rewrite

    # S1-S21 risk type switch configuration
    s1_enabled = Column(Boolean, default=True)  # General political topics  # fcg-rewrite
    s2_enabled = Column(Boolean, default=True)  # Sensitive political topics  # fcg-rewrite
    s3_enabled = Column(Boolean, default=True)  # Insult to National Symbols or Leaders  # fcg-rewrite
    s4_enabled = Column(Boolean, default=True)  # Harm to minors  # fcg-rewrite
    s5_enabled = Column(Boolean, default=True)  # Violent crime  # fcg-rewrite
    s6_enabled = Column(Boolean, default=True)  # Non-violent crime  # fcg-rewrite
    s7_enabled = Column(Boolean, default=True)  # Pornography  # fcg-rewrite
    s8_enabled = Column(Boolean, default=True)  # Hate & Discrimination  # fcg-rewrite
    s9_enabled = Column(Boolean, default=True)  # Prompt Attacks  # fcg-rewrite
    s10_enabled = Column(Boolean, default=True) # Profanity  # fcg-rewrite
    s11_enabled = Column(Boolean, default=True) # Privacy Invasion  # fcg-rewrite
    s12_enabled = Column(Boolean, default=True) # Commercial Violations  # fcg-rewrite
    s13_enabled = Column(Boolean, default=True) # Intellectual Property Infringement  # fcg-rewrite
    s14_enabled = Column(Boolean, default=True) # Harassment  # fcg-rewrite
    s15_enabled = Column(Boolean, default=True) # Weapons of Mass Destruction  # fcg-rewrite
    s16_enabled = Column(Boolean, default=True) # Self-Harm  # fcg-rewrite
    s17_enabled = Column(Boolean, default=True) # Sexual Crimes  # fcg-rewrite
    s18_enabled = Column(Boolean, default=True) # Threats  # fcg-rewrite
    s19_enabled = Column(Boolean, default=True) # Professional Financial Advice  # fcg-rewrite
    s20_enabled = Column(Boolean, default=True) # Professional Medical Advice  # fcg-rewrite
    s21_enabled = Column(Boolean, default=True) # Professional Legal Advice  # fcg-rewrite

    # Global sensitivity threshold config
    high_sensitivity_threshold = Column(Float, default=0.40)    # High sensitivity threshold  # fcg-rewrite
    medium_sensitivity_threshold = Column(Float, default=0.60)  # Medium sensitivity threshold  # fcg-rewrite
    low_sensitivity_threshold = Column(Float, default=0.95)     # Low sensitivity threshold  # fcg-rewrite

    # Sensitivity trigger level config (low, medium, high)
    sensitivity_trigger_level = Column(String(20), default="medium")  # Trigger detection hit lowest sensitivity level  # fcg-rewrite

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant", back_populates="risk_config")  # fcg-rewrite
    application = relationship("Application", back_populates="risk_config")  # fcg-rewrite

class TenantRateLimit(Base):  # fcg-rewrite
    """Tenant rate limit config table"""
    __tablename__ = "tenant_rate_limits"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Kept for backward compatibility  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True)  # Associated application  # fcg-rewrite
    requests_per_second = Column(Integer, default=10, nullable=False)  # Requests per second, 0 means no limit  # fcg-rewrite
    monthly_scan_limit = Column(Integer, default=10000, nullable=False)  # Monthly scan limit, 0 means no limit  # fcg-rewrite
    current_month_usage = Column(Integer, default=0, nullable=False)  # Current month usage count  # fcg-rewrite
    usage_reset_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # Usage counter reset time (start of current month)  # fcg-rewrite
    is_active = Column(Boolean, default=True, index=True)  # Whether to enable rate limiting  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application", back_populates="rate_limits")  # fcg-rewrite

class TenantRateLimitCounter(Base):  # fcg-rewrite
    """Tenant real-time rate limit counter table - for cross-process rate limiting"""
    __tablename__ = "tenant_rate_limit_counters"  # fcg-rewrite

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True, index=True)  # fcg-rewrite
    current_count = Column(Integer, default=0, nullable=False)  # Requests count in current window  # fcg-rewrite
    window_start = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # Window start time  # fcg-rewrite
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)  # Last updated time  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite

class TestModelConfig(Base):  # fcg-rewrite
    """Proxy model config table"""
    __tablename__ = "test_model_configs"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Kept for backward compatibility  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # Associated application  # fcg-rewrite
    name = Column(String(255), nullable=False)  # Model display name  # fcg-rewrite
    base_url = Column(String(512), nullable=False)  # API Base URL  # fcg-rewrite
    api_key = Column(String(512), nullable=False)  # API Key  # fcg-rewrite
    model_name = Column(String(255), nullable=False)  # Model name  # fcg-rewrite
    enabled = Column(Boolean, default=True, index=True)  # Whether enabled  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant", back_populates="test_models")  # fcg-rewrite
    application = relationship("Application", back_populates="test_models")  # fcg-rewrite

class UpstreamApiConfig(Base):  # fcg-rewrite
    """Upstream API configuration for Security Gateway"""
    __tablename__ = "upstream_api_configs"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # Used in gateway URL  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Tenant-level configuration  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=False)  # DEPRECATED: Always NULL. Applications are determined by API key when calling gateway  # fcg-rewrite
    config_name = Column(String(100), nullable=False, index=True)  # Display name (e.g., "OpenAI Production")  # fcg-rewrite
    api_base_url = Column(String(512), nullable=False)  # Upstream API base URL  # fcg-rewrite
    api_key_encrypted = Column(Text, nullable=False)  # Encrypted upstream API key  # fcg-rewrite
    provider = Column(String(50))  # Provider type: openai, anthropic, local, etc.  # fcg-rewrite
    is_active = Column(Boolean, default=True, index=True)  # Whether this config is active  # fcg-rewrite

    # Security config
    enable_reasoning_detection = Column(Boolean, default=True)  # Whether to detect reasoning content  # fcg-rewrite
    reasoning_format = Column(String(20), default='auto')  # Reasoning extraction format: auto, field, tag, none  # fcg-rewrite
    stream_chunk_size = Column(Integer, default=50)  # Stream detection interval, detect every N chunks  # fcg-rewrite

    # Private model attributes (for data leakage prevention)
    is_private_model = Column(Boolean, default=False, index=True)  # Whether this model is private (on-premise/data-safe)  # fcg-rewrite
    is_default_private_model = Column(Boolean, default=False, index=True)  # Whether this is the default private model for tenant  # fcg-rewrite
    private_model_names = Column(JSON, default=list)  # Model names available for automatic switching (e.g., ["gpt-4", "gpt-4-turbo"])  # fcg-rewrite
    default_private_model_name = Column(String(255), nullable=True)  # The specific model name to use when this is the default private model  # fcg-rewrite
    higress_cluster = Column(String(255), nullable=True)  # Higress cluster name for routing (e.g., outbound|443||private-llm.dns)  # fcg-rewrite

    # Metadata
    description = Column(Text)  # Optional description  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    # Note: application relationship removed - Security Gateway configs are tenant-level, not application-specific

    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('tenant_id', 'config_name', name='upstream_api_configs_tenant_name_unique'),  # fcg-rewrite
    )

class ProxyModelConfig(Base):  # fcg-rewrite
    """DEPRECATED: Reverse proxy model config table (replaced by UpstreamApiConfig)"""
    __tablename__ = "proxy_model_configs_deprecated"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # fcg-rewrite
    config_name = Column(String(100), nullable=False, index=True)  # Proxy model name, for model parameter matching  # fcg-rewrite
    api_base_url = Column(String(512), nullable=False)  # Upstream API base URL  # fcg-rewrite
    api_key_encrypted = Column(Text, nullable=False)  # Encrypted upstream API key  # fcg-rewrite
    model_name = Column(String(255), nullable=False)  # Upstream API model name  # fcg-rewrite
    enabled = Column(Boolean, default=True, index=True)  # Whether enabled  # fcg-rewrite

    # Security config (simplified design)
    enable_reasoning_detection = Column(Boolean, default=True)  # Whether to detect reasoning content, default enabled  # fcg-rewrite
    stream_chunk_size = Column(Integer, default=50)  # Stream detection interval, detect every N chunks, default 50  # fcg-rewrite

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite

class ProxyRequestLog(Base):  # fcg-rewrite
    """Reverse proxy request log table"""
    __tablename__ = "proxy_request_logs"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    request_id = Column(String(64), unique=True, nullable=False, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # fcg-rewrite

    # New foreign key to upstream_api_configs
    upstream_api_config_id = Column(UUID(as_uuid=True), ForeignKey("upstream_api_configs.id", ondelete="SET NULL"), index=True)  # fcg-rewrite

    # Old foreign key (deprecated, kept for backward compatibility)
    proxy_config_id = Column(UUID(as_uuid=True), ForeignKey("proxy_model_configs_deprecated.id"), nullable=True)  # fcg-rewrite

    # Request information
    model_requested = Column(String(255), nullable=False)  # User requested model name  # fcg-rewrite
    model_used = Column(String(255), nullable=False)  # Actual used model name  # fcg-rewrite
    provider = Column(String(50), nullable=False)  # Provider  # fcg-rewrite

    # Detection results
    input_detection_id = Column(String(64), index=True)  # Input detection request ID  # fcg-rewrite
    output_detection_id = Column(String(64), index=True)  # Output detection request ID  # fcg-rewrite
    input_blocked = Column(Boolean, default=False)  # Whether input is blocked  # fcg-rewrite
    output_blocked = Column(Boolean, default=False)  # Whether output is blocked  # fcg-rewrite

    # Statistics information
    request_tokens = Column(Integer)  # Request token count  # fcg-rewrite
    response_tokens = Column(Integer)  # Response token count  # fcg-rewrite
    total_tokens = Column(Integer)  # Total token count  # fcg-rewrite
    response_time_ms = Column(Integer)  # Response time (milliseconds)  # fcg-rewrite

    # Status
    status = Column(String(20), nullable=False)  # success, blocked, error  # fcg-rewrite
    error_message = Column(Text)  # Error message  # fcg-rewrite

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    proxy_config = relationship("ProxyModelConfig")  # fcg-rewrite

class KnowledgeBase(Base):  # fcg-rewrite
    """Knowledge base table - supports all scanner types"""
    __tablename__ = "knowledge_bases"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Kept for backward compatibility  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # Associated application  # fcg-rewrite

    # Legacy field: Risk category (S1-S21) - kept for backward compatibility
    category = Column(String(50), nullable=True, index=True)  # fcg-rewrite

    # New fields for unified scanner support
    scanner_type = Column(String(50), nullable=True, index=True)  # Scanner type: blacklist, whitelist, official_scanner, marketplace_scanner, custom_scanner  # fcg-rewrite
    scanner_identifier = Column(String(255), nullable=True)  # Scanner identifier: blacklist name, whitelist name, or scanner tag (S1, S2, S100, etc.)  # fcg-rewrite
    scanner_name = Column(String(255), nullable=True)  # Scanner human-readable name for display (e.g., "Bank Fraud", "Travel Discussion")  # fcg-rewrite

    name = Column(String(255), nullable=False)  # Knowledge base name  # fcg-rewrite
    description = Column(Text)  # Description  # fcg-rewrite
    file_path = Column(String(512), nullable=False)  # Original JSONL file path  # fcg-rewrite
    vector_file_path = Column(String(512))  # Vectorized file path  # fcg-rewrite
    total_qa_pairs = Column(Integer, default=0)  # Total QA pairs  # fcg-rewrite
    similarity_threshold = Column(Float, default=0.7, nullable=False)  # Similarity threshold for this KB (0-1)  # fcg-rewrite
    is_active = Column(Boolean, default=True, index=True)  # Whether enabled  # fcg-rewrite
    is_global = Column(Boolean, default=False, index=True)  # Whether it is a global knowledge base (all tenants take effect), only admin can set  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application", back_populates="knowledge_bases")  # fcg-rewrite

class OnlineTestModelSelection(Base):  # fcg-rewrite
    """Online test model selection table - record the proxy model selected by the tenant in online test"""
    __tablename__ = "online_test_model_selections"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # fcg-rewrite
    proxy_model_id = Column(UUID(as_uuid=True), ForeignKey("upstream_api_configs.id"), nullable=False, index=True)  # fcg-rewrite
    selected = Column(Boolean, default=False, nullable=False)  # Whether it is selected for online test  # fcg-rewrite
    model_name = Column(String(200), nullable=True)  # Model name specified by user for testing  # fcg-rewrite

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    proxy_model = relationship("UpstreamApiConfig")  # fcg-rewrite

    # Add unique constraint, ensure each tenant has only one record for each proxy model
    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('tenant_id', 'proxy_model_id', name='_tenant_proxy_model_selection_uc'),  # fcg-rewrite
    )

class DataSecurityEntityType(Base):  # fcg-rewrite
    """Data security entity type config table"""
    __tablename__ = "data_security_entity_types"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Kept for backward compatibility  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # Associated application  # fcg-rewrite
    entity_type = Column(String(100), nullable=False, index=True)  # Entity type code, such as ID_CARD_NUMBER  # fcg-rewrite
    entity_type_name = Column(String(200), nullable=False)  # Entity type name, such as "ID Card Number"  # fcg-rewrite
    category = Column(String(50), nullable=False, index=True)  # Risk level: low, medium, high  # fcg-rewrite
    recognition_method = Column(String(20), nullable=False)  # Recognition method: regex  # fcg-rewrite
    recognition_config = Column(JSON, nullable=False)  # Recognition config, such as {"pattern": "...", "check_input": true, "check_output": true}  # fcg-rewrite
    anonymization_method = Column(String(20), default='replace')  # Anonymization method: replace, mask, hash, encrypt, shuffle, random  # fcg-rewrite
    anonymization_config = Column(JSON)  # Anonymization config, such as {"replacement": "<ID_CARD>"}  # fcg-rewrite
    is_active = Column(Boolean, default=True, index=True)  # Whether enabled  # fcg-rewrite
    is_global = Column(Boolean, default=False, index=True)  # Whether it is a global config (deprecated, use source_type instead)  # fcg-rewrite
    source_type = Column(String(20), default='custom', index=True)  # Source type: 'system_template', 'system_copy', 'custom'  # fcg-rewrite
    template_id = Column(UUID(as_uuid=True), index=True, nullable=True)  # Template ID if copied from a template  # fcg-rewrite

    # GenAI code anonymization fields (for anonymization_method='genai_code')
    # These are used when the anonymization_method is 'genai_code' to execute custom AI-generated Python code
    restore_code = Column(Text, nullable=True)  # AI-generated Python code for genai_code anonymization  # fcg-rewrite
    restore_code_hash = Column(String(64), nullable=True)  # SHA-256 hash for code integrity verification  # fcg-rewrite
    restore_natural_desc = Column(Text, nullable=True)  # Natural language description used to generate the code  # fcg-rewrite

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application", back_populates="data_security_entity_types")  # fcg-rewrite

class TenantEntityTypeDisable(Base):  # fcg-rewrite
    """Tenant entity type disable table - supports application-level entity type disabling"""
    __tablename__ = "tenant_entity_type_disables"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=True, index=True)  # Optional: for application-level disable  # fcg-rewrite
    entity_type = Column(String(100), nullable=False, index=True)  # Entity type code, such as ID_CARD_NUMBER_SYS  # fcg-rewrite
    disabled_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application")  # fcg-rewrite

    # Unique constraint - includes application_id for application-level disabling
    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('tenant_id', 'application_id', 'entity_type', name='_tenant_app_entity_type_disable_uc'),  # fcg-rewrite
    )

class BanPolicy(Base):  # fcg-rewrite
    """Ban policy config table"""
    __tablename__ = "ban_policies"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Kept for backward compatibility  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # Associated application  # fcg-rewrite
    enabled = Column(Boolean, nullable=False, default=False)  # Whether ban policy is enabled  # fcg-rewrite
    risk_level = Column(String(20), nullable=False, default='high_risk')  # Risk level threshold (high_risk, medium_risk, low_risk)  # fcg-rewrite
    trigger_count = Column(Integer, nullable=False, default=3)  # Trigger count threshold (1-100)  # fcg-rewrite
    time_window_minutes = Column(Integer, nullable=False, default=10)  # Time window in minutes (1-1440)  # fcg-rewrite
    ban_duration_minutes = Column(Integer, nullable=False, default=60)  # Ban duration in minutes (1-10080)  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application", back_populates="ban_policies")  # fcg-rewrite

class UserBanRecord(Base):  # fcg-rewrite
    """User ban records table"""
    __tablename__ = "user_ban_records"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Kept for backward compatibility  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # Associated application  # fcg-rewrite
    user_id = Column(String(255), nullable=False)  # User identifier (from request header or custom field)  # fcg-rewrite
    banned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())  # fcg-rewrite
    ban_until = Column(DateTime(timezone=True), nullable=False)  # Ban expiration time  # fcg-rewrite
    trigger_count = Column(Integer, nullable=False)  # Number of risk triggers that led to ban  # fcg-rewrite
    risk_level = Column(String(20), nullable=False)  # Risk level that triggered the ban  # fcg-rewrite
    reason = Column(Text)  # Ban reason  # fcg-rewrite
    is_active = Column(Boolean, nullable=False, default=True)  # Whether ban is currently active  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application", back_populates="user_ban_records")  # fcg-rewrite

class UserRiskTrigger(Base):  # fcg-rewrite
    """User risk trigger history table"""
    __tablename__ = "user_risk_triggers"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # Kept for backward compatibility  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # Associated application  # fcg-rewrite
    user_id = Column(String(255), nullable=False)  # User identifier  # fcg-rewrite
    detection_result_id = Column(String(64))  # Associated detection result request ID  # fcg-rewrite
    risk_level = Column(String(20), nullable=False)  # Risk level of this trigger  # fcg-rewrite
    triggered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application", back_populates="user_risk_triggers")  # fcg-rewrite

class TenantKnowledgeBaseDisable(Base):  # fcg-rewrite
    """Tenant knowledge base disable table - allows tenants to disable global knowledge bases"""
    __tablename__ = "tenant_kb_disables"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # fcg-rewrite
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False, index=True)  # fcg-rewrite
    disabled_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    knowledge_base = relationship("KnowledgeBase")  # fcg-rewrite

    # Unique constraint
    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('tenant_id', 'kb_id', name='_tenant_kb_disable_uc'),  # fcg-rewrite
    )

class TenantSubscription(Base):  # fcg-rewrite
    """Tenant subscription and billing table"""
    __tablename__ = "tenant_subscriptions"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, unique=True, index=True)  # fcg-rewrite
    subscription_type = Column(String(20), nullable=False, default='free', index=True)  # 'free' or 'subscribed'  # fcg-rewrite
    monthly_quota = Column(Integer, nullable=False, default=1000)  # Monthly API call quota (default for free plan)  # fcg-rewrite
    current_month_usage = Column(Integer, nullable=False, default=0)  # Current month usage  # fcg-rewrite
    usage_reset_at = Column(DateTime(timezone=True), nullable=False)  # Next reset date (1st of next month)  # fcg-rewrite

    # Tier info
    subscription_tier = Column(Integer, default=0, index=True)  # tier 0 = free, 1-9 = paid tiers  # fcg-rewrite

    # Payment provider IDs
    stripe_customer_id = Column(String(255), index=True)  # Stripe customer ID  # fcg-rewrite
    alipay_user_id = Column(String(255), index=True)  # Alipay user ID  # fcg-rewrite
    alipay_agreement_no = Column(String(255))  # Alipay recurring billing agreement number (周期扣款)  # fcg-rewrite

    # Purchased quota (pay-per-use for Chinese users)
    purchased_quota = Column(Integer, default=0, nullable=False)  # fcg-rewrite
    purchased_quota_expires_at = Column(DateTime(timezone=True))  # fcg-rewrite

    # Subscription dates
    subscription_started_at = Column(DateTime(timezone=True))  # When subscription started  # fcg-rewrite
    subscription_expires_at = Column(DateTime(timezone=True))  # When subscription expires  # fcg-rewrite

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Association relationships
    tenant = relationship("Tenant")  # fcg-rewrite


class SubscriptionTier(Base):  # fcg-rewrite
    """Subscription tier reference table - defines available pricing tiers"""
    __tablename__ = "subscription_tiers"  # fcg-rewrite

    id = Column(Integer, primary_key=True, index=True)  # fcg-rewrite
    tier_number = Column(Integer, unique=True, nullable=False, index=True)  # fcg-rewrite
    tier_name = Column(String(100), nullable=False)  # fcg-rewrite
    monthly_quota = Column(Integer, nullable=False)  # fcg-rewrite
    price_usd = Column(Numeric(10, 2), nullable=False)  # fcg-rewrite
    price_cny = Column(Numeric(10, 2), nullable=False)  # fcg-rewrite
    is_active = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    display_order = Column(Integer, default=0)  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite


# =====================================================
# Scanner Package System Models
# =====================================================

class ScannerPackage(Base):  # fcg-rewrite
    """Scanner package metadata"""
    __tablename__ = "scanner_packages"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    package_code = Column(String(100), nullable=False, index=True)  # fcg-rewrite
    package_name = Column(String(200), nullable=False)  # fcg-rewrite
    author = Column(String(200), nullable=False, default='FangcunGuard')  # fcg-rewrite
    description = Column(Text)  # fcg-rewrite
    version = Column(String(50), nullable=False, default='1.0.0')  # fcg-rewrite
    license = Column(String(100), default='proprietary')  # fcg-rewrite

    # Package type
    package_type = Column(String(50), nullable=False)  # 'basic', 'premium' (formerly 'builtin', 'purchasable')  # fcg-rewrite
    is_official = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    requires_purchase = Column(Boolean, nullable=False, default=False)  # fcg-rewrite

    # Purchase settings (for premium packages)
    price = Column(Float, nullable=True)  # Original price as number for dynamic display  # fcg-rewrite
    price_display = Column(String(100))   # Fallback display text  # fcg-rewrite
    bundle = Column(String(100))          # Bundle name for grouping (e.g., Enterprise, Security)  # fcg-rewrite
    file_path = Column(String(512))  # fcg-rewrite

    # Metadata
    is_active = Column(Boolean, nullable=False, default=True, index=True)  # fcg-rewrite
    archived = Column(Boolean, nullable=False, default=False, index=True)  # Archive status  # fcg-rewrite
    archive_reason = Column(Text)  # Reason for archiving  # fcg-rewrite
    archived_at = Column(DateTime(timezone=True))  # Archive timestamp  # fcg-rewrite
    archived_by = Column(UUID(as_uuid=True), ForeignKey("tenants.id"))  # Admin who archived  # fcg-rewrite
    display_order = Column(Integer, default=0)  # fcg-rewrite
    scanner_count = Column(Integer, default=0)  # fcg-rewrite

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    scanners = relationship("Scanner", back_populates="package", cascade="all, delete-orphan")  # fcg-rewrite
    purchases = relationship("PackagePurchase", back_populates="package", cascade="all, delete-orphan")  # fcg-rewrite


class Scanner(Base):  # fcg-rewrite
    """Individual scanner definition"""
    __tablename__ = "scanners"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    package_id = Column(UUID(as_uuid=True), ForeignKey("scanner_packages.id", ondelete="CASCADE"))  # fcg-rewrite

    # Scanner identification
    tag = Column(String(50), unique=True, nullable=False, index=True)  # fcg-rewrite
    name = Column(String(200), nullable=False)  # fcg-rewrite
    description = Column(Text)  # fcg-rewrite

    # Scanner configuration
    scanner_type = Column(String(50), nullable=False)  # 'genai', 'regex', 'keyword'  # fcg-rewrite
    definition = Column(Text, nullable=False)  # fcg-rewrite

    # Default behavior (package defaults)
    default_risk_level = Column(String(20), nullable=False)  # 'high_risk', 'medium_risk', 'low_risk'  # fcg-rewrite
    default_scan_prompt = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    default_scan_response = Column(Boolean, nullable=False, default=True)  # fcg-rewrite

    # Metadata
    is_active = Column(Boolean, nullable=False, default=True, index=True)  # fcg-rewrite
    display_order = Column(Integer, default=0)  # fcg-rewrite

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    package = relationship("ScannerPackage", back_populates="scanners")  # fcg-rewrite
    configs = relationship("ApplicationScannerConfig", back_populates="scanner", cascade="all, delete-orphan")  # fcg-rewrite
    custom_scanners = relationship("CustomScanner", back_populates="scanner", cascade="all, delete-orphan")  # fcg-rewrite


class ApplicationScannerConfig(Base):  # fcg-rewrite
    """Per-application scanner configuration overrides"""
    __tablename__ = "application_scanner_configs"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    scanner_id = Column(UUID(as_uuid=True), ForeignKey("scanners.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite

    # Override settings (NULL = use package defaults)
    is_enabled = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    risk_level_override = Column(String(20))  # NULL = use default_risk_level  # fcg-rewrite
    scan_prompt_override = Column(Boolean)     # NULL = use default_scan_prompt  # fcg-rewrite
    scan_response_override = Column(Boolean)   # NULL = use default_scan_response  # fcg-rewrite

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    application = relationship("Application")  # fcg-rewrite
    scanner = relationship("Scanner", back_populates="configs")  # fcg-rewrite

    # Constraints
    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('application_id', 'scanner_id', name='uq_app_scanner_config'),  # fcg-rewrite
    )


class TenantDataLeakagePolicy(Base):  # fcg-rewrite
    """Tenant-level default data leakage prevention policies"""
    __tablename__ = "tenant_data_leakage_policies"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)  # fcg-rewrite

    # Input Policy Defaults (prevent external data leakage)
    # Actions: 'block' | 'switch_private_model' | 'anonymize' | 'pass'
    default_input_high_risk_action = Column(String(50), default='block', nullable=False)  # fcg-rewrite
    default_input_medium_risk_action = Column(String(50), default='anonymize', nullable=False)  # fcg-rewrite
    default_input_low_risk_action = Column(String(50), default='anonymize', nullable=False)  # fcg-rewrite

    # Output Policy Defaults (prevent internal unauthorized access)
    # Boolean flags: whether to anonymize output for each risk level (legacy, kept for backward compatibility)
    default_output_high_risk_anonymize = Column(Boolean, default=True, nullable=False)  # fcg-rewrite
    default_output_medium_risk_anonymize = Column(Boolean, default=True, nullable=False)  # fcg-rewrite
    default_output_low_risk_anonymize = Column(Boolean, default=False, nullable=False)  # fcg-rewrite

    # Output Policy Defaults - Action type (same as input policy)
    # Actions: 'block' | 'switch_private_model' | 'anonymize' | 'pass'
    default_output_high_risk_action = Column(String(50), default='block', nullable=False)  # fcg-rewrite
    default_output_medium_risk_action = Column(String(50), default='anonymize', nullable=False)  # fcg-rewrite
    default_output_low_risk_action = Column(String(50), default='pass', nullable=False)  # fcg-rewrite

    # General Risk Policy Defaults (security, safety, company policy violations)
    # Actions: 'block' | 'replace' (use knowledge base/template) | 'pass' (log only)
    # Legacy fields (kept for backward compatibility)
    default_general_high_risk_action = Column(String(50), default='block', nullable=False)  # fcg-rewrite
    default_general_medium_risk_action = Column(String(50), default='replace', nullable=False)  # fcg-rewrite
    default_general_low_risk_action = Column(String(50), default='pass', nullable=False)  # fcg-rewrite

    # General Risk Policy - Input Defaults
    default_general_input_high_risk_action = Column(String(50), default='block', nullable=False)  # fcg-rewrite
    default_general_input_medium_risk_action = Column(String(50), default='replace', nullable=False)  # fcg-rewrite
    default_general_input_low_risk_action = Column(String(50), default='pass', nullable=False)  # fcg-rewrite

    # General Risk Policy - Output Defaults
    default_general_output_high_risk_action = Column(String(50), default='block', nullable=False)  # fcg-rewrite
    default_general_output_medium_risk_action = Column(String(50), default='replace', nullable=False)  # fcg-rewrite
    default_general_output_low_risk_action = Column(String(50), default='pass', nullable=False)  # fcg-rewrite

    # Default Feature Flags
    default_enable_format_detection = Column(Boolean, default=True, nullable=False)  # fcg-rewrite
    default_enable_smart_segmentation = Column(Boolean, default=True, nullable=False)  # fcg-rewrite

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    tenant = relationship("Tenant", backref="data_leakage_policy")  # fcg-rewrite
    # Note: Default private model is determined by upstream_api_configs.is_default_private_model = true


class ApplicationDataLeakagePolicy(Base):  # fcg-rewrite
    """Application-level data leakage policy overrides. NULL values inherit from tenant defaults."""
    __tablename__ = "application_data_leakage_policies"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite

    # Input Policy Overrides (prevent external data leakage)
    # Actions: 'block' | 'switch_private_model' | 'anonymize' | 'pass'
    # NULL = use tenant default
    input_high_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite
    input_medium_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite
    input_low_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite

    # Output Policy Overrides (prevent internal unauthorized access)
    # Boolean flags: whether to anonymize output for each risk level (legacy, kept for backward compatibility)
    # NULL = use tenant default
    output_high_risk_anonymize = Column(Boolean, default=None, nullable=True)  # fcg-rewrite
    output_medium_risk_anonymize = Column(Boolean, default=None, nullable=True)  # fcg-rewrite
    output_low_risk_anonymize = Column(Boolean, default=None, nullable=True)  # fcg-rewrite

    # Output Policy Overrides - Action type (same as input policy)
    # Actions: 'block' | 'switch_private_model' | 'anonymize' | 'pass'
    # NULL = use tenant default
    output_high_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite
    output_medium_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite
    output_low_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite

    # General Risk Policy Overrides (security, safety, company policy violations)
    # Actions: 'block' | 'replace' (use knowledge base/template) | 'pass' (log only)
    # NULL = use tenant default
    # Legacy fields (kept for backward compatibility)
    general_high_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite
    general_medium_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite
    general_low_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite

    # General Risk Policy - Input Overrides
    general_input_high_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite
    general_input_medium_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite
    general_input_low_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite

    # General Risk Policy - Output Overrides
    general_output_high_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite
    general_output_medium_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite
    general_output_low_risk_action = Column(String(50), default=None, nullable=True)  # fcg-rewrite

    # Private model configuration (nullable if using tenant's default)
    private_model_id = Column(UUID(as_uuid=True), ForeignKey("upstream_api_configs.id", ondelete="SET NULL"), nullable=True)  # fcg-rewrite

    # Feature flags (NULL = use tenant default)
    enable_format_detection = Column(Boolean, default=None, nullable=True)  # fcg-rewrite
    enable_smart_segmentation = Column(Boolean, default=None, nullable=True)  # fcg-rewrite

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application")  # fcg-rewrite
    private_model = relationship("UpstreamApiConfig", foreign_keys=[private_model_id])  # fcg-rewrite

    # Constraints
    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('application_id', name='uq_application_data_leakage_policy'),  # fcg-rewrite
    )


class AgentSafetyPolicy(Base):  # fcg-rewrite
    """Per-application agent safety policy configuration"""
    __tablename__ = "agent_safety_policies"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite

    enabled = Column(Boolean, nullable=False, default=False)  # fcg-rewrite
    tool_whitelist = Column(JSON, default=None, nullable=True)  # NULL = allow all  # fcg-rewrite
    tool_blacklist = Column(JSON, default=list)  # [] = block none  # fcg-rewrite
    max_tool_calls_per_request = Column(Integer, nullable=False, default=20)  # fcg-rewrite
    enable_argument_inspection = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    argument_patterns = Column(JSON, default=list)  # Custom regex patterns  # fcg-rewrite
    enable_reasoning_safety = Column(Boolean, nullable=False, default=False)  # fcg-rewrite
    enable_tool_definition_scan = Column(Boolean, nullable=False, default=True)  # Scan JSON tool definitions  # fcg-rewrite
    tool_violation_action = Column(String(20), nullable=False, default='block')  # block|warn|log  # fcg-rewrite
    reasoning_violation_action = Column(String(20), nullable=False, default='warn')  # block|warn|log  # fcg-rewrite
    tool_definition_scan_action = Column(String(20), nullable=False, default='warn')  # block|warn|log  # fcg-rewrite

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application")  # fcg-rewrite

    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('application_id', name='uq_agent_safety_policy_app'),  # fcg-rewrite
    )


class HallucinationPolicy(Base):  # fcg-rewrite
    """Per-application hallucination detection policy"""
    __tablename__ = "hallucination_policies"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite

    enabled = Column(Boolean, nullable=False, default=False)  # fcg-rewrite
    enable_groundedness = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_consistency = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    groundedness_threshold = Column(Float, nullable=False, default=0.7)  # fcg-rewrite
    consistency_threshold = Column(Float, nullable=False, default=0.7)  # fcg-rewrite
    source_context_field = Column(String(100), nullable=False, default='system_message')  # system_message|extra_body.context|extra_body.documents  # fcg-rewrite
    violation_action = Column(String(20), nullable=False, default='flag')  # block|flag|warn|log  # fcg-rewrite

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application")  # fcg-rewrite

    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('application_id', name='uq_hallucination_policy_app'),  # fcg-rewrite
    )


class BasicGuardPolicy(Base):  # fcg-rewrite
    """Per-application basic guard policy"""
    __tablename__ = "basic_guard_policies"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite

    enabled = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_content_pattern_check = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_reasoning_divergence_check = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_output_anomaly_check = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    max_repetition_ratio = Column(Float, nullable=False, default=0.4)  # fcg-rewrite
    min_content_length = Column(Integer, nullable=False, default=10)  # fcg-rewrite
    violation_action = Column(String(20), nullable=False, default='warn')  # block|warn|log  # fcg-rewrite

    # Prompt Injection detection (Prompt Guard 2)
    enable_prompt_injection_check = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    prompt_injection_threshold = Column(Float, nullable=False, default=0.5)  # fcg-rewrite
    prompt_injection_action = Column(String(20), nullable=False, default='block')  # block|warn|log  # fcg-rewrite
    scan_user_messages = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    scan_system_messages = Column(Boolean, nullable=False, default=True)  # fcg-rewrite

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application")  # fcg-rewrite

    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('application_id', name='uq_basic_guard_policy_app'),  # fcg-rewrite
    )


class SkillScannerPolicy(Base):  # fcg-rewrite
    """Per-application skill scanner policy"""
    __tablename__ = "skill_scanner_policies"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite

    enabled = Column(Boolean, nullable=False, default=False)  # fcg-rewrite
    enable_static_pattern = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_structural_validation = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_capability_risk = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_llm_semantic = Column(Boolean, nullable=False, default=False)  # fcg-rewrite
    llm_auto_trigger_on_medium = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    policy_mode = Column(String(20), nullable=False, default='balanced')  # fcg-rewrite
    critical_action = Column(String(20), nullable=False, default='block')  # fcg-rewrite
    high_action = Column(String(20), nullable=False, default='warn')  # fcg-rewrite
    medium_action = Column(String(20), nullable=False, default='log')  # fcg-rewrite
    low_action = Column(String(20), nullable=False, default='log')  # fcg-rewrite
    custom_patterns = Column(JSON, default=list)  # fcg-rewrite
    dangerous_capability_keywords = Column(JSON, default=list)  # fcg-rewrite

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application")  # fcg-rewrite

    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('application_id', name='uq_skill_scanner_policy_app'),  # fcg-rewrite
    )


class McpScannerPolicy(Base):  # fcg-rewrite
    """Per-application MCP scanner policy"""
    __tablename__ = "mcp_scanner_policies"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite

    enabled = Column(Boolean, nullable=False, default=False)  # fcg-rewrite
    enable_yara_rules = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_llm_semantic = Column(Boolean, nullable=False, default=False)  # fcg-rewrite
    enable_behavior_analysis = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    llm_auto_trigger_on_medium = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_tool_scan = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_prompt_scan = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_resource_scan = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_instruction_scan = Column(Boolean, nullable=False, default=True)  # fcg-rewrite
    enable_supply_chain = Column(Boolean, nullable=False, default=False)  # fcg-rewrite
    policy_mode = Column(String(20), nullable=False, default='balanced')  # fcg-rewrite
    critical_action = Column(String(20), nullable=False, default='block')  # fcg-rewrite
    high_action = Column(String(20), nullable=False, default='warn')  # fcg-rewrite
    medium_action = Column(String(20), nullable=False, default='log')  # fcg-rewrite
    low_action = Column(String(20), nullable=False, default='log')  # fcg-rewrite
    custom_yara_rules = Column(JSON, default=list)  # fcg-rewrite
    trusted_servers = Column(JSON, default=list)  # fcg-rewrite

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application")  # fcg-rewrite

    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('application_id', name='uq_mcp_scanner_policy_app'),  # fcg-rewrite
    )


class ApplicationSettings(Base):  # fcg-rewrite
    """Application-level settings including fixed answer templates"""
    __tablename__ = "application_settings"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite

    # Fixed Answer Templates (stored as JSONB with language keys)
    # Format: {"en": "English template", "zh": "中文模板"}
    security_risk_template = Column(JSON, default={  # fcg-rewrite
        "en": "Request blocked by FangcunGuard due to possible violation of policy related to {scanner_name}.",  # fcg-rewrite
        "zh": "请求已被FangcunGuard拦截，原因：可能违反了与{scanner_name}有关的策略要求。"  # fcg-rewrite
    })
    data_leakage_template = Column(JSON, default={  # fcg-rewrite
        "en": "Request blocked by FangcunGuard due to possible sensitive data ({entity_type_names}).",  # fcg-rewrite
        "zh": "请求已被FangcunGuard拦截，原因：可能包含敏感数据（{entity_type_names}）。"  # fcg-rewrite
    })

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application")  # fcg-rewrite

    # Constraints
    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('application_id', name='uq_application_settings_app'),  # fcg-rewrite
    )


class PackagePurchase(Base):  # fcg-rewrite
    """
    Package purchase tracking.
    
    Modern flow (with payment system):
    - Paid packages: Payment completed -> auto-approved (status='approved')
    - Free packages: Direct purchase -> auto-approved (status='approved')
    
    Legacy flow (deprecated):
    - Manual request -> admin review -> approved/rejected
    """
    __tablename__ = "package_purchases"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    package_id = Column(UUID(as_uuid=True), ForeignKey("scanner_packages.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite

    # Purchase lifecycle
    status = Column(String(50), nullable=False, default='pending', index=True)  # 'pending', 'approved', 'rejected'  # fcg-rewrite
    request_email = Column(String(255))  # fcg-rewrite
    request_message = Column(Text)  # fcg-rewrite

    # Admin actions (used in legacy manual approval flow)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("tenants.id"))  # fcg-rewrite
    approved_at = Column(DateTime(timezone=True))  # fcg-rewrite
    rejection_reason = Column(Text)  # fcg-rewrite

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    tenant = relationship("Tenant", foreign_keys=[tenant_id])  # fcg-rewrite
    package = relationship("ScannerPackage", back_populates="purchases")  # fcg-rewrite
    approver = relationship("Tenant", foreign_keys=[approved_by])  # fcg-rewrite

    # Constraints
    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('tenant_id', 'package_id', name='uq_tenant_package_purchase'),  # fcg-rewrite
    )


class CustomScanner(Base):  # fcg-rewrite
    """User-defined custom scanners (S100+)"""
    __tablename__ = "custom_scanners"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    scanner_id = Column(UUID(as_uuid=True), ForeignKey("scanners.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    created_by = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)  # fcg-rewrite

    # Custom scanner metadata
    notes = Column(Text)  # fcg-rewrite

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    application = relationship("Application")  # fcg-rewrite
    scanner = relationship("Scanner", back_populates="custom_scanners")  # fcg-rewrite
    creator = relationship("Tenant")  # fcg-rewrite

    # Constraints
    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('application_id', 'scanner_id', name='uq_app_custom_scanner'),  # fcg-rewrite
    )


# =====================================================
# Payment System Models
# =====================================================

class PaymentOrder(Base):  # fcg-rewrite
    """Payment order table - stores all payment transactions"""
    __tablename__ = "payment_orders"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    order_type = Column(String(50), nullable=False, index=True)  # 'subscription' or 'package'  # fcg-rewrite
    amount = Column(Float, nullable=False)  # fcg-rewrite
    currency = Column(String(10), nullable=False)  # 'CNY' or 'USD'  # fcg-rewrite
    payment_provider = Column(String(50), nullable=False, index=True)  # 'alipay' or 'stripe'  # fcg-rewrite
    status = Column(String(50), nullable=False, default='pending', index=True)  # 'pending', 'paid', 'failed', 'refunded', 'cancelled'  # fcg-rewrite

    # Provider-specific IDs
    provider_order_id = Column(String(255), index=True)  # Our order ID sent to provider  # fcg-rewrite
    provider_transaction_id = Column(String(255), index=True)  # Transaction ID from provider  # fcg-rewrite

    # For package purchases
    package_id = Column(UUID(as_uuid=True), ForeignKey("scanner_packages.id", ondelete="SET NULL"), index=True)  # fcg-rewrite

    # Additional metadata
    order_metadata = Column(JSON, default={})  # fcg-rewrite

    # Timestamps
    paid_at = Column(DateTime(timezone=True))  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    package = relationship("ScannerPackage")  # fcg-rewrite


class SubscriptionPayment(Base):  # fcg-rewrite
    """Subscription payment table - tracks recurring subscription payments"""
    __tablename__ = "subscription_payments"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    payment_order_id = Column(UUID(as_uuid=True), ForeignKey("payment_orders.id", ondelete="SET NULL"), index=True)  # fcg-rewrite

    # Billing cycle
    billing_cycle_start = Column(DateTime(timezone=True), nullable=False)  # fcg-rewrite
    billing_cycle_end = Column(DateTime(timezone=True), nullable=False)  # fcg-rewrite

    # Provider-specific subscription IDs
    stripe_subscription_id = Column(String(255), index=True)  # fcg-rewrite
    stripe_customer_id = Column(String(255), index=True)  # fcg-rewrite
    alipay_agreement_id = Column(String(255), index=True)  # fcg-rewrite

    # Status
    status = Column(String(50), nullable=False, default='active', index=True)  # 'active', 'cancelled', 'expired', 'past_due'  # fcg-rewrite
    cancel_at_period_end = Column(Boolean, default=False)  # fcg-rewrite

    # Next payment info
    next_payment_date = Column(DateTime(timezone=True), index=True)  # fcg-rewrite
    next_payment_amount = Column(Float)  # fcg-rewrite

    # Timestamps
    cancelled_at = Column(DateTime(timezone=True))  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    payment_order = relationship("PaymentOrder")  # fcg-rewrite


# =====================================================
# Appeal System Models
# =====================================================

class AppealConfig(Base):  # fcg-rewrite
    """Appeal configuration table - per-application settings for false positive appeals"""
    __tablename__ = "appeal_config"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    enabled = Column(Boolean, nullable=False, default=False)  # fcg-rewrite
    # Template for appeal link message, supports {appeal_url} placeholder
    # Note: Default value uses English. Localized defaults are provided via i18n when config is first displayed.
    message_template = Column(Text, nullable=False, default='If you think this is a false positive, please click the following link to appeal: {appeal_url}')  # fcg-rewrite
    # Base URL for appeal links (e.g., https://domain.com or http://192.168.1.100:5001)
    appeal_base_url = Column(String(512), nullable=False, default='')  # fcg-rewrite
    # Final reviewer email - when AI considers it a true positive, send email for human review
    final_reviewer_email = Column(String(255), nullable=True)  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application", back_populates="appeal_config")  # fcg-rewrite

    # Constraints
    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('application_id', name='uq_appeal_config_application'),  # fcg-rewrite
    )


class AppealRecord(Base):  # fcg-rewrite
    """Appeal records table - tracks false positive appeal requests and reviews"""
    __tablename__ = "appeal_records"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    request_id = Column(String(64), nullable=False, unique=True, index=True)  # Original detection request_id (guardrails-xxx)  # fcg-rewrite
    user_id = Column(String(255), index=True)  # User who triggered the detection  # fcg-rewrite

    # Original detection info (denormalized for review)
    original_content = Column(Text, nullable=False)  # fcg-rewrite
    original_risk_level = Column(String(20), nullable=False)  # fcg-rewrite
    original_categories = Column(JSON, nullable=False)  # fcg-rewrite
    original_suggest_action = Column(String(20), nullable=False)  # fcg-rewrite

    # Review status: pending, reviewing, pending_review, approved, rejected
    # pending_review: AI rejected, waiting for human final review
    status = Column(String(20), nullable=False, default='pending', index=True)  # fcg-rewrite

    # AI review results
    ai_review_result = Column(Text)  # AI reasoning output  # fcg-rewrite
    ai_approved = Column(Boolean)  # AI decision: true=false positive confirmed (NOT actual violation)  # fcg-rewrite
    ai_reviewed_at = Column(DateTime(timezone=True))  # fcg-rewrite

    # Human review fields
    processor_type = Column(String(20), nullable=True)  # 'agent' | 'human'  # fcg-rewrite
    processor_id = Column(String(255), nullable=True)  # Human reviewer identifier (email prefix)  # fcg-rewrite
    processor_reason = Column(Text, nullable=True)  # Human reviewer's reason (optional)  # fcg-rewrite
    processed_at = Column(DateTime(timezone=True))  # When the appeal was finally processed  # fcg-rewrite

    # Content hash for duplicate detection
    content_hash = Column(String(64), nullable=True, index=True)  # fcg-rewrite

    # Context for review
    user_recent_requests = Column(JSON)  # Recent 10 requests from this user  # fcg-rewrite
    user_ban_history = Column(JSON)  # User's ban records if any  # fcg-rewrite

    # Whitelist addition
    whitelist_id = Column(Integer, ForeignKey("whitelist.id", ondelete="SET NULL"))  # fcg-rewrite
    whitelist_keyword = Column(Text)  # The specific keyword/phrase added  # fcg-rewrite

    # Metadata
    ip_address = Column(String(45))  # fcg-rewrite
    user_agent = Column(Text)  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    application = relationship("Application", back_populates="appeal_records")  # fcg-rewrite
    whitelist = relationship("Whitelist")  # fcg-rewrite


# =====================================================
# Model Routing System Models
# =====================================================

class ModelRoute(Base):  # fcg-rewrite
    """Model routing rules for automatic upstream API selection based on model name patterns"""
    __tablename__ = "model_routes"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    name = Column(String(200), nullable=False)  # fcg-rewrite
    description = Column(Text)  # fcg-rewrite
    model_pattern = Column(String(255), nullable=False)  # Model name pattern (e.g., "gpt-4", "claude")  # fcg-rewrite
    match_type = Column(String(20), nullable=False, default='prefix')  # 'exact' | 'prefix'  # fcg-rewrite
    upstream_api_config_id = Column(UUID(as_uuid=True), ForeignKey("upstream_api_configs.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    priority = Column(Integer, nullable=False, default=100)  # Priority, higher number = higher priority  # fcg-rewrite
    is_active = Column(Boolean, nullable=False, default=True, index=True)  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # fcg-rewrite

    # Relationships
    tenant = relationship("Tenant")  # fcg-rewrite
    upstream_api_config = relationship("UpstreamApiConfig")  # fcg-rewrite
    route_applications = relationship("ModelRouteApplication", back_populates="model_route", cascade="all, delete-orphan")  # fcg-rewrite

    # Constraints
    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('tenant_id', 'model_pattern', 'match_type', name='uq_model_routes_tenant_pattern'),  # fcg-rewrite
    )


class ModelRouteApplication(Base):  # fcg-rewrite
    """Optional per-application route bindings. Routes without entries here apply to all applications."""
    __tablename__ = "model_route_applications"  # fcg-rewrite

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)  # fcg-rewrite
    model_route_id = Column(UUID(as_uuid=True), ForeignKey("model_routes.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)  # fcg-rewrite
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # fcg-rewrite

    # Relationships
    model_route = relationship("ModelRoute", back_populates="route_applications")  # fcg-rewrite
    application = relationship("Application")  # fcg-rewrite

    # Constraints
    __table_args__ = (  # fcg-rewrite
        UniqueConstraint('model_route_id', 'application_id', name='uq_model_route_applications'),  # fcg-rewrite
    )



