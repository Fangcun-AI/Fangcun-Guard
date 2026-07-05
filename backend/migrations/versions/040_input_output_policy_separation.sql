-- Migration: Separate input and output data leakage policies -- fcg-rewrite
-- Description: Split data leakage policies into input (prevent external leakage) -- fcg-rewrite
--              and output (prevent internal unauthorized access) configurations. -- fcg-rewrite
--              Add tenant-level defaults with application-level overrides. -- fcg-rewrite
-- Version: 040 -- fcg-rewrite
-- Date: 2026-01-05 -- fcg-rewrite

BEGIN; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 1: Create tenant-level default data leakage policies table -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

CREATE TABLE IF NOT EXISTS tenant_data_leakage_policies ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    tenant_id UUID NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite

    -- Input Policy Defaults (prevent external data leakage) -- fcg-rewrite
    -- Actions: 'block' | 'switch_private_model' | 'anonymize' | 'pass' -- fcg-rewrite
    default_input_high_risk_action VARCHAR(50) NOT NULL DEFAULT 'block', -- fcg-rewrite
    default_input_medium_risk_action VARCHAR(50) NOT NULL DEFAULT 'switch_private_model', -- fcg-rewrite
    default_input_low_risk_action VARCHAR(50) NOT NULL DEFAULT 'anonymize', -- fcg-rewrite

    -- Output Policy Defaults (prevent internal unauthorized access) -- fcg-rewrite
    -- Boolean flags: whether to anonymize output for each risk level (legacy) -- fcg-rewrite
    default_output_high_risk_anonymize BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite
    default_output_medium_risk_anonymize BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite
    default_output_low_risk_anonymize BOOLEAN NOT NULL DEFAULT FALSE, -- fcg-rewrite

    -- Output Policy Defaults - Action type (same as input policy) -- fcg-rewrite
    default_output_high_risk_action VARCHAR(50) NOT NULL DEFAULT 'block', -- fcg-rewrite
    default_output_medium_risk_action VARCHAR(50) NOT NULL DEFAULT 'anonymize', -- fcg-rewrite
    default_output_low_risk_action VARCHAR(50) NOT NULL DEFAULT 'pass', -- fcg-rewrite

    -- General Risk Policy Defaults (security, safety, company policy violations) -- fcg-rewrite
    default_general_high_risk_action VARCHAR(50) NOT NULL DEFAULT 'block', -- fcg-rewrite
    default_general_medium_risk_action VARCHAR(50) NOT NULL DEFAULT 'replace', -- fcg-rewrite
    default_general_low_risk_action VARCHAR(50) NOT NULL DEFAULT 'pass', -- fcg-rewrite

    -- General Risk Policy - Input Defaults -- fcg-rewrite
    default_general_input_high_risk_action VARCHAR(50) NOT NULL DEFAULT 'block', -- fcg-rewrite
    default_general_input_medium_risk_action VARCHAR(50) NOT NULL DEFAULT 'replace', -- fcg-rewrite
    default_general_input_low_risk_action VARCHAR(50) NOT NULL DEFAULT 'pass', -- fcg-rewrite

    -- General Risk Policy - Output Defaults -- fcg-rewrite
    default_general_output_high_risk_action VARCHAR(50) NOT NULL DEFAULT 'block', -- fcg-rewrite
    default_general_output_medium_risk_action VARCHAR(50) NOT NULL DEFAULT 'replace', -- fcg-rewrite
    default_general_output_low_risk_action VARCHAR(50) NOT NULL DEFAULT 'pass', -- fcg-rewrite

    -- Note: Default private model is determined by upstream_api_configs.is_default_private_model = true -- fcg-rewrite
    -- (No column needed here as it's stored in upstream_api_configs) -- fcg-rewrite

    -- Default Feature Flags -- fcg-rewrite
    default_enable_format_detection BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite
    default_enable_smart_segmentation BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite

    -- Timestamps -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP, -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP -- fcg-rewrite
); -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_tenant_dlp_tenant_id ON tenant_data_leakage_policies(tenant_id); -- fcg-rewrite

