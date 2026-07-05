-- FangcunGuard Platform - PostgreSQL database initialization script -- fcg-rewrite
-- Complete database schema with all migrations merged -- fcg-rewrite
-- Version: 2.3.0+ -- fcg-rewrite
-- Last updated: 2025-10-20 -- fcg-rewrite

-- Create necessary extensions -- fcg-rewrite
CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- CORE TABLES -- fcg-rewrite
-- ============================================================ -- fcg-rewrite

-- Tenants table (formerly users table) -- fcg-rewrite
CREATE TABLE IF NOT EXISTS tenants ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- fcg-rewrite
    email VARCHAR(255) UNIQUE NOT NULL, -- fcg-rewrite
    password_hash VARCHAR(128) NOT NULL, -- fcg-rewrite
    is_super_admin BOOLEAN DEFAULT FALSE, -- fcg-rewrite
    is_active BOOLEAN DEFAULT FALSE, -- fcg-rewrite
    is_verified BOOLEAN DEFAULT FALSE, -- fcg-rewrite
    api_key VARCHAR(64) UNIQUE NOT NULL, -- fcg-rewrite
    language VARCHAR(10) DEFAULT 'en' NOT NULL, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Email verification table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS email_verifications ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    email VARCHAR(255) NOT NULL, -- fcg-rewrite
    verification_code VARCHAR(6) NOT NULL, -- fcg-rewrite
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, -- fcg-rewrite
    is_used BOOLEAN DEFAULT FALSE, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Login attempts table (for anti-brute force) -- fcg-rewrite
CREATE TABLE IF NOT EXISTS login_attempts ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    email VARCHAR(255) NOT NULL, -- fcg-rewrite
    ip_address VARCHAR(45) NOT NULL, -- fcg-rewrite
    user_agent TEXT, -- fcg-rewrite
    success BOOLEAN DEFAULT FALSE, -- fcg-rewrite
    attempted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- System config table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS system_config ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    config_key VARCHAR(100) UNIQUE NOT NULL, -- fcg-rewrite
    config_value TEXT, -- fcg-rewrite
    description TEXT, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Tenant switches table (for super admin to switch tenant perspective) -- fcg-rewrite
CREATE TABLE IF NOT EXISTS tenant_switches ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    admin_tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    target_tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    switch_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    session_token VARCHAR(128) UNIQUE NOT NULL, -- fcg-rewrite
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, -- fcg-rewrite
    is_active BOOLEAN DEFAULT TRUE -- fcg-rewrite
); -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- DETECTION AND SECURITY TABLES -- fcg-rewrite
-- ============================================================ -- fcg-rewrite

