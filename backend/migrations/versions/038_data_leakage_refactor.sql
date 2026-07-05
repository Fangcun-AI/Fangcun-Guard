-- Migration: data_leakage_refactor -- fcg-rewrite
-- Version: 038 -- fcg-rewrite
-- Date: 2026-01-05 -- fcg-rewrite
-- Author: Claude -- fcg-rewrite

-- Description: -- fcg-rewrite
-- Major refactoring of data leakage prevention system: -- fcg-rewrite
-- 1. Add private model fields to upstream_api_configs (is_data_safe, is_default_private_model, private_model_priority) -- fcg-rewrite
-- 2. Create application_data_leakage_policies table for application-level disposal strategies -- fcg-rewrite
-- 3. Enable smart model switching, anonymization, and blocking based on data leakage risk -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Part 1: Add private model fields to upstream_api_configs -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

ALTER TABLE upstream_api_configs ADD COLUMN IF NOT EXISTS is_data_safe BOOLEAN DEFAULT FALSE; -- fcg-rewrite
ALTER TABLE upstream_api_configs ADD COLUMN IF NOT EXISTS is_default_private_model BOOLEAN DEFAULT FALSE; -- fcg-rewrite
ALTER TABLE upstream_api_configs ADD COLUMN IF NOT EXISTS private_model_priority INTEGER DEFAULT 0; -- fcg-rewrite

-- Create indexes for efficient queries -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_upstream_api_configs_is_data_safe ON upstream_api_configs(is_data_safe); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_upstream_api_configs_is_default_private_model ON upstream_api_configs(is_default_private_model); -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Part 2: Create application_data_leakage_policies table -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- Drop the table if it exists to ensure clean schema (fresh install scenario) -- fcg-rewrite
-- This is safe because this table is first created in this migration -- fcg-rewrite
DROP TABLE IF EXISTS application_data_leakage_policies CASCADE; -- fcg-rewrite

-- Create table with DEFAULT gen_random_uuid() for id column -- fcg-rewrite
CREATE TABLE application_data_leakage_policies ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE, -- fcg-rewrite

    -- Disposal actions for each risk level: 'block' | 'switch_private_model' | 'anonymize' | 'pass' -- fcg-rewrite
    high_risk_action VARCHAR(50) NOT NULL DEFAULT 'block', -- fcg-rewrite
    medium_risk_action VARCHAR(50) NOT NULL DEFAULT 'switch_private_model', -- fcg-rewrite
    low_risk_action VARCHAR(50) NOT NULL DEFAULT 'anonymize', -- fcg-rewrite

    -- Private model configuration (nullable if using tenant's default) -- fcg-rewrite
    private_model_id UUID REFERENCES upstream_api_configs(id) ON DELETE SET NULL, -- fcg-rewrite

    -- Feature flags -- fcg-rewrite
    enable_format_detection BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite
    enable_smart_segmentation BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite

    -- Timestamps -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- fcg-rewrite

    -- Constraints -- fcg-rewrite
    CONSTRAINT uq_application_data_leakage_policy UNIQUE (application_id) -- fcg-rewrite
); -- fcg-rewrite

-- Create indexes -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_application_data_leakage_policies_tenant -- fcg-rewrite
ON application_data_leakage_policies(tenant_id); -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_application_data_leakage_policies_app -- fcg-rewrite
ON application_data_leakage_policies(application_id); -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Part 3: Create default policies for all existing applications -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- Create default policies for all existing applications -- fcg-rewrite
-- Default strategy: high=block, medium=switch_private_model, low=anonymize -- fcg-rewrite
-- Use WHERE NOT EXISTS to handle re-runs and partial failures -- fcg-rewrite
INSERT INTO application_data_leakage_policies ( -- fcg-rewrite
    id, -- fcg-rewrite
    tenant_id, -- fcg-rewrite
    application_id, -- fcg-rewrite
    high_risk_action, -- fcg-rewrite
    medium_risk_action, -- fcg-rewrite
    low_risk_action, -- fcg-rewrite
    enable_format_detection, -- fcg-rewrite
    enable_smart_segmentation -- fcg-rewrite
) -- fcg-rewrite
SELECT -- fcg-rewrite
    gen_random_uuid(), -- fcg-rewrite
    a.tenant_id, -- fcg-rewrite
    a.id, -- fcg-rewrite
    'block', -- fcg-rewrite
    'switch_private_model', -- fcg-rewrite
    'anonymize', -- fcg-rewrite
    TRUE, -- fcg-rewrite
    TRUE -- fcg-rewrite
FROM applications a -- fcg-rewrite
WHERE NOT EXISTS ( -- fcg-rewrite
    SELECT 1 FROM application_data_leakage_policies p WHERE p.application_id = a.id -- fcg-rewrite
); -- fcg-rewrite