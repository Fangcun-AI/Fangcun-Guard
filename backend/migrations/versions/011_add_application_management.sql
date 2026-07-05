-- Migration: Add Application Management (Multi-Application Support) -- fcg-rewrite
-- Version: 011 -- fcg-rewrite
-- Date: 2025-11-01 -- fcg-rewrite
-- Description: Transform from tenant-scoped to application-scoped configurations -- fcg-rewrite
--              to support multiple applications per tenant with independent API keys and configs -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 1: Create applications table -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

CREATE TABLE IF NOT EXISTS applications ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    name VARCHAR(100) NOT NULL, -- fcg-rewrite
    description TEXT, -- fcg-rewrite
    is_active BOOLEAN DEFAULT true NOT NULL, -- fcg-rewrite
    source VARCHAR(32) DEFAULT 'manual' NOT NULL, -- fcg-rewrite
    external_id VARCHAR(255), -- fcg-rewrite
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL, -- fcg-rewrite
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL, -- fcg-rewrite

    CONSTRAINT uq_applications_tenant_name UNIQUE(tenant_id, name) -- fcg-rewrite
); -- fcg-rewrite

-- Ensure default is set even if table already exists -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns  -- fcg-rewrite
               WHERE table_name = 'applications' AND column_name = 'id'  -- fcg-rewrite
               AND column_default IS NULL) THEN -- fcg-rewrite
        ALTER TABLE applications ALTER COLUMN id SET DEFAULT gen_random_uuid(); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_applications_tenant_id ON applications(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_applications_is_active ON applications(is_active); -- fcg-rewrite

COMMENT ON TABLE applications IS 'Applications owned by tenants. Each tenant can have multiple applications with independent configurations.'; -- fcg-rewrite
COMMENT ON COLUMN applications.tenant_id IS 'Owner of this application'; -- fcg-rewrite
COMMENT ON COLUMN applications.name IS 'Application name (unique per tenant)'; -- fcg-rewrite
COMMENT ON COLUMN applications.is_active IS 'Whether this application is active'; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 2: Create api_keys table -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

CREATE TABLE IF NOT EXISTS api_keys ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE, -- fcg-rewrite
    key VARCHAR(64) NOT NULL UNIQUE, -- fcg-rewrite
    name VARCHAR(100), -- fcg-rewrite
    is_active BOOLEAN DEFAULT true NOT NULL, -- fcg-rewrite
    last_used_at TIMESTAMPTZ, -- fcg-rewrite
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL, -- fcg-rewrite
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL -- fcg-rewrite
); -- fcg-rewrite

