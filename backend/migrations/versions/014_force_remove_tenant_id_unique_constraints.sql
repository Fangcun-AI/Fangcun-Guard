-- Migration: Force remove all unique constraints on tenant_id in risk_type_config -- fcg-rewrite
-- Version: 014 -- fcg-rewrite
-- Date: 2025-11-05 -- fcg-rewrite
-- Author: System -- fcg-rewrite

-- Description: -- fcg-rewrite
-- This migration forcefully removes any remaining unique constraints or indexes -- fcg-rewrite
-- on tenant_id in the risk_type_config table. The error "ix_risk_type_config_user_id" -- fcg-rewrite
-- indicates that an old constraint still exists, preventing multiple applications -- fcg-rewrite
-- under the same tenant from having their own risk_type_config records. -- fcg-rewrite
-- -- fcg-rewrite
-- The correct constraint should be on application_id only (enforced by uq_risk_type_config_application). -- fcg-rewrite

-- Step 1: Drop ALL unique constraints on tenant_id in risk_type_config -- fcg-rewrite
-- This includes any constraint with any name that enforces uniqueness on tenant_id -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    constraint_record RECORD; -- fcg-rewrite
    index_record RECORD; -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Find and drop all unique constraints on tenant_id -- fcg-rewrite
    FOR constraint_record IN -- fcg-rewrite
        SELECT conname, conkey -- fcg-rewrite
        FROM pg_constraint -- fcg-rewrite
        WHERE conrelid = 'risk_type_config'::regclass -- fcg-rewrite
        AND contype = 'u'  -- Unique constraint -- fcg-rewrite
        AND ( -- fcg-rewrite
            -- Check if tenant_id is in the constraint columns -- fcg-rewrite
            array_length(ARRAY(SELECT unnest(conkey)::int), 1) = 1 -- fcg-rewrite
            AND (SELECT attname FROM pg_attribute WHERE attrelid = 'risk_type_config'::regclass AND attnum = (SELECT unnest(conkey)::int)) = 'tenant_id' -- fcg-rewrite
            OR -- fcg-rewrite
            -- Check all columns in the constraint -- fcg-rewrite
            EXISTS ( -- fcg-rewrite
                SELECT 1 FROM unnest(conkey) AS col_num -- fcg-rewrite
                JOIN pg_attribute ON pg_attribute.attrelid = 'risk_type_config'::regclass -- fcg-rewrite
                AND pg_attribute.attnum = col_num -- fcg-rewrite
                WHERE pg_attribute.attname = 'tenant_id' -- fcg-rewrite
            ) -- fcg-rewrite
        ) -- fcg-rewrite
    LOOP -- fcg-rewrite
        EXECUTE format('ALTER TABLE risk_type_config DROP CONSTRAINT IF EXISTS %I', constraint_record.conname); -- fcg-rewrite
        RAISE NOTICE 'Dropped unique constraint: %', constraint_record.conname; -- fcg-rewrite
    END LOOP; -- fcg-rewrite

    -- Find and drop all unique indexes on tenant_id -- fcg-rewrite
    FOR index_record IN -- fcg-rewrite
        SELECT indexname, indexdef -- fcg-rewrite
        FROM pg_indexes -- fcg-rewrite
        WHERE tablename = 'risk_type_config' -- fcg-rewrite
        AND indexdef LIKE '%UNIQUE%' -- fcg-rewrite
        AND ( -- fcg-rewrite
            indexdef LIKE '%tenant_id%' -- fcg-rewrite
            OR indexname LIKE '%tenant_id%' -- fcg-rewrite
            OR indexname LIKE '%user_id%'  -- Also catch old "user_id" named indexes -- fcg-rewrite
        ) -- fcg-rewrite
    LOOP -- fcg-rewrite
        EXECUTE format('DROP INDEX IF EXISTS %I', index_record.indexname); -- fcg-rewrite
        RAISE NOTICE 'Dropped unique index: %', index_record.indexname; -- fcg-rewrite
    END LOOP; -- fcg-rewrite

    -- Specifically target the problematic constraint name from the error -- fcg-rewrite
    DROP INDEX IF EXISTS ix_risk_type_config_user_id; -- fcg-rewrite
    ALTER TABLE risk_type_config DROP CONSTRAINT IF EXISTS ix_risk_type_config_user_id; -- fcg-rewrite
    
    RAISE NOTICE 'Completed cleanup of tenant_id unique constraints'; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Step 2: Ensure we have a regular (non-unique) index on tenant_id for query performance -- fcg-rewrite
CREATE INDEX IF NOT EXISTS ix_risk_type_config_tenant_id ON risk_type_config(tenant_id); -- fcg-rewrite

-- Step 3: Ensure application_id UNIQUE constraint exists (this is the correct constraint) -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint -- fcg-rewrite
        WHERE conname = 'uq_risk_type_config_application' -- fcg-rewrite
        AND conrelid = 'risk_type_config'::regclass -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE risk_type_config ADD CONSTRAINT uq_risk_type_config_application UNIQUE (application_id); -- fcg-rewrite
        RAISE NOTICE 'Added uq_risk_type_config_application constraint'; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'uq_risk_type_config_application constraint already exists'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Step 4: Verify the final state -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    unique_constraints_count INTEGER; -- fcg-rewrite
    tenant_id_unique_count INTEGER; -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Count all unique constraints -- fcg-rewrite
    SELECT COUNT(*) INTO unique_constraints_count -- fcg-rewrite
    FROM pg_constraint -- fcg-rewrite
    WHERE conrelid = 'risk_type_config'::regclass -- fcg-rewrite
    AND contype = 'u'; -- fcg-rewrite

    -- Count unique constraints involving tenant_id -- fcg-rewrite
    SELECT COUNT(*) INTO tenant_id_unique_count -- fcg-rewrite
    FROM pg_constraint -- fcg-rewrite
    WHERE conrelid = 'risk_type_config'::regclass -- fcg-rewrite
    AND contype = 'u' -- fcg-rewrite
    AND EXISTS ( -- fcg-rewrite
        SELECT 1 FROM unnest(conkey) AS col_num -- fcg-rewrite
        JOIN pg_attribute ON pg_attribute.attrelid = 'risk_type_config'::regclass -- fcg-rewrite
        AND pg_attribute.attnum = col_num -- fcg-rewrite
        WHERE pg_attribute.attname = 'tenant_id' -- fcg-rewrite
    ); -- fcg-rewrite

    IF tenant_id_unique_count > 0 THEN -- fcg-rewrite
        RAISE WARNING 'WARNING: Found % unique constraint(s) on tenant_id. This may cause issues.', tenant_id_unique_count; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'SUCCESS: No unique constraints found on tenant_id'; -- fcg-rewrite
    END IF; -- fcg-rewrite

    IF unique_constraints_count = 1 THEN -- fcg-rewrite
        RAISE NOTICE 'SUCCESS: Found exactly 1 unique constraint (should be on application_id)'; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE WARNING 'WARNING: Found % unique constraint(s) (expected 1 on application_id)', unique_constraints_count; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