-- Add missing columns to tenant_data_leakage_policies if they don't exist -- fcg-rewrite
-- (handles case where table was created by partial/older migration run or SQLAlchemy create_all) -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_input_high_risk_action') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_input_high_risk_action VARCHAR(50) NOT NULL DEFAULT 'block'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_input_medium_risk_action') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_input_medium_risk_action VARCHAR(50) NOT NULL DEFAULT 'switch_private_model'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_input_low_risk_action') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_input_low_risk_action VARCHAR(50) NOT NULL DEFAULT 'anonymize'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_output_high_risk_anonymize') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_output_high_risk_anonymize BOOLEAN NOT NULL DEFAULT TRUE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_output_medium_risk_anonymize') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_output_medium_risk_anonymize BOOLEAN NOT NULL DEFAULT TRUE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_output_low_risk_anonymize') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_output_low_risk_anonymize BOOLEAN NOT NULL DEFAULT FALSE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_enable_format_detection') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_enable_format_detection BOOLEAN NOT NULL DEFAULT TRUE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_enable_smart_segmentation') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_enable_smart_segmentation BOOLEAN NOT NULL DEFAULT TRUE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Add output action columns (added in model, may not exist in DB) -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_output_high_risk_action') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_output_high_risk_action VARCHAR(50) NOT NULL DEFAULT 'block'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_output_medium_risk_action') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_output_medium_risk_action VARCHAR(50) NOT NULL DEFAULT 'anonymize'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_output_low_risk_action') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_output_low_risk_action VARCHAR(50) NOT NULL DEFAULT 'pass'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Add general risk policy columns (added in model, may not exist in DB) -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_general_high_risk_action') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_general_high_risk_action VARCHAR(50) NOT NULL DEFAULT 'block'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_general_medium_risk_action') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_general_medium_risk_action VARCHAR(50) NOT NULL DEFAULT 'replace'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'default_general_low_risk_action') THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies -- fcg-rewrite
        ADD COLUMN default_general_low_risk_action VARCHAR(50) NOT NULL DEFAULT 'pass'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Set database-level defaults for columns that may have been created by SQLAlchemy without defaults -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN id SET DEFAULT gen_random_uuid(); -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_input_high_risk_action SET DEFAULT 'block'; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_input_medium_risk_action SET DEFAULT 'switch_private_model'; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_input_low_risk_action SET DEFAULT 'anonymize'; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_output_high_risk_anonymize SET DEFAULT TRUE; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_output_medium_risk_anonymize SET DEFAULT TRUE; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_output_low_risk_anonymize SET DEFAULT FALSE; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_output_high_risk_action SET DEFAULT 'block'; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_output_medium_risk_action SET DEFAULT 'anonymize'; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_output_low_risk_action SET DEFAULT 'pass'; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_general_high_risk_action SET DEFAULT 'block'; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_general_medium_risk_action SET DEFAULT 'replace'; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_general_low_risk_action SET DEFAULT 'pass'; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_enable_format_detection SET DEFAULT TRUE; -- fcg-rewrite
    ALTER TABLE tenant_data_leakage_policies ALTER COLUMN default_enable_smart_segmentation SET DEFAULT TRUE; -- fcg-rewrite
EXCEPTION WHEN OTHERS THEN -- fcg-rewrite
    -- Ignore errors if columns don't exist yet -- fcg-rewrite
    NULL; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 2: Backup existing application policies -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

CREATE TABLE IF NOT EXISTS application_data_leakage_policies_backup AS -- fcg-rewrite
SELECT * FROM application_data_leakage_policies; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 3: Rename existing table columns for input policy -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- Rename action columns to input-specific names -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'high_risk_action') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies -- fcg-rewrite
        RENAME COLUMN high_risk_action TO input_high_risk_action; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'medium_risk_action') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies -- fcg-rewrite
        RENAME COLUMN medium_risk_action TO input_medium_risk_action; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'low_risk_action') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies -- fcg-rewrite
        RENAME COLUMN low_risk_action TO input_low_risk_action; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 4: Add output policy columns to application table -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- Add output anonymization flags (NULL = use tenant default) -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'output_high_risk_anonymize') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies -- fcg-rewrite
        ADD COLUMN output_high_risk_anonymize BOOLEAN DEFAULT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'output_medium_risk_anonymize') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies -- fcg-rewrite
        ADD COLUMN output_medium_risk_anonymize BOOLEAN DEFAULT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
                   WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
                   AND column_name = 'output_low_risk_anonymize') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies -- fcg-rewrite
        ADD COLUMN output_low_risk_anonymize BOOLEAN DEFAULT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 5: Make existing columns nullable for override capability -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- Make input action columns nullable (NULL = use tenant default) -- fcg-rewrite