-- Detection results table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS detection_results ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    request_id VARCHAR(64) UNIQUE NOT NULL, -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    content TEXT NOT NULL, -- fcg-rewrite
    suggest_action VARCHAR(20) DEFAULT 'pass', -- fcg-rewrite
    suggest_answer TEXT, -- fcg-rewrite
    hit_keywords TEXT, -- fcg-rewrite
    model_response TEXT, -- fcg-rewrite
    ip_address VARCHAR(45), -- fcg-rewrite
    user_agent TEXT, -- fcg-rewrite
    -- Risk levels (English values with extended length) -- fcg-rewrite
    security_risk_level VARCHAR(20) DEFAULT 'no_risk', -- fcg-rewrite
    security_categories JSONB DEFAULT '[]', -- fcg-rewrite
    compliance_risk_level VARCHAR(20) DEFAULT 'no_risk', -- fcg-rewrite
    compliance_categories JSONB DEFAULT '[]', -- fcg-rewrite
    data_risk_level VARCHAR(20) DEFAULT 'no_risk', -- fcg-rewrite
    data_categories JSONB DEFAULT '[]', -- fcg-rewrite
    -- Confidence/Sensitivity fields -- fcg-rewrite
    confidence_level VARCHAR(10), -- fcg-rewrite
    confidence_score FLOAT, -- fcg-rewrite
    -- Multimodal fields -- fcg-rewrite
    has_image BOOLEAN DEFAULT FALSE, -- fcg-rewrite
    image_count INTEGER DEFAULT 0, -- fcg-rewrite
    image_paths JSONB DEFAULT '[]', -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Blacklist table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS blacklist ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    name VARCHAR(100) NOT NULL, -- fcg-rewrite
    keywords JSONB NOT NULL, -- fcg-rewrite
    description TEXT, -- fcg-rewrite
    is_active BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Whitelist table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS whitelist ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    name VARCHAR(100) NOT NULL, -- fcg-rewrite
    keywords JSONB NOT NULL, -- fcg-rewrite
    description TEXT, -- fcg-rewrite
    is_active BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Response templates table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS response_templates ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    category VARCHAR(50) NOT NULL, -- fcg-rewrite
    risk_level VARCHAR(20) NOT NULL, -- fcg-rewrite
    template_content TEXT NOT NULL, -- fcg-rewrite
    is_default BOOLEAN DEFAULT FALSE, -- fcg-rewrite
    is_active BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Risk type config table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS risk_type_config ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE UNIQUE NOT NULL, -- fcg-rewrite
    -- S1-S12 risk type switches -- fcg-rewrite
    s1_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    s2_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    s3_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    s4_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    s5_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    s6_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    s7_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    s8_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    s9_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    s10_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    s11_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    s12_enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    -- S1-S12 confidence thresholds -- fcg-rewrite
    s1_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    s2_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    s3_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    s4_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    s5_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    s6_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    s7_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    s8_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    s9_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    s10_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    s11_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    s12_confidence_threshold FLOAT DEFAULT 0.90, -- fcg-rewrite
    -- Global sensitivity thresholds -- fcg-rewrite
    high_sensitivity_threshold FLOAT DEFAULT 0.40, -- fcg-rewrite
    medium_sensitivity_threshold FLOAT DEFAULT 0.60, -- fcg-rewrite
    low_sensitivity_threshold FLOAT DEFAULT 0.95, -- fcg-rewrite
    -- Sensitivity trigger level (low, medium, high) -- fcg-rewrite
    sensitivity_trigger_level VARCHAR(10) DEFAULT 'medium', -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- DATA SECURITY TABLES -- fcg-rewrite
-- ============================================================ -- fcg-rewrite

-- Data security entity types table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS data_security_entity_types ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    entity_type VARCHAR(100) NOT NULL, -- fcg-rewrite
    entity_type_name VARCHAR(200) NOT NULL, -- fcg-rewrite
    category VARCHAR(50) NOT NULL, -- fcg-rewrite
    recognition_method VARCHAR(20) NOT NULL, -- fcg-rewrite
    recognition_config JSONB NOT NULL, -- fcg-rewrite
    anonymization_method VARCHAR(20) DEFAULT 'replace', -- fcg-rewrite
    anonymization_config JSONB, -- fcg-rewrite
    is_active BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    is_global BOOLEAN DEFAULT FALSE, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Tenant entity type disables table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS tenant_entity_type_disables ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    entity_type VARCHAR(100) NOT NULL, -- fcg-rewrite
    disabled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    UNIQUE(tenant_id, entity_type) -- fcg-rewrite
); -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- BAN POLICY TABLES -- fcg-rewrite
-- ============================================================ -- fcg-rewrite

-- Ban policies table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS ban_policies ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    enabled BOOLEAN NOT NULL DEFAULT FALSE, -- fcg-rewrite
    risk_level VARCHAR(20) NOT NULL DEFAULT 'high_risk', -- fcg-rewrite
    trigger_count INTEGER NOT NULL DEFAULT 3, -- fcg-rewrite
    time_window_minutes INTEGER NOT NULL DEFAULT 10, -- fcg-rewrite
    ban_duration_minutes INTEGER NOT NULL DEFAULT 60, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    CONSTRAINT check_risk_level CHECK (risk_level IN ('high_risk', 'medium_risk', 'low_risk')), -- fcg-rewrite
    CONSTRAINT check_trigger_count CHECK (trigger_count >= 1 AND trigger_count <= 100), -- fcg-rewrite
    CONSTRAINT check_time_window CHECK (time_window_minutes >= 1 AND time_window_minutes <= 1440), -- fcg-rewrite
    CONSTRAINT check_ban_duration CHECK (ban_duration_minutes >= 1 AND ban_duration_minutes <= 10080) -- fcg-rewrite
); -- fcg-rewrite

