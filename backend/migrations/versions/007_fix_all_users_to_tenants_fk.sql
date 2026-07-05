-- Fix ALL foreign key constraints from 'users' table to 'tenants' table -- fcg-rewrite
-- This is a comprehensive fix for the incomplete users->tenants migration -- fcg-rewrite
-- -- fcg-rewrite
-- Migration: 007_fix_all_users_to_tenants_fk -- fcg-rewrite
-- Date: 2025-10-31 -- fcg-rewrite
-- Description: Fix all foreign key constraints to reference tenants table instead of users table -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix blacklist table -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
ALTER TABLE blacklist DROP CONSTRAINT IF EXISTS blacklist_user_id_fkey; -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint WHERE conname = 'blacklist_tenant_id_fkey' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE blacklist ADD CONSTRAINT blacklist_tenant_id_fkey  -- fcg-rewrite
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix knowledge_bases table -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
ALTER TABLE knowledge_bases DROP CONSTRAINT IF EXISTS knowledge_bases_user_id_fkey; -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint WHERE conname = 'knowledge_bases_tenant_id_fkey' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE knowledge_bases ADD CONSTRAINT knowledge_bases_tenant_id_fkey  -- fcg-rewrite
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix online_test_model_selections table -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
ALTER TABLE online_test_model_selections DROP CONSTRAINT IF EXISTS online_test_model_selections_user_id_fkey; -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint WHERE conname = 'online_test_model_selections_tenant_id_fkey' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE online_test_model_selections ADD CONSTRAINT online_test_model_selections_tenant_id_fkey  -- fcg-rewrite
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix proxy_model_configs table (THIS IS THE ONE USER REPORTED) -- fcg-rewrite
-- NOTE: This table was renamed to proxy_model_configs_deprecated in migration 008 -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Only run if table exists (it may have been renamed in later migrations) -- fcg-rewrite
    IF EXISTS ( -- fcg-rewrite
        SELECT 1 FROM information_schema.tables -- fcg-rewrite
        WHERE table_schema = 'public' AND table_name = 'proxy_model_configs' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        EXECUTE 'ALTER TABLE proxy_model_configs DROP CONSTRAINT IF EXISTS proxy_model_configs_user_id_fkey'; -- fcg-rewrite

        IF NOT EXISTS ( -- fcg-rewrite
            SELECT 1 FROM pg_constraint WHERE conname = 'proxy_model_configs_tenant_id_fkey' -- fcg-rewrite
        ) THEN -- fcg-rewrite
            EXECUTE 'ALTER TABLE proxy_model_configs ADD CONSTRAINT proxy_model_configs_tenant_id_fkey -- fcg-rewrite
                FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE'; -- fcg-rewrite
        END IF; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'Table proxy_model_configs does not exist, skipping migration for this table'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix proxy_request_logs table -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
ALTER TABLE proxy_request_logs DROP CONSTRAINT IF EXISTS proxy_request_logs_user_id_fkey; -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint WHERE conname = 'proxy_request_logs_tenant_id_fkey' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE proxy_request_logs ADD CONSTRAINT proxy_request_logs_tenant_id_fkey  -- fcg-rewrite
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix response_templates table -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
ALTER TABLE response_templates DROP CONSTRAINT IF EXISTS response_templates_user_id_fkey; -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint WHERE conname = 'response_templates_tenant_id_fkey' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE response_templates ADD CONSTRAINT response_templates_tenant_id_fkey  -- fcg-rewrite
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix risk_type_config table -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
ALTER TABLE risk_type_config DROP CONSTRAINT IF EXISTS risk_type_config_user_id_fkey; -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint WHERE conname = 'risk_type_config_tenant_id_fkey' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE risk_type_config ADD CONSTRAINT risk_type_config_tenant_id_fkey  -- fcg-rewrite
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix test_model_configs table -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
ALTER TABLE test_model_configs DROP CONSTRAINT IF EXISTS test_model_configs_user_id_fkey; -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint WHERE conname = 'test_model_configs_tenant_id_fkey' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE test_model_configs ADD CONSTRAINT test_model_configs_tenant_id_fkey  -- fcg-rewrite
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix user_rate_limit_counters table (column name is user_id, not tenant_id) -- fcg-rewrite
-- Note: This table uses 'user_id' column name, but should reference tenants table -- fcg-rewrite
-- NOTE: This table may have been renamed to tenant_rate_limit_counters in later migrations -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS ( -- fcg-rewrite
        SELECT 1 FROM information_schema.tables -- fcg-rewrite
        WHERE table_schema = 'public' AND table_name = 'user_rate_limit_counters' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        EXECUTE 'ALTER TABLE user_rate_limit_counters DROP CONSTRAINT IF EXISTS user_rate_limit_counters_user_id_fkey'; -- fcg-rewrite

        IF NOT EXISTS ( -- fcg-rewrite
            SELECT 1 FROM pg_constraint WHERE conname = 'user_rate_limit_counters_user_id_fkey' -- fcg-rewrite
        ) THEN -- fcg-rewrite
            EXECUTE 'ALTER TABLE user_rate_limit_counters ADD CONSTRAINT user_rate_limit_counters_user_id_fkey -- fcg-rewrite
                FOREIGN KEY (user_id) REFERENCES tenants(id) ON DELETE CASCADE'; -- fcg-rewrite
        END IF; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'Table user_rate_limit_counters does not exist, skipping migration for this table'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix user_rate_limits table (column name is user_id, not tenant_id) -- fcg-rewrite
-- Note: This table uses 'user_id' column name, but should reference tenants table -- fcg-rewrite
-- NOTE: This table may have been renamed to tenant_rate_limits in later migrations -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS ( -- fcg-rewrite
        SELECT 1 FROM information_schema.tables -- fcg-rewrite
        WHERE table_schema = 'public' AND table_name = 'user_rate_limits' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        EXECUTE 'ALTER TABLE user_rate_limits DROP CONSTRAINT IF EXISTS user_rate_limits_user_id_fkey'; -- fcg-rewrite

        IF NOT EXISTS ( -- fcg-rewrite
            SELECT 1 FROM pg_constraint WHERE conname = 'user_rate_limits_user_id_fkey' -- fcg-rewrite
        ) THEN -- fcg-rewrite
            EXECUTE 'ALTER TABLE user_rate_limits ADD CONSTRAINT user_rate_limits_user_id_fkey -- fcg-rewrite
                FOREIGN KEY (user_id) REFERENCES tenants(id) ON DELETE CASCADE'; -- fcg-rewrite
        END IF; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'Table user_rate_limits does not exist, skipping migration for this table'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix user_switches table (has two foreign keys to fix) -- fcg-rewrite
-- Note: This table may have been renamed to tenant_switches in later migrations -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF EXISTS ( -- fcg-rewrite
        SELECT 1 FROM information_schema.tables -- fcg-rewrite
        WHERE table_schema = 'public' AND table_name = 'user_switches' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        EXECUTE 'ALTER TABLE user_switches DROP CONSTRAINT IF EXISTS user_switches_admin_user_id_fkey'; -- fcg-rewrite

        IF NOT EXISTS ( -- fcg-rewrite
            SELECT 1 FROM pg_constraint WHERE conname = 'user_switches_admin_user_id_fkey' -- fcg-rewrite
        ) THEN -- fcg-rewrite
            EXECUTE 'ALTER TABLE user_switches ADD CONSTRAINT user_switches_admin_user_id_fkey -- fcg-rewrite
                FOREIGN KEY (admin_user_id) REFERENCES tenants(id) ON DELETE CASCADE'; -- fcg-rewrite
        END IF; -- fcg-rewrite

        EXECUTE 'ALTER TABLE user_switches DROP CONSTRAINT IF EXISTS user_switches_target_user_id_fkey'; -- fcg-rewrite

        IF NOT EXISTS ( -- fcg-rewrite
            SELECT 1 FROM pg_constraint WHERE conname = 'user_switches_target_user_id_fkey' -- fcg-rewrite
        ) THEN -- fcg-rewrite
            EXECUTE 'ALTER TABLE user_switches ADD CONSTRAINT user_switches_target_user_id_fkey -- fcg-rewrite
                FOREIGN KEY (target_user_id) REFERENCES tenants(id) ON DELETE CASCADE'; -- fcg-rewrite
        END IF; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'Table user_switches does not exist, skipping migration for this table'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- Fix whitelist table -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
ALTER TABLE whitelist DROP CONSTRAINT IF EXISTS whitelist_user_id_fkey; -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint WHERE conname = 'whitelist_tenant_id_fkey' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE whitelist ADD CONSTRAINT whitelist_tenant_id_fkey  -- fcg-rewrite
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================ -- fcg-rewrite
-- SUMMARY -- fcg-rewrite
-- ============================================================ -- fcg-rewrite
-- This migration fixed foreign key constraints for 13 tables -- fcg-rewrite
-- All tables now correctly reference the 'tenants' table instead of 'users' table -- fcg-rewrite
-- The 'users' table can potentially be dropped after this migration -- fcg-rewrite
-- (but we'll keep it for now for safety) -- fcg-rewrite