-- Wrap in DO blocks to handle cases where columns might not exist or are already nullable -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'input_high_risk_action' -- fcg-rewrite
               AND is_nullable = 'NO') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies ALTER COLUMN input_high_risk_action DROP NOT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'input_medium_risk_action' -- fcg-rewrite
               AND is_nullable = 'NO') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies ALTER COLUMN input_medium_risk_action DROP NOT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'input_low_risk_action' -- fcg-rewrite
               AND is_nullable = 'NO') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies ALTER COLUMN input_low_risk_action DROP NOT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'enable_format_detection' -- fcg-rewrite
               AND is_nullable = 'NO') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies ALTER COLUMN enable_format_detection DROP NOT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'enable_smart_segmentation' -- fcg-rewrite
               AND is_nullable = 'NO') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies ALTER COLUMN enable_smart_segmentation DROP NOT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Set default values to NULL for future records -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'input_high_risk_action') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies ALTER COLUMN input_high_risk_action SET DEFAULT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'input_medium_risk_action') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies ALTER COLUMN input_medium_risk_action SET DEFAULT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'input_low_risk_action') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies ALTER COLUMN input_low_risk_action SET DEFAULT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'enable_format_detection') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies ALTER COLUMN enable_format_detection SET DEFAULT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'application_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'enable_smart_segmentation') THEN -- fcg-rewrite
        ALTER TABLE application_data_leakage_policies ALTER COLUMN enable_smart_segmentation SET DEFAULT NULL; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 6: Ensure id column has default (fix for tables created by SQLAlchemy) -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Add default to id column if missing (handles tables created by SQLAlchemy create_all) -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns -- fcg-rewrite
               WHERE table_name = 'tenant_data_leakage_policies' -- fcg-rewrite
               AND column_name = 'id' -- fcg-rewrite
               AND column_default IS NULL) THEN -- fcg-rewrite
        ALTER TABLE tenant_data_leakage_policies ALTER COLUMN id SET DEFAULT gen_random_uuid(); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 7: Migrate existing data to tenant defaults -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- Create tenant-level defaults from existing application policies -- fcg-rewrite
-- Use the most common settings from each tenant's applications -- fcg-rewrite
-- Note: default_private_model is now determined by upstream_api_configs.is_default_private_model flag -- fcg-rewrite
-- Note: Explicitly use gen_random_uuid() for id to handle tables without default -- fcg-rewrite
INSERT INTO tenant_data_leakage_policies ( -- fcg-rewrite
    id, -- fcg-rewrite
    tenant_id, -- fcg-rewrite
    default_input_high_risk_action, -- fcg-rewrite
    default_input_medium_risk_action, -- fcg-rewrite
    default_input_low_risk_action, -- fcg-rewrite
    default_output_high_risk_anonymize, -- fcg-rewrite
    default_output_medium_risk_anonymize, -- fcg-rewrite
    default_output_low_risk_anonymize, -- fcg-rewrite
    default_output_high_risk_action, -- fcg-rewrite
    default_output_medium_risk_action, -- fcg-rewrite
    default_output_low_risk_action, -- fcg-rewrite
    default_general_high_risk_action, -- fcg-rewrite
    default_general_medium_risk_action, -- fcg-rewrite
    default_general_low_risk_action, -- fcg-rewrite
    default_general_input_high_risk_action, -- fcg-rewrite
    default_general_input_medium_risk_action, -- fcg-rewrite
    default_general_input_low_risk_action, -- fcg-rewrite
    default_general_output_high_risk_action, -- fcg-rewrite
    default_general_output_medium_risk_action, -- fcg-rewrite
    default_general_output_low_risk_action, -- fcg-rewrite
    default_enable_format_detection, -- fcg-rewrite
    default_enable_smart_segmentation -- fcg-rewrite
) -- fcg-rewrite
SELECT DISTINCT ON (tenant_id) -- fcg-rewrite
    gen_random_uuid(), -- fcg-rewrite
    tenant_id, -- fcg-rewrite
    COALESCE(input_high_risk_action, 'block'), -- fcg-rewrite
    COALESCE(input_medium_risk_action, 'switch_private_model'), -- fcg-rewrite
    COALESCE(input_low_risk_action, 'anonymize'), -- fcg-rewrite
    TRUE,   -- default_output_high_risk_anonymize -- fcg-rewrite
    TRUE,   -- default_output_medium_risk_anonymize -- fcg-rewrite
    FALSE,  -- default_output_low_risk_anonymize -- fcg-rewrite
    'block',     -- default_output_high_risk_action -- fcg-rewrite
    'anonymize', -- default_output_medium_risk_action -- fcg-rewrite
    'pass',      -- default_output_low_risk_action -- fcg-rewrite
    'block',     -- default_general_high_risk_action -- fcg-rewrite
    'replace',   -- default_general_medium_risk_action -- fcg-rewrite
    'pass',      -- default_general_low_risk_action -- fcg-rewrite
    'block',     -- default_general_input_high_risk_action -- fcg-rewrite
    'replace',   -- default_general_input_medium_risk_action -- fcg-rewrite
    'pass',      -- default_general_input_low_risk_action -- fcg-rewrite
    'block',     -- default_general_output_high_risk_action -- fcg-rewrite
    'replace',   -- default_general_output_medium_risk_action -- fcg-rewrite
    'pass',      -- default_general_output_low_risk_action -- fcg-rewrite
    COALESCE(enable_format_detection, TRUE), -- fcg-rewrite
    COALESCE(enable_smart_segmentation, TRUE) -- fcg-rewrite