-- User ban records table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS user_ban_records ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    user_id VARCHAR(255) NOT NULL, -- fcg-rewrite
    banned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(), -- fcg-rewrite
    ban_until TIMESTAMP WITH TIME ZONE NOT NULL, -- fcg-rewrite
    trigger_count INTEGER NOT NULL, -- fcg-rewrite
    risk_level VARCHAR(20) NOT NULL, -- fcg-rewrite
    reason TEXT, -- fcg-rewrite
    is_active BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- User risk triggers table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS user_risk_triggers ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    user_id VARCHAR(255) NOT NULL, -- fcg-rewrite
    detection_result_id VARCHAR(64), -- fcg-rewrite
    risk_level VARCHAR(20) NOT NULL, -- fcg-rewrite
    triggered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(), -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- RATE LIMITING TABLES -- fcg-rewrite
-- ============================================================ -- fcg-rewrite

-- Tenant rate limits table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS tenant_rate_limits ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE UNIQUE NOT NULL, -- fcg-rewrite
    requests_per_second INTEGER DEFAULT 1 NOT NULL, -- fcg-rewrite
    is_active BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Tenant rate limit counters table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS tenant_rate_limit_counters ( -- fcg-rewrite
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    current_count INTEGER DEFAULT 0 NOT NULL, -- fcg-rewrite
    window_start TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL, -- fcg-rewrite
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL -- fcg-rewrite
); -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- MODEL CONFIGURATION TABLES -- fcg-rewrite
-- ============================================================ -- fcg-rewrite

-- Test model configs table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS test_model_configs ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    name VARCHAR(255) NOT NULL, -- fcg-rewrite
    base_url VARCHAR(512) NOT NULL, -- fcg-rewrite
    api_key VARCHAR(512) NOT NULL, -- fcg-rewrite
    model_name VARCHAR(255) NOT NULL, -- fcg-rewrite
    enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Proxy model configs table (simplified design) -- fcg-rewrite
CREATE TABLE IF NOT EXISTS proxy_model_configs ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    config_name VARCHAR(100) NOT NULL, -- fcg-rewrite
    api_base_url VARCHAR(512) NOT NULL, -- fcg-rewrite
    api_key_encrypted TEXT NOT NULL, -- fcg-rewrite
    model_name VARCHAR(255) NOT NULL, -- fcg-rewrite
    enabled BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    -- Security config (simplified) -- fcg-rewrite
    enable_reasoning_detection BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    -- Stream and confidence config -- fcg-rewrite
    stream_chunk_size INTEGER DEFAULT 50, -- fcg-rewrite
    confidence_trigger_level VARCHAR(10) DEFAULT 'medium', -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    CONSTRAINT check_stream_chunk_size_range CHECK (stream_chunk_size >= 1 AND stream_chunk_size <= 500), -- fcg-rewrite
    CONSTRAINT check_confidence_trigger_level_values CHECK (confidence_trigger_level IN ('high', 'medium', 'low')) -- fcg-rewrite
); -- fcg-rewrite

