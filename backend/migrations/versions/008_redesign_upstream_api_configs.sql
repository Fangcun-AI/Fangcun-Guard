-- Migration: Redesign upstream API configurations for Security Gateway -- fcg-rewrite
-- Description: Replace per-model configuration with per-API configuration, -- fcg-rewrite
--              allowing one upstream API key to serve multiple models -- fcg-rewrite
-- Author: Claude -- fcg-rewrite
-- Date: 2025-10-31 -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 1: Create new upstream_api_configs table -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

CREATE TABLE IF NOT EXISTS upstream_api_configs ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    config_name VARCHAR(100) NOT NULL,  -- Display name for UI (e.g., "OpenAI Production") -- fcg-rewrite
    api_base_url VARCHAR(512) NOT NULL,  -- Upstream API base URL -- fcg-rewrite
    api_key_encrypted TEXT NOT NULL,     -- Encrypted upstream API key -- fcg-rewrite
    provider VARCHAR(50),                 -- Provider type: openai, anthropic, local, etc. -- fcg-rewrite
    is_active BOOLEAN DEFAULT true,      -- Whether this config is active -- fcg-rewrite

    -- Security settings (moved from old table) -- fcg-rewrite
    block_on_input_risk BOOLEAN DEFAULT false,     -- Block requests with input risk -- fcg-rewrite
    block_on_output_risk BOOLEAN DEFAULT false,    -- Block responses with output risk -- fcg-rewrite
    enable_reasoning_detection BOOLEAN DEFAULT true, -- Detect reasoning content -- fcg-rewrite
    stream_chunk_size INTEGER DEFAULT 50,          -- Stream detection interval -- fcg-rewrite

    -- Metadata -- fcg-rewrite
    description TEXT,                    -- Optional description -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite

    CONSTRAINT upstream_api_configs_tenant_name_unique UNIQUE(tenant_id, config_name) -- fcg-rewrite
); -- fcg-rewrite