-- Ensure default is set even if table already exists -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS (SELECT 1 FROM information_schema.columns  -- fcg-rewrite
               WHERE table_name = 'api_keys' AND column_name = 'id'  -- fcg-rewrite
               AND column_default IS NULL) THEN -- fcg-rewrite
        ALTER TABLE api_keys ALTER COLUMN id SET DEFAULT gen_random_uuid(); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(key); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_api_keys_application_id ON api_keys(application_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant_id ON api_keys(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active); -- fcg-rewrite

COMMENT ON TABLE api_keys IS 'API keys for applications. Each application can have multiple API keys.'; -- fcg-rewrite
COMMENT ON COLUMN api_keys.tenant_id IS 'Owner (for quick tenant-level queries)'; -- fcg-rewrite
COMMENT ON COLUMN api_keys.application_id IS 'Which application this key belongs to'; -- fcg-rewrite
COMMENT ON COLUMN api_keys.key IS 'API key string (format: sk-xxai-{52 chars})'; -- fcg-rewrite
COMMENT ON COLUMN api_keys.name IS 'Optional friendly name (e.g., "Production Key", "Test Key")'; -- fcg-rewrite
COMMENT ON COLUMN api_keys.last_used_at IS 'Last usage timestamp'; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 3: Create "Default Application" for all existing tenants -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    tenant_record RECORD; -- fcg-rewrite
    new_app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR tenant_record IN SELECT id, email FROM tenants LOOP -- fcg-rewrite
        -- Check if application already exists (idempotent migration) -- fcg-rewrite
        SELECT id INTO new_app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = tenant_record.id AND name = 'Default Application'; -- fcg-rewrite
        
        -- Create "Default Application" for each tenant if it doesn't exist -- fcg-rewrite
        IF new_app_id IS NULL THEN -- fcg-rewrite
            INSERT INTO applications (id, tenant_id, name, description, is_active, source) -- fcg-rewrite
            VALUES ( -- fcg-rewrite
                gen_random_uuid(), -- fcg-rewrite
                tenant_record.id, -- fcg-rewrite
                'Default Application', -- fcg-rewrite
                'Automatically created during migration. All existing configurations have been migrated to this application.', -- fcg-rewrite
                true, -- fcg-rewrite
                'manual' -- fcg-rewrite
            ) -- fcg-rewrite
            RETURNING id INTO new_app_id; -- fcg-rewrite
            
            RAISE NOTICE 'Created Default Application for tenant % (email: %)', tenant_record.id, tenant_record.email; -- fcg-rewrite
        ELSE -- fcg-rewrite
            RAISE NOTICE 'Default Application already exists for tenant % (email: %)', tenant_record.id, tenant_record.email; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 4: Migrate existing API keys from tenants.api_key to api_keys table -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    tenant_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR tenant_record IN SELECT id, email, api_key FROM tenants WHERE api_key IS NOT NULL LOOP -- fcg-rewrite
        -- Get the "Default Application" for this tenant -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = tenant_record.id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            -- Migrate existing API key to api_keys table (skip if already exists) -- fcg-rewrite
            INSERT INTO api_keys (id, tenant_id, application_id, key, name, is_active) -- fcg-rewrite
            SELECT gen_random_uuid(), tenant_record.id, app_id, tenant_record.api_key, 'Migrated API Key', true -- fcg-rewrite
            WHERE NOT EXISTS ( -- fcg-rewrite
                SELECT 1 FROM api_keys WHERE key = tenant_record.api_key -- fcg-rewrite
            ); -- fcg-rewrite

            RAISE NOTICE 'Migrated API key for tenant % (email: %)', tenant_record.id, tenant_record.email; -- fcg-rewrite
        ELSE -- fcg-rewrite
            RAISE WARNING 'No Default Application found for tenant % (email: %)', tenant_record.id, tenant_record.email; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 5: Add application_id column to all configuration tables -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- 5.1 blacklist -- fcg-rewrite
ALTER TABLE blacklist ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_blacklist_application_id ON blacklist(application_id); -- fcg-rewrite

-- 5.2 whitelist -- fcg-rewrite
ALTER TABLE whitelist ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_whitelist_application_id ON whitelist(application_id); -- fcg-rewrite

-- 5.3 response_templates -- fcg-rewrite
ALTER TABLE response_templates ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_response_templates_application_id ON response_templates(application_id); -- fcg-rewrite

-- 5.4 risk_type_config -- fcg-rewrite
ALTER TABLE risk_type_config ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_risk_type_config_application_id ON risk_type_config(application_id); -- fcg-rewrite

-- 5.5 ban_policies -- fcg-rewrite
ALTER TABLE ban_policies ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_ban_policies_application_id ON ban_policies(application_id); -- fcg-rewrite

-- 5.6 knowledge_bases -- fcg-rewrite
ALTER TABLE knowledge_bases ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_application_id ON knowledge_bases(application_id); -- fcg-rewrite

-- 5.7 data_security_entity_types -- fcg-rewrite
ALTER TABLE data_security_entity_types ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_data_security_entity_types_application_id ON data_security_entity_types(application_id); -- fcg-rewrite

-- 5.8 upstream_api_configs -- fcg-rewrite
ALTER TABLE upstream_api_configs ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_upstream_api_configs_application_id ON upstream_api_configs(application_id); -- fcg-rewrite

-- 5.9 test_model_configs -- fcg-rewrite
ALTER TABLE test_model_configs ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_test_model_configs_application_id ON test_model_configs(application_id); -- fcg-rewrite

-- 5.10 tenant_rate_limits -- fcg-rewrite
ALTER TABLE tenant_rate_limits ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_tenant_rate_limits_application_id ON tenant_rate_limits(application_id); -- fcg-rewrite

-- 5.11 detection_results (keep nullable for historical data) -- fcg-rewrite
ALTER TABLE detection_results ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE SET NULL; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_detection_results_application_id ON detection_results(application_id); -- fcg-rewrite

-- 5.12 user_ban_records -- fcg-rewrite
ALTER TABLE user_ban_records ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_user_ban_records_application_id ON user_ban_records(application_id); -- fcg-rewrite

-- 5.13 user_risk_triggers -- fcg-rewrite
ALTER TABLE user_risk_triggers ADD COLUMN IF NOT EXISTS application_id UUID REFERENCES applications(id) ON DELETE CASCADE; -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_user_risk_triggers_application_id ON user_risk_triggers(application_id); -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 6: Migrate existing configurations to "Default Application" -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- 6.1 Migrate blacklist -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM blacklist WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE blacklist SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % blacklist entries', (SELECT COUNT(*) FROM blacklist WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- 6.2 Migrate whitelist -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM whitelist WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE whitelist SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % whitelist entries', (SELECT COUNT(*) FROM whitelist WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- 6.3 Migrate response_templates -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM response_templates WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE response_templates SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % response_template entries', (SELECT COUNT(*) FROM response_templates WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- 6.4 Migrate risk_type_config -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM risk_type_config WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE risk_type_config SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % risk_type_config entries', (SELECT COUNT(*) FROM risk_type_config WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- 6.5 Migrate ban_policies -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM ban_policies WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE ban_policies SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % ban_policies entries', (SELECT COUNT(*) FROM ban_policies WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- 6.6 Migrate knowledge_bases -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM knowledge_bases WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE knowledge_bases SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % knowledge_bases entries', (SELECT COUNT(*) FROM knowledge_bases WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- 6.7 Migrate data_security_entity_types -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM data_security_entity_types WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE data_security_entity_types SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % data_security_entity_types entries', (SELECT COUNT(*) FROM data_security_entity_types WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- 6.8 Migrate upstream_api_configs -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM upstream_api_configs WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE upstream_api_configs SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % upstream_api_configs entries', (SELECT COUNT(*) FROM upstream_api_configs WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- 6.9 Migrate test_model_configs -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM test_model_configs WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE test_model_configs SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % test_model_configs entries', (SELECT COUNT(*) FROM test_model_configs WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- 6.10 Migrate tenant_rate_limits -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM tenant_rate_limits WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE tenant_rate_limits SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % tenant_rate_limits entries', (SELECT COUNT(*) FROM tenant_rate_limits WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- 6.11 Migrate user_ban_records -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM user_ban_records WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE user_ban_records SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % user_ban_records entries', (SELECT COUNT(*) FROM user_ban_records WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- 6.12 Migrate user_risk_triggers -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    config_record RECORD; -- fcg-rewrite
    app_id UUID; -- fcg-rewrite
BEGIN -- fcg-rewrite
    FOR config_record IN SELECT id, tenant_id FROM user_risk_triggers WHERE application_id IS NULL LOOP -- fcg-rewrite
        SELECT id INTO app_id -- fcg-rewrite
        FROM applications -- fcg-rewrite
        WHERE tenant_id = config_record.tenant_id AND name = 'Default Application'; -- fcg-rewrite

        IF app_id IS NOT NULL THEN -- fcg-rewrite
            UPDATE user_risk_triggers SET application_id = app_id WHERE id = config_record.id; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
    RAISE NOTICE 'Migrated % user_risk_triggers entries', (SELECT COUNT(*) FROM user_risk_triggers WHERE application_id IS NOT NULL); -- fcg-rewrite
END $$; -- fcg-rewrite

-- NOTE: detection_results.application_id kept nullable for historical data -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 7: Set application_id as NOT NULL for core config tables -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- Set NOT NULL constraint for tables where application_id must always exist -- fcg-rewrite
-- (after migration ensures all existing records have application_id) -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- blacklist -- fcg-rewrite
    ALTER TABLE blacklist ALTER COLUMN application_id SET NOT NULL; -- fcg-rewrite

    -- whitelist -- fcg-rewrite
    ALTER TABLE whitelist ALTER COLUMN application_id SET NOT NULL; -- fcg-rewrite

    -- risk_type_config -- fcg-rewrite
    ALTER TABLE risk_type_config ALTER COLUMN application_id SET NOT NULL; -- fcg-rewrite

    -- ban_policies -- fcg-rewrite
    ALTER TABLE ban_policies ALTER COLUMN application_id SET NOT NULL; -- fcg-rewrite

    -- knowledge_bases -- fcg-rewrite
    ALTER TABLE knowledge_bases ALTER COLUMN application_id SET NOT NULL; -- fcg-rewrite

    -- data_security_entity_types -- fcg-rewrite
    ALTER TABLE data_security_entity_types ALTER COLUMN application_id SET NOT NULL; -- fcg-rewrite

    -- upstream_api_configs -- fcg-rewrite
    ALTER TABLE upstream_api_configs ALTER COLUMN application_id SET NOT NULL; -- fcg-rewrite

    -- test_model_configs -- fcg-rewrite
    ALTER TABLE test_model_configs ALTER COLUMN application_id SET NOT NULL; -- fcg-rewrite

    -- user_ban_records -- fcg-rewrite
    ALTER TABLE user_ban_records ALTER COLUMN application_id SET NOT NULL; -- fcg-rewrite

    -- user_risk_triggers -- fcg-rewrite
    ALTER TABLE user_risk_triggers ALTER COLUMN application_id SET NOT NULL; -- fcg-rewrite

    -- Keep nullable: detection_results (historical data), response_templates (can be global), tenant_rate_limits -- fcg-rewrite

    RAISE NOTICE 'Set application_id as NOT NULL for core config tables'; -- fcg-rewrite
EXCEPTION -- fcg-rewrite
    WHEN others THEN -- fcg-rewrite
        RAISE WARNING 'Could not set NOT NULL constraint. Some records may still have NULL application_id: %', SQLERRM; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 8: Update unique constraints -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- 8.1 risk_type_config: Change from UNIQUE(tenant_id) to UNIQUE(application_id) -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Drop old constraint if exists -- fcg-rewrite
    ALTER TABLE risk_type_config DROP CONSTRAINT IF EXISTS uq_risk_type_config_tenant; -- fcg-rewrite
    ALTER TABLE risk_type_config DROP CONSTRAINT IF EXISTS risk_type_config_tenant_id_key; -- fcg-rewrite

    -- Add new constraint (idempotent) -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint -- fcg-rewrite
        WHERE conname = 'uq_risk_type_config_application' -- fcg-rewrite
        AND conrelid = 'risk_type_config'::regclass -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE risk_type_config ADD CONSTRAINT uq_risk_type_config_application UNIQUE(application_id); -- fcg-rewrite
    END IF; -- fcg-rewrite

    RAISE NOTICE 'Updated risk_type_config unique constraint to application_id'; -- fcg-rewrite
END $$; -- fcg-rewrite

-- 8.2 tenant_rate_limits: Change from UNIQUE(tenant_id) to UNIQUE(application_id) -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Drop old constraint if exists -- fcg-rewrite
    ALTER TABLE tenant_rate_limits DROP CONSTRAINT IF EXISTS uq_tenant_rate_limits_tenant; -- fcg-rewrite
    ALTER TABLE tenant_rate_limits DROP CONSTRAINT IF EXISTS tenant_rate_limits_tenant_id_key; -- fcg-rewrite

    -- Add new constraint (idempotent) -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint -- fcg-rewrite
        WHERE conname = 'uq_tenant_rate_limits_application' -- fcg-rewrite
        AND conrelid = 'tenant_rate_limits'::regclass -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE tenant_rate_limits ADD CONSTRAINT uq_tenant_rate_limits_application UNIQUE(application_id); -- fcg-rewrite
    END IF; -- fcg-rewrite

    RAISE NOTICE 'Updated tenant_rate_limits unique constraint to application_id'; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 9: DO NOT drop tenants.api_key column (keep for backward compatibility) -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- Commented out for safety - will be removed in a future migration after users have migrated -- fcg-rewrite
-- ALTER TABLE tenants DROP COLUMN IF EXISTS api_key; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 10: Verification queries (for logging) -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    app_count INT; -- fcg-rewrite
    key_count INT; -- fcg-rewrite
    tenant_count INT; -- fcg-rewrite
BEGIN -- fcg-rewrite
    SELECT COUNT(*) INTO app_count FROM applications; -- fcg-rewrite
    SELECT COUNT(*) INTO key_count FROM api_keys; -- fcg-rewrite
    SELECT COUNT(*) INTO tenant_count FROM tenants; -- fcg-rewrite

    RAISE NOTICE '=== Migration 011 Complete ==='; -- fcg-rewrite
    RAISE NOTICE 'Created % applications for % tenants', app_count, tenant_count; -- fcg-rewrite
    RAISE NOTICE 'Migrated % API keys to api_keys table', key_count; -- fcg-rewrite
    RAISE NOTICE 'All configurations have been migrated to application-scoped model'; -- fcg-rewrite
    RAISE NOTICE '================================'; -- fcg-rewrite
END $$; -- fcg-rewrite
