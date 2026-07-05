-- Create ban policy tables -- fcg-rewrite
-- Run this script if ban policy tables are missing from the database -- fcg-rewrite

-- Enable UUID extension -- fcg-rewrite
CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- fcg-rewrite

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

-- Create indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_ban_policies_tenant ON ban_policies(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_user_ban_records_tenant_user ON user_ban_records(tenant_id, user_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_user_ban_records_active ON user_ban_records(tenant_id, user_id, is_active) WHERE is_active = TRUE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_user_risk_triggers_tenant_user_time ON user_risk_triggers(tenant_id, user_id, triggered_at); -- fcg-rewrite

-- Create triggers -- fcg-rewrite
CREATE OR REPLACE FUNCTION update_ban_policies_updated_at() -- fcg-rewrite
RETURNS TRIGGER AS $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    NEW.updated_at = NOW(); -- fcg-rewrite
    RETURN NEW; -- fcg-rewrite
END; -- fcg-rewrite
$$ LANGUAGE plpgsql; -- fcg-rewrite

-- Drop trigger if it exists, then recreate it using safer syntax -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'ban_policies_updated_at') THEN -- fcg-rewrite
        DROP TRIGGER ban_policies_updated_at ON ban_policies; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

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

-- Drop trigger if it exists, then recreate it using safer syntax -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'user_ban_records_updated_at') THEN -- fcg-rewrite
        DROP TRIGGER user_ban_records_updated_at ON user_ban_records; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

CREATE TRIGGER user_ban_records_updated_at -- fcg-rewrite
    BEFORE UPDATE ON user_ban_records -- fcg-rewrite
    FOR EACH ROW -- fcg-rewrite
    EXECUTE FUNCTION update_user_ban_records_updated_at(); -- fcg-rewrite

-- Create utility functions -- fcg-rewrite
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

-- Add comments -- fcg-rewrite
COMMENT ON TABLE ban_policies IS 'Ban policy config table'; -- fcg-rewrite
COMMENT ON TABLE user_ban_records IS 'User ban records table'; -- fcg-rewrite
COMMENT ON TABLE user_risk_triggers IS 'User risk trigger history table'; -- fcg-rewrite