-- Indexes for performance -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_upstream_api_configs_tenant_id ON upstream_api_configs(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_upstream_api_configs_is_active ON upstream_api_configs(is_active); -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 2: Migrate existing data from proxy_model_configs to upstream_api_configs -- fcg-rewrite
-- NOTE: Only run if proxy_model_configs table exists (may not exist in fresh deployments) -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Check if proxy_model_configs table exists -- fcg-rewrite
    IF EXISTS ( -- fcg-rewrite
        SELECT 1 FROM information_schema.tables -- fcg-rewrite
        WHERE table_schema = 'public' AND table_name = 'proxy_model_configs' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        -- Migrate data from old table to new table -- fcg-rewrite
        INSERT INTO upstream_api_configs ( -- fcg-rewrite
            id, -- fcg-rewrite
            tenant_id, -- fcg-rewrite
            config_name, -- fcg-rewrite
            api_base_url, -- fcg-rewrite
            api_key_encrypted, -- fcg-rewrite
            provider, -- fcg-rewrite
            is_active, -- fcg-rewrite
            block_on_input_risk, -- fcg-rewrite
            block_on_output_risk, -- fcg-rewrite
            enable_reasoning_detection, -- fcg-rewrite
            stream_chunk_size, -- fcg-rewrite
            description, -- fcg-rewrite
            created_at, -- fcg-rewrite
            updated_at -- fcg-rewrite
        ) -- fcg-rewrite
        SELECT -- fcg-rewrite
            gen_random_uuid() as id, -- fcg-rewrite
            tenant_id, -- fcg-rewrite
            -- Use the first config_name as the display name, append "(Migrated)" to avoid conflicts -- fcg-rewrite
            MIN(config_name) || ' (Migrated)' as config_name, -- fcg-rewrite
            api_base_url, -- fcg-rewrite
            api_key_encrypted, -- fcg-rewrite
            -- Infer provider from api_base_url -- fcg-rewrite
            CASE -- fcg-rewrite
                WHEN api_base_url LIKE '%openai%' THEN 'openai' -- fcg-rewrite
                WHEN api_base_url LIKE '%anthropic%' THEN 'anthropic' -- fcg-rewrite
                WHEN api_base_url LIKE '%localhost%' OR api_base_url LIKE '%127.0.0.1%' THEN 'local' -- fcg-rewrite
                ELSE 'other' -- fcg-rewrite
            END as provider, -- fcg-rewrite
            BOOL_OR(enabled) as is_active,  -- Active if any old config was enabled -- fcg-rewrite
            BOOL_OR(block_on_input_risk) as block_on_input_risk, -- fcg-rewrite
            BOOL_OR(block_on_output_risk) as block_on_output_risk, -- fcg-rewrite
            BOOL_OR(enable_reasoning_detection) as enable_reasoning_detection, -- fcg-rewrite
            MAX(stream_chunk_size) as stream_chunk_size, -- fcg-rewrite
            'Migrated from proxy_model_configs. Original models: ' || STRING_AGG(model_name, ', ') as description, -- fcg-rewrite
            MIN(created_at) as created_at, -- fcg-rewrite
            MAX(updated_at) as updated_at -- fcg-rewrite
        FROM proxy_model_configs -- fcg-rewrite
        GROUP BY tenant_id, api_base_url, api_key_encrypted -- fcg-rewrite
        ON CONFLICT (tenant_id, config_name) DO NOTHING; -- fcg-rewrite

        RAISE NOTICE 'Successfully migrated data from proxy_model_configs'; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'Table proxy_model_configs does not exist, skipping data migration'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 3: Update proxy_request_logs to reference new table -- fcg-rewrite
-- NOTE: Only run if proxy_model_configs table exists -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- Add new column for upstream_api_config_id -- fcg-rewrite
ALTER TABLE proxy_request_logs -- fcg-rewrite
ADD COLUMN IF NOT EXISTS upstream_api_config_id UUID; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Only run mapping if proxy_model_configs table exists -- fcg-rewrite
    IF EXISTS ( -- fcg-rewrite
        SELECT 1 FROM information_schema.tables -- fcg-rewrite
        WHERE table_schema = 'public' AND table_name = 'proxy_model_configs' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        -- Create a mapping table to help migrate foreign keys -- fcg-rewrite
        CREATE TEMP TABLE IF NOT EXISTS config_mapping AS -- fcg-rewrite
        SELECT -- fcg-rewrite
            pmc.id as old_config_id, -- fcg-rewrite
            uac.id as new_config_id -- fcg-rewrite
        FROM proxy_model_configs pmc -- fcg-rewrite
        JOIN upstream_api_configs uac ON -- fcg-rewrite
            pmc.tenant_id = uac.tenant_id AND -- fcg-rewrite
            pmc.api_base_url = uac.api_base_url AND -- fcg-rewrite
            pmc.api_key_encrypted = uac.api_key_encrypted; -- fcg-rewrite

        -- Update proxy_request_logs with new foreign keys -- fcg-rewrite
        UPDATE proxy_request_logs prl -- fcg-rewrite
        SET upstream_api_config_id = cm.new_config_id -- fcg-rewrite
        FROM config_mapping cm -- fcg-rewrite
        WHERE prl.proxy_config_id = cm.old_config_id; -- fcg-rewrite

        RAISE NOTICE 'Successfully updated proxy_request_logs foreign keys'; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'Table proxy_model_configs does not exist, skipping proxy_request_logs migration'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Add foreign key constraint for new column -- fcg-rewrite
ALTER TABLE proxy_request_logs -- fcg-rewrite
ADD CONSTRAINT fk_proxy_request_logs_upstream_api_config -- fcg-rewrite
FOREIGN KEY (upstream_api_config_id) REFERENCES upstream_api_configs(id) ON DELETE SET NULL; -- fcg-rewrite

-- Create index for new foreign key -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_proxy_request_logs_upstream_api_config_id -- fcg-rewrite
ON proxy_request_logs(upstream_api_config_id); -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 4: Mark old table as deprecated (keep for rollback, will drop in future) -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- Drop the empty deprecated table if it already exists (from previous failed migration) -- fcg-rewrite
DROP TABLE IF EXISTS proxy_model_configs_deprecated CASCADE; -- fcg-rewrite

-- Rename old table to indicate deprecation -- fcg-rewrite
ALTER TABLE IF EXISTS proxy_model_configs -- fcg-rewrite
RENAME TO proxy_model_configs_deprecated; -- fcg-rewrite

-- Add comment to old table (only if it exists) -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS ( -- fcg-rewrite
        SELECT 1 FROM information_schema.tables -- fcg-rewrite
        WHERE table_schema = 'public' AND table_name = 'proxy_model_configs_deprecated' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        EXECUTE 'COMMENT ON TABLE proxy_model_configs_deprecated IS -- fcg-rewrite
''DEPRECATED: Replaced by upstream_api_configs. Kept for rollback purposes. Will be dropped in future migration.'''; -- fcg-rewrite
        RAISE NOTICE 'Added comment to proxy_model_configs_deprecated table'; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'Table proxy_model_configs_deprecated does not exist, skipping comment'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Make old foreign key nullable for smooth transition -- fcg-rewrite
ALTER TABLE proxy_request_logs -- fcg-rewrite
ALTER COLUMN proxy_config_id DROP NOT NULL; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Step 5: Add helpful comments -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

COMMENT ON TABLE upstream_api_configs IS -- fcg-rewrite
'Upstream API configurations for Security Gateway. Each config represents one upstream API endpoint (e.g., OpenAI API) that can serve multiple models.'; -- fcg-rewrite

COMMENT ON COLUMN upstream_api_configs.id IS -- fcg-rewrite
'UUID used in gateway URL: /v1/gateway/{id}/chat/completions'; -- fcg-rewrite

COMMENT ON COLUMN upstream_api_configs.config_name IS -- fcg-rewrite
'Display name shown in UI, must be unique per tenant'; -- fcg-rewrite

COMMENT ON COLUMN upstream_api_configs.api_base_url IS -- fcg-rewrite
'Upstream API base URL (e.g., https://api.openai.com/v1)'; -- fcg-rewrite

COMMENT ON COLUMN upstream_api_configs.provider IS -- fcg-rewrite
'Provider type for UI display and special handling'; -- fcg-rewrite

COMMENT ON COLUMN proxy_request_logs.upstream_api_config_id IS -- fcg-rewrite
'References the new upstream_api_configs table'; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- Migration complete -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite
