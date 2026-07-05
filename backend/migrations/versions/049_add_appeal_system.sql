-- Migration: Add appeal system for false positive handling -- fcg-rewrite
-- Version: 049 -- fcg-rewrite
-- Description: Creates appeal_config and appeal_records tables for user false positive appeals -- fcg-rewrite

-- 1. Create appeal_config table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS appeal_config ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE, -- fcg-rewrite
    enabled BOOLEAN NOT NULL DEFAULT FALSE, -- fcg-rewrite
    -- Template for appeal link message, supports {appeal_url} placeholder -- fcg-rewrite
    message_template TEXT NOT NULL DEFAULT 'If you think this is a false positive, please click the following link to appeal: {appeal_url}', -- fcg-rewrite
    -- Base URL for appeal links (e.g., https://domain.com or http://192.168.1.100:5001) -- fcg-rewrite
    appeal_base_url VARCHAR(512) NOT NULL DEFAULT '', -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite

    CONSTRAINT uq_appeal_config_application UNIQUE (application_id) -- fcg-rewrite
); -- fcg-rewrite

-- 2. Create appeal_records table -- fcg-rewrite
CREATE TABLE IF NOT EXISTS appeal_records ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE, -- fcg-rewrite
    request_id VARCHAR(64) NOT NULL,  -- Original detection request_id (guardrails-xxx) -- fcg-rewrite
    user_id VARCHAR(255),             -- User who triggered the detection -- fcg-rewrite

    -- Original detection info (denormalized for review) -- fcg-rewrite
    original_content TEXT NOT NULL, -- fcg-rewrite
    original_risk_level VARCHAR(20) NOT NULL, -- fcg-rewrite
    original_categories JSON NOT NULL, -- fcg-rewrite
    original_suggest_action VARCHAR(20) NOT NULL, -- fcg-rewrite

    -- Review status: pending, reviewing, approved, rejected -- fcg-rewrite
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- fcg-rewrite

    -- AI review results -- fcg-rewrite
    ai_review_result TEXT,            -- AI reasoning output -- fcg-rewrite
    ai_approved BOOLEAN,              -- AI decision: true=false positive confirmed -- fcg-rewrite
    ai_reviewed_at TIMESTAMP WITH TIME ZONE, -- fcg-rewrite

    -- Context for review -- fcg-rewrite
    user_recent_requests JSON,        -- Recent 10 requests from this user -- fcg-rewrite
    user_ban_history JSON,            -- User's ban records if any -- fcg-rewrite

    -- Whitelist addition -- fcg-rewrite
    whitelist_id INTEGER REFERENCES whitelist(id) ON DELETE SET NULL, -- fcg-rewrite
    whitelist_keyword TEXT,           -- The specific keyword/phrase added -- fcg-rewrite

    -- Metadata -- fcg-rewrite
    ip_address VARCHAR(45), -- fcg-rewrite
    user_agent TEXT, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite

    CONSTRAINT uq_appeal_request_id UNIQUE (request_id) -- fcg-rewrite
); -- fcg-rewrite

-- 3. Create indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_appeal_config_application ON appeal_config(application_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_appeal_config_tenant ON appeal_config(tenant_id); -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_appeal_records_application ON appeal_records(application_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_appeal_records_tenant ON appeal_records(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_appeal_records_status ON appeal_records(status); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_appeal_records_request_id ON appeal_records(request_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_appeal_records_user_id ON appeal_records(user_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_appeal_records_created_at ON appeal_records(created_at); -- fcg-rewrite

-- 4. Create trigger to auto-update updated_at -- fcg-rewrite
CREATE OR REPLACE FUNCTION update_appeal_config_updated_at() -- fcg-rewrite
RETURNS TRIGGER AS $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    NEW.updated_at = NOW(); -- fcg-rewrite
    RETURN NEW; -- fcg-rewrite
END; -- fcg-rewrite
$$ LANGUAGE plpgsql; -- fcg-rewrite

DROP TRIGGER IF EXISTS trg_appeal_config_updated_at ON appeal_config; -- fcg-rewrite
CREATE TRIGGER trg_appeal_config_updated_at -- fcg-rewrite
    BEFORE UPDATE ON appeal_config -- fcg-rewrite
    FOR EACH ROW -- fcg-rewrite
    EXECUTE FUNCTION update_appeal_config_updated_at(); -- fcg-rewrite

CREATE OR REPLACE FUNCTION update_appeal_records_updated_at() -- fcg-rewrite
RETURNS TRIGGER AS $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    NEW.updated_at = NOW(); -- fcg-rewrite
    RETURN NEW; -- fcg-rewrite
END; -- fcg-rewrite
$$ LANGUAGE plpgsql; -- fcg-rewrite

DROP TRIGGER IF EXISTS trg_appeal_records_updated_at ON appeal_records; -- fcg-rewrite
CREATE TRIGGER trg_appeal_records_updated_at -- fcg-rewrite
    BEFORE UPDATE ON appeal_records -- fcg-rewrite
    FOR EACH ROW -- fcg-rewrite
    EXECUTE FUNCTION update_appeal_records_updated_at(); -- fcg-rewrite