-- Proxy request logs table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS proxy_request_logs ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- fcg-rewrite
    request_id VARCHAR(64) UNIQUE NOT NULL, -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    proxy_config_id UUID REFERENCES proxy_model_configs(id) ON DELETE CASCADE, -- fcg-rewrite
    -- Request information -- fcg-rewrite
    model_requested VARCHAR(255) NOT NULL, -- fcg-rewrite
    model_used VARCHAR(255) NOT NULL, -- fcg-rewrite
    provider VARCHAR(50) NOT NULL, -- fcg-rewrite
    -- Detection results -- fcg-rewrite
    input_detection_id VARCHAR(64), -- fcg-rewrite
    output_detection_id VARCHAR(64), -- fcg-rewrite
    input_blocked BOOLEAN DEFAULT FALSE, -- fcg-rewrite
    output_blocked BOOLEAN DEFAULT FALSE, -- fcg-rewrite
    -- Statistics -- fcg-rewrite
    request_tokens INTEGER, -- fcg-rewrite
    response_tokens INTEGER, -- fcg-rewrite
    total_tokens INTEGER, -- fcg-rewrite
    response_time_ms INTEGER, -- fcg-rewrite
    -- Status -- fcg-rewrite
    status VARCHAR(20) NOT NULL, -- fcg-rewrite
    error_message TEXT, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Online test model selections table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS online_test_model_selections ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    proxy_model_id UUID REFERENCES proxy_model_configs(id) ON DELETE CASCADE, -- fcg-rewrite
    selected BOOLEAN DEFAULT FALSE NOT NULL, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    UNIQUE(tenant_id, proxy_model_id) -- fcg-rewrite
); -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- KNOWLEDGE BASE TABLES -- fcg-rewrite
-- ============================================================ -- fcg-rewrite