FROM application_data_leakage_policies -- fcg-rewrite
ORDER BY tenant_id, created_at -- fcg-rewrite
ON CONFLICT (tenant_id) DO NOTHING; -- fcg-rewrite

-- Also create defaults for tenants without any application policies yet -- fcg-rewrite
-- Note: Explicitly specify all columns to handle tables created by SQLAlchemy without defaults -- fcg-rewrite
INSERT INTO tenant_data_leakage_policies ( -- fcg-rewrite
    id, -- fcg-rewrite
    tenant_id, -- fcg-rewrite
    default_input_high_risk_action, -- fcg-rewrite
    default_input_medium_risk_action, -- fcg-rewrite
    default_input_low_risk_action, -- fcg-rewrite
    default_output_high_risk_anonymize, -- fcg-rewrite
    default_output_medium_risk_anonymize, -- fcg-rewrite
    default_output_low_risk_anonymize, -- fcg-rewrite
    default_output_high_risk_action, -- fcg-rewrite
    default_output_medium_risk_action, -- fcg-rewrite
    default_output_low_risk_action, -- fcg-rewrite
    default_general_high_risk_action, -- fcg-rewrite
    default_general_medium_risk_action, -- fcg-rewrite
    default_general_low_risk_action, -- fcg-rewrite
    default_general_input_high_risk_action, -- fcg-rewrite
    default_general_input_medium_risk_action, -- fcg-rewrite
    default_general_input_low_risk_action, -- fcg-rewrite
    default_general_output_high_risk_action, -- fcg-rewrite
    default_general_output_medium_risk_action, -- fcg-rewrite
    default_general_output_low_risk_action, -- fcg-rewrite
    default_enable_format_detection, -- fcg-rewrite
    default_enable_smart_segmentation -- fcg-rewrite
) -- fcg-rewrite
SELECT -- fcg-rewrite
    gen_random_uuid(), -- fcg-rewrite
    id, -- fcg-rewrite
    'block',              -- default_input_high_risk_action -- fcg-rewrite
    'switch_private_model', -- default_input_medium_risk_action -- fcg-rewrite
    'anonymize',          -- default_input_low_risk_action -- fcg-rewrite
    TRUE,                 -- default_output_high_risk_anonymize -- fcg-rewrite
    TRUE,                 -- default_output_medium_risk_anonymize -- fcg-rewrite
    FALSE,                -- default_output_low_risk_anonymize -- fcg-rewrite
    'block',              -- default_output_high_risk_action -- fcg-rewrite
    'anonymize',          -- default_output_medium_risk_action -- fcg-rewrite
    'pass',               -- default_output_low_risk_action -- fcg-rewrite
    'block',              -- default_general_high_risk_action -- fcg-rewrite
    'replace',            -- default_general_medium_risk_action -- fcg-rewrite
    'pass',               -- default_general_low_risk_action -- fcg-rewrite
    'block',              -- default_general_input_high_risk_action -- fcg-rewrite
    'replace',            -- default_general_input_medium_risk_action -- fcg-rewrite
    'pass',               -- default_general_input_low_risk_action -- fcg-rewrite
    'block',              -- default_general_output_high_risk_action -- fcg-rewrite
    'replace',            -- default_general_output_medium_risk_action -- fcg-rewrite
    'pass',               -- default_general_output_low_risk_action -- fcg-rewrite
    TRUE,                 -- default_enable_format_detection -- fcg-rewrite
    TRUE                  -- default_enable_smart_segmentation -- fcg-rewrite