-- Knowledge bases table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS knowledge_bases ( -- fcg-rewrite
    id SERIAL PRIMARY KEY, -- fcg-rewrite
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    category VARCHAR(50) NOT NULL, -- fcg-rewrite
    name VARCHAR(255) NOT NULL, -- fcg-rewrite
    description TEXT, -- fcg-rewrite
    file_path VARCHAR(512) NOT NULL, -- fcg-rewrite
    vector_file_path VARCHAR(512), -- fcg-rewrite
    total_qa_pairs INTEGER DEFAULT 0, -- fcg-rewrite
    is_active BOOLEAN DEFAULT TRUE, -- fcg-rewrite
    is_global BOOLEAN DEFAULT FALSE NOT NULL, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- INDEXES -- fcg-rewrite
-- ============================================================ -- fcg-rewrite

-- Tenants indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_tenants_email ON tenants(email); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_tenants_api_key ON tenants(api_key); -- fcg-rewrite

-- Email verifications indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_email_verifications_email ON email_verifications(email); -- fcg-rewrite

-- Login attempts indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_login_attempts_email ON login_attempts(email); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_login_attempts_success ON login_attempts(success); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_login_attempts_attempted_at ON login_attempts(attempted_at); -- fcg-rewrite

-- Detection results indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_detection_results_tenant_id ON detection_results(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_detection_results_request_id ON detection_results(request_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_detection_results_created_at ON detection_results(created_at); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_detection_results_has_image ON detection_results(has_image); -- fcg-rewrite

-- Blacklist indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_blacklist_tenant_id ON blacklist(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_blacklist_is_active ON blacklist(is_active); -- fcg-rewrite

-- Whitelist indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_whitelist_tenant_id ON whitelist(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_whitelist_is_active ON whitelist(is_active); -- fcg-rewrite

-- Response templates indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_response_templates_tenant_id ON response_templates(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_response_templates_category ON response_templates(category); -- fcg-rewrite

-- Risk type config indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_risk_type_config_tenant_id ON risk_type_config(tenant_id); -- fcg-rewrite

-- Data security entity types indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_data_security_entity_types_tenant_id ON data_security_entity_types(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_data_security_entity_types_entity_type ON data_security_entity_types(entity_type); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_data_security_entity_types_category ON data_security_entity_types(category); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_data_security_entity_types_is_active ON data_security_entity_types(is_active); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_data_security_entity_types_is_global ON data_security_entity_types(is_global); -- fcg-rewrite

-- Tenant entity type disables indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_tenant_entity_type_disables_tenant_id ON tenant_entity_type_disables(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_tenant_entity_type_disables_entity_type ON tenant_entity_type_disables(entity_type); -- fcg-rewrite

-- Ban policies indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_ban_policies_tenant ON ban_policies(tenant_id); -- fcg-rewrite

-- User ban records indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_user_ban_records_tenant_user ON user_ban_records(tenant_id, user_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_user_ban_records_active ON user_ban_records(tenant_id, user_id, is_active) WHERE is_active = TRUE; -- fcg-rewrite

-- User risk triggers indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_user_risk_triggers_tenant_user_time ON user_risk_triggers(tenant_id, user_id, triggered_at); -- fcg-rewrite

-- Tenant rate limits indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_tenant_rate_limits_tenant_id ON tenant_rate_limits(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_tenant_rate_limits_is_active ON tenant_rate_limits(is_active); -- fcg-rewrite

-- Test model configs indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_test_model_configs_tenant_id ON test_model_configs(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_test_model_configs_enabled ON test_model_configs(enabled); -- fcg-rewrite

-- Proxy model configs indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_proxy_model_configs_tenant_id ON proxy_model_configs(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_proxy_model_configs_config_name ON proxy_model_configs(config_name); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_proxy_model_configs_enabled ON proxy_model_configs(enabled); -- fcg-rewrite

-- Proxy request logs indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_proxy_request_logs_request_id ON proxy_request_logs(request_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_proxy_request_logs_tenant_id ON proxy_request_logs(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_proxy_request_logs_input_detection_id ON proxy_request_logs(input_detection_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_proxy_request_logs_output_detection_id ON proxy_request_logs(output_detection_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_proxy_request_logs_created_at ON proxy_request_logs(created_at); -- fcg-rewrite

-- Online test model selections indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_online_test_model_selections_tenant_id ON online_test_model_selections(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_online_test_model_selections_proxy_model_id ON online_test_model_selections(proxy_model_id); -- fcg-rewrite

-- Knowledge bases indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_tenant_id ON knowledge_bases(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_category ON knowledge_bases(category); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_is_active ON knowledge_bases(is_active); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_is_global ON knowledge_bases(is_global); -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- TRIGGERS AND FUNCTIONS -- fcg-rewrite
-- ============================================================ -- fcg-rewrite

-- Update timestamp function -- fcg-rewrite
CREATE OR REPLACE FUNCTION update_updated_at_column() -- fcg-rewrite
RETURNS TRIGGER AS $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    NEW.updated_at = NOW(); -- fcg-rewrite
    RETURN NEW; -- fcg-rewrite
END; -- fcg-rewrite
$$ language 'plpgsql'; -- fcg-rewrite

-- Create triggers for updated_at columns -- fcg-rewrite
CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

CREATE TRIGGER update_blacklist_updated_at BEFORE UPDATE ON blacklist -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

CREATE TRIGGER update_whitelist_updated_at BEFORE UPDATE ON whitelist -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

CREATE TRIGGER update_response_templates_updated_at BEFORE UPDATE ON response_templates -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

CREATE TRIGGER update_risk_type_config_updated_at BEFORE UPDATE ON risk_type_config -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

CREATE TRIGGER update_tenant_rate_limits_updated_at BEFORE UPDATE ON tenant_rate_limits -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

CREATE TRIGGER update_test_model_configs_updated_at BEFORE UPDATE ON test_model_configs -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

CREATE TRIGGER update_proxy_model_configs_updated_at BEFORE UPDATE ON proxy_model_configs -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

CREATE TRIGGER update_knowledge_bases_updated_at BEFORE UPDATE ON knowledge_bases -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

CREATE TRIGGER update_data_security_entity_types_updated_at BEFORE UPDATE ON data_security_entity_types -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

CREATE TRIGGER update_tenant_entity_type_disables_updated_at BEFORE UPDATE ON tenant_entity_type_disables -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

CREATE TRIGGER update_online_test_model_selections_updated_at BEFORE UPDATE ON online_test_model_selections -- fcg-rewrite
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite

-- Ban policy triggers -- fcg-rewrite
CREATE OR REPLACE FUNCTION update_ban_policies_updated_at() -- fcg-rewrite
RETURNS TRIGGER AS $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    NEW.updated_at = NOW(); -- fcg-rewrite
    RETURN NEW; -- fcg-rewrite
END; -- fcg-rewrite
$$ LANGUAGE plpgsql; -- fcg-rewrite

CREATE TRIGGER ban_policies_updated_at -- fcg-rewrite
    BEFORE UPDATE ON ban_policies -- fcg-rewrite
    FOR EACH ROW -- fcg-rewrite
    EXECUTE FUNCTION update_ban_policies_updated_at(); -- fcg-rewrite

CREATE OR REPLACE FUNCTION update_user_ban_records_updated_at() -- fcg-rewrite
RETURNS TRIGGER AS $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    NEW.updated_at = NOW(); -- fcg-rewrite
    RETURN NEW; -- fcg-rewrite
END; -- fcg-rewrite
$$ LANGUAGE plpgsql; -- fcg-rewrite

CREATE TRIGGER user_ban_records_updated_at -- fcg-rewrite
    BEFORE UPDATE ON user_ban_records -- fcg-rewrite
    FOR EACH ROW -- fcg-rewrite
    EXECUTE FUNCTION update_user_ban_records_updated_at(); -- fcg-rewrite

-- Ban policy utility functions -- fcg-rewrite
CREATE OR REPLACE FUNCTION deactivate_expired_bans() -- fcg-rewrite
RETURNS void AS $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    UPDATE user_ban_records -- fcg-rewrite
    SET is_active = FALSE -- fcg-rewrite
    WHERE is_active = TRUE -- fcg-rewrite
    AND ban_until < NOW(); -- fcg-rewrite
END; -- fcg-rewrite
$$ LANGUAGE plpgsql; -- fcg-rewrite

CREATE OR REPLACE FUNCTION cleanup_old_risk_triggers() -- fcg-rewrite
RETURNS void AS $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    DELETE FROM user_risk_triggers -- fcg-rewrite
    WHERE triggered_at < NOW() - INTERVAL '7 days'; -- fcg-rewrite
END; -- fcg-rewrite
$$ LANGUAGE plpgsql; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- DEFAULT DATA -- fcg-rewrite
-- ============================================================ -- fcg-rewrite

-- Insert default admin tenant (password: admin123456) -- fcg-rewrite
INSERT INTO tenants (email, password_hash, is_super_admin, is_verified, is_active, api_key) -- fcg-rewrite
VALUES ( -- fcg-rewrite
    'admin@fangcunguard.com', -- fcg-rewrite
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewlDBqUJwgN3k6Nm', -- fcg-rewrite
    true, -- fcg-rewrite
    true, -- fcg-rewrite
    true, -- fcg-rewrite
    'sk-admin-' || substring(md5(random()::text) from 1 for 32) -- fcg-rewrite
) -- fcg-rewrite
ON CONFLICT (email) DO NOTHING; -- fcg-rewrite

-- Insert default response templates (English values) -- fcg-rewrite
INSERT INTO response_templates (tenant_id, category, risk_level, template_content, is_default, is_active) -- fcg-rewrite
VALUES -- fcg-rewrite
    (null, 'default', 'high_risk', 'I apologize, but I cannot answer your question. If you have other questions, I would be happy to help.', true, true), -- fcg-rewrite
    (null, 'default', 'medium_risk', 'I apologize, but I cannot provide relevant information. Let''s change the subject, I can introduce you to other interesting content.', true, true), -- fcg-rewrite
    (null, 'default', 'low_risk', 'Let''s maintain a friendly communication environment, I can provide you with other useful information.', true, true) -- fcg-rewrite
ON CONFLICT DO NOTHING; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- COMMENTS -- fcg-rewrite
-- ============================================================ -- fcg-rewrite

COMMENT ON TABLE tenants IS 'Tenant table (formerly users table)'; -- fcg-rewrite
COMMENT ON TABLE email_verifications IS 'Email verification table'; -- fcg-rewrite
COMMENT ON TABLE login_attempts IS 'Login attempt record table (for anti-brute force)'; -- fcg-rewrite
COMMENT ON TABLE system_config IS 'System config table'; -- fcg-rewrite
COMMENT ON TABLE tenant_switches IS 'Tenant switch record table (for super admin)'; -- fcg-rewrite
COMMENT ON TABLE detection_results IS 'Detection results table'; -- fcg-rewrite
COMMENT ON TABLE blacklist IS 'Blacklist table'; -- fcg-rewrite
COMMENT ON TABLE whitelist IS 'Whitelist table'; -- fcg-rewrite
COMMENT ON TABLE response_templates IS 'Response template table'; -- fcg-rewrite
COMMENT ON TABLE risk_type_config IS 'Risk type switch config table'; -- fcg-rewrite
COMMENT ON TABLE data_security_entity_types IS 'Data security entity type config table'; -- fcg-rewrite
COMMENT ON TABLE tenant_entity_type_disables IS 'Tenant entity type disable table'; -- fcg-rewrite
COMMENT ON TABLE ban_policies IS 'Ban policy config table'; -- fcg-rewrite
COMMENT ON TABLE user_ban_records IS 'User ban records table'; -- fcg-rewrite
COMMENT ON TABLE user_risk_triggers IS 'User risk trigger history table'; -- fcg-rewrite
COMMENT ON TABLE tenant_rate_limits IS 'Tenant rate limit config table'; -- fcg-rewrite
COMMENT ON TABLE tenant_rate_limit_counters IS 'Tenant real-time rate limit counter table'; -- fcg-rewrite
COMMENT ON TABLE test_model_configs IS 'Test model config table'; -- fcg-rewrite
COMMENT ON TABLE proxy_model_configs IS 'Reverse proxy model config table'; -- fcg-rewrite
COMMENT ON TABLE proxy_request_logs IS 'Reverse proxy request log table'; -- fcg-rewrite
COMMENT ON TABLE online_test_model_selections IS 'Online test model selection table'; -- fcg-rewrite
COMMENT ON TABLE knowledge_bases IS 'Knowledge base table'; -- fcg-rewrite

-- Column comments -- fcg-rewrite
COMMENT ON COLUMN tenants.language IS 'User language preference'; -- fcg-rewrite
COMMENT ON COLUMN detection_results.has_image IS 'Whether contains image'; -- fcg-rewrite
COMMENT ON COLUMN detection_results.image_count IS 'Image count'; -- fcg-rewrite
COMMENT ON COLUMN detection_results.image_paths IS 'Saved image file path list'; -- fcg-rewrite
COMMENT ON COLUMN detection_results.data_risk_level IS 'Data leakage risk level'; -- fcg-rewrite
COMMENT ON COLUMN detection_results.data_categories IS 'Data leakage categories'; -- fcg-rewrite
COMMENT ON COLUMN proxy_model_configs.enable_reasoning_detection IS 'Whether to detect reasoning content, default enabled'; -- fcg-rewrite
COMMENT ON COLUMN proxy_model_configs.stream_chunk_size IS 'Stream detection interval, detect every N chunks, default 50'; -- fcg-rewrite
COMMENT ON COLUMN proxy_model_configs.confidence_trigger_level IS 'Confidence trigger level: high, medium, low'; -- fcg-rewrite
COMMENT ON COLUMN tenant_entity_type_disables.entity_type IS 'Disabled entity type code'; -- fcg-rewrite
COMMENT ON COLUMN knowledge_bases.is_global IS 'Whether it is a global knowledge base (all tenants take effect), only admin can set'; -- fcg-rewrite

-- Completion message -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    RAISE NOTICE '========================================'; -- fcg-rewrite
    RAISE NOTICE 'FangcunGuard database initialization completed successfully!'; -- fcg-rewrite
    RAISE NOTICE 'All tables, indexes, triggers, and default data have been created.'; -- fcg-rewrite
    RAISE NOTICE 'Default admin account: admin@fangcunguard.com'; -- fcg-rewrite
    RAISE NOTICE 'Default password: admin123456'; -- fcg-rewrite
    RAISE NOTICE '========================================'; -- fcg-rewrite
END $$; -- fcg-rewrite