FROM tenants -- fcg-rewrite
WHERE id NOT IN (SELECT tenant_id FROM tenant_data_leakage_policies) -- fcg-rewrite
ON CONFLICT (tenant_id) DO NOTHING; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 8: Clear application-level values that match tenant defaults -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- For each application, if its values match the tenant default, set to NULL -- fcg-rewrite
-- Note: private_model_id is kept as-is since default is now determined by upstream_api_configs flag -- fcg-rewrite
UPDATE application_data_leakage_policies app -- fcg-rewrite
SET -- fcg-rewrite
    input_high_risk_action = CASE -- fcg-rewrite
        WHEN app.input_high_risk_action = tenant.default_input_high_risk_action -- fcg-rewrite
        THEN NULL ELSE app.input_high_risk_action END, -- fcg-rewrite
    input_medium_risk_action = CASE -- fcg-rewrite
        WHEN app.input_medium_risk_action = tenant.default_input_medium_risk_action -- fcg-rewrite
        THEN NULL ELSE app.input_medium_risk_action END, -- fcg-rewrite
    input_low_risk_action = CASE -- fcg-rewrite
        WHEN app.input_low_risk_action = tenant.default_input_low_risk_action -- fcg-rewrite
        THEN NULL ELSE app.input_low_risk_action END, -- fcg-rewrite
    enable_format_detection = CASE -- fcg-rewrite
        WHEN app.enable_format_detection = tenant.default_enable_format_detection -- fcg-rewrite
        THEN NULL ELSE app.enable_format_detection END, -- fcg-rewrite
    enable_smart_segmentation = CASE -- fcg-rewrite
        WHEN app.enable_smart_segmentation = tenant.default_enable_smart_segmentation -- fcg-rewrite
        THEN NULL ELSE app.enable_smart_segmentation END -- fcg-rewrite
FROM tenant_data_leakage_policies tenant -- fcg-rewrite
WHERE app.tenant_id = tenant.tenant_id; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 9: Add comments for documentation -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

COMMENT ON TABLE tenant_data_leakage_policies IS -- fcg-rewrite
'Tenant-level default data leakage prevention policies. All applications inherit these defaults unless explicitly overridden.'; -- fcg-rewrite

COMMENT ON COLUMN tenant_data_leakage_policies.default_input_high_risk_action IS -- fcg-rewrite
'Default action for high-risk input data: block | switch_private_model | anonymize | pass'; -- fcg-rewrite

COMMENT ON COLUMN tenant_data_leakage_policies.default_output_high_risk_anonymize IS -- fcg-rewrite
'Default flag: whether to anonymize high-risk data in model outputs (prevent internal unauthorized access)'; -- fcg-rewrite

COMMENT ON TABLE application_data_leakage_policies IS -- fcg-rewrite
'Application-level data leakage policy overrides. NULL values inherit from tenant defaults.'; -- fcg-rewrite

COMMENT ON COLUMN application_data_leakage_policies.input_high_risk_action IS -- fcg-rewrite
'Override input action for high-risk data. NULL = use tenant default'; -- fcg-rewrite

COMMENT ON COLUMN application_data_leakage_policies.output_high_risk_anonymize IS -- fcg-rewrite
'Override output anonymization for high-risk data. NULL = use tenant default'; -- fcg-rewrite

COMMIT; -- fcg-rewrite
