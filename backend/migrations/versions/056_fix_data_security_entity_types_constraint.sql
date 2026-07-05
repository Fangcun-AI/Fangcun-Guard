-- Migration: Fix application_id constraint for global system templates in data_security_entity_types -- fcg-rewrite
-- Version: 056 -- fcg-rewrite
-- Date: 2025-11-19 (renumbered from 028 to fix duplicate version) -- fcg-rewrite
-- Description: Allow NULL application_id for global system templates (source_type='system_template') -- fcg-rewrite
--              This fixes the constraint violation that prevents creation of global entity types -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 1: Make application_id nullable for global system templates -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- First, let's check if there are any existing records that would be affected -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    affected_count INTEGER; -- fcg-rewrite
BEGIN -- fcg-rewrite
    SELECT COUNT(*) INTO affected_count -- fcg-rewrite
    FROM data_security_entity_types -- fcg-rewrite
    WHERE source_type = 'system_template' AND application_id IS NOT NULL; -- fcg-rewrite

    IF affected_count > 0 THEN -- fcg-rewrite
        RAISE NOTICE 'Found % system_template records with non-null application_id - this should not happen', affected_count; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'No conflicting system_template records found'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 2: Remove the NOT NULL constraint to allow NULL for global templates -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Remove the NOT NULL constraint from application_id -- fcg-rewrite
    -- This will allow NULL values for global system templates -- fcg-rewrite
    ALTER TABLE data_security_entity_types ALTER COLUMN application_id DROP NOT NULL; -- fcg-rewrite

    RAISE NOTICE 'Removed NOT NULL constraint from data_security_entity_types.application_id'; -- fcg-rewrite
EXCEPTION -- fcg-rewrite
    WHEN others THEN -- fcg-rewrite
        -- If constraint doesn't exist or other error, continue -- fcg-rewrite
        RAISE NOTICE 'Could not remove NOT NULL constraint (may not exist): %', SQLERRM; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 3: Create global system entity type templates -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

-- Get the super admin tenant ID to use as the creator -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    admin_tenant_id UUID; -- fcg-rewrite
    created_count INTEGER := 0; -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Find super admin tenant -- fcg-rewrite
    SELECT id INTO admin_tenant_id -- fcg-rewrite
    FROM tenants -- fcg-rewrite
    WHERE is_super_admin = true -- fcg-rewrite
    LIMIT 1; -- fcg-rewrite

    IF admin_tenant_id IS NULL THEN -- fcg-rewrite
        RAISE WARNING 'No super admin tenant found - cannot create system templates'; -- fcg-rewrite
        RETURN; -- fcg-rewrite
    END IF; -- fcg-rewrite

    RAISE NOTICE 'Creating global system entity types for admin tenant: %', admin_tenant_id; -- fcg-rewrite

    -- Insert US Bank Number template (the one that was failing) -- fcg-rewrite
    INSERT INTO data_security_entity_types ( -- fcg-rewrite
        id, -- fcg-rewrite
        tenant_id, -- fcg-rewrite
        application_id,  -- NULL for global templates -- fcg-rewrite
        entity_type, -- fcg-rewrite
        entity_type_name, -- fcg-rewrite
        category, -- fcg-rewrite
        recognition_method, -- fcg-rewrite
        recognition_config, -- fcg-rewrite
        anonymization_method, -- fcg-rewrite
        anonymization_config, -- fcg-rewrite
        is_active, -- fcg-rewrite
        is_global, -- fcg-rewrite
        source_type, -- fcg-rewrite
        template_id -- fcg-rewrite
    ) SELECT -- fcg-rewrite
        gen_random_uuid(), -- fcg-rewrite
        admin_tenant_id, -- fcg-rewrite
        NULL,  -- NULL for global system templates -- fcg-rewrite
        'US_BANK_NUMBER_SYS', -- fcg-rewrite
        'US BANK NUMBER', -- fcg-rewrite
        'medium', -- fcg-rewrite
        'regex', -- fcg-rewrite
        '{"pattern": "\\d{8,19}", "check_input": true, "check_output": true}', -- fcg-rewrite
        'replace', -- fcg-rewrite
        '{}', -- fcg-rewrite
        true, -- fcg-rewrite
        true, -- fcg-rewrite
        'system_template', -- fcg-rewrite
        NULL -- fcg-rewrite
    WHERE NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM data_security_entity_types -- fcg-rewrite
        WHERE entity_type = 'US_BANK_NUMBER_SYS' AND source_type = 'system_template' -- fcg-rewrite
    ); -- fcg-rewrite

    IF FOUND THEN -- fcg-rewrite
        created_count := created_count + 1; -- fcg-rewrite
    END IF; -- fcg-rewrite

    -- Insert other common system templates -- fcg-rewrite
    INSERT INTO data_security_entity_types ( -- fcg-rewrite
        id, -- fcg-rewrite
        tenant_id, -- fcg-rewrite
        application_id,  -- NULL for global templates -- fcg-rewrite
        entity_type, -- fcg-rewrite
        entity_type_name, -- fcg-rewrite
        category, -- fcg-rewrite
        recognition_method, -- fcg-rewrite
        recognition_config, -- fcg-rewrite
        anonymization_method, -- fcg-rewrite
        anonymization_config, -- fcg-rewrite
        is_active, -- fcg-rewrite
        is_global, -- fcg-rewrite
        source_type, -- fcg-rewrite
        template_id -- fcg-rewrite
    ) SELECT -- fcg-rewrite
        gen_random_uuid(), -- fcg-rewrite
        admin_tenant_id, -- fcg-rewrite
        NULL,  -- NULL for global system templates -- fcg-rewrite
        'ID_CARD_NUMBER_SYS', -- fcg-rewrite
        'ID Card Number', -- fcg-rewrite
        'high', -- fcg-rewrite
        'regex', -- fcg-rewrite
        '{"pattern": "[1-8]\\d{5}(19|20)\\d{2}((0[1-9])|(1[0-2]))((0[1-9])|([12]\\d)|(3[01]))\\d{3}[\\dxX]", "check_input": true, "check_output": true}', -- fcg-rewrite
        'mask', -- fcg-rewrite
        '{"mask_char": "*", "keep_prefix": 3, "keep_suffix": 4}', -- fcg-rewrite
        true, -- fcg-rewrite
        true, -- fcg-rewrite
        'system_template', -- fcg-rewrite
        NULL -- fcg-rewrite
    WHERE NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM data_security_entity_types -- fcg-rewrite
        WHERE entity_type = 'ID_CARD_NUMBER_SYS' AND source_type = 'system_template' -- fcg-rewrite
    ); -- fcg-rewrite

    IF FOUND THEN -- fcg-rewrite
        created_count := created_count + 1; -- fcg-rewrite
    END IF; -- fcg-rewrite

    INSERT INTO data_security_entity_types ( -- fcg-rewrite
        id, -- fcg-rewrite
        tenant_id, -- fcg-rewrite
        application_id,  -- NULL for global templates -- fcg-rewrite
        entity_type, -- fcg-rewrite
        entity_type_name, -- fcg-rewrite
        category, -- fcg-rewrite
        recognition_method, -- fcg-rewrite
        recognition_config, -- fcg-rewrite
        anonymization_method, -- fcg-rewrite
        anonymization_config, -- fcg-rewrite
        is_active, -- fcg-rewrite
        is_global, -- fcg-rewrite
        source_type, -- fcg-rewrite
        template_id -- fcg-rewrite
    ) SELECT -- fcg-rewrite
        gen_random_uuid(), -- fcg-rewrite
        admin_tenant_id, -- fcg-rewrite
        NULL,  -- NULL for global system templates -- fcg-rewrite
        'PHONE_NUMBER_SYS', -- fcg-rewrite
        'Phone Number', -- fcg-rewrite
        'medium', -- fcg-rewrite
        'regex', -- fcg-rewrite
        '{"pattern": "1[3-9]\\d{9}", "check_input": true, "check_output": true}', -- fcg-rewrite
        'mask', -- fcg-rewrite
        '{"mask_char": "*", "keep_prefix": 3, "keep_suffix": 4}', -- fcg-rewrite
        true, -- fcg-rewrite
        true, -- fcg-rewrite
        'system_template', -- fcg-rewrite
        NULL -- fcg-rewrite
    WHERE NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM data_security_entity_types -- fcg-rewrite
        WHERE entity_type = 'PHONE_NUMBER_SYS' AND source_type = 'system_template' -- fcg-rewrite
    ); -- fcg-rewrite

    IF FOUND THEN -- fcg-rewrite
        created_count := created_count + 1; -- fcg-rewrite
    END IF; -- fcg-rewrite

    INSERT INTO data_security_entity_types ( -- fcg-rewrite
        id, -- fcg-rewrite
        tenant_id, -- fcg-rewrite
        application_id,  -- NULL for global templates -- fcg-rewrite
        entity_type, -- fcg-rewrite
        entity_type_name, -- fcg-rewrite
        category, -- fcg-rewrite
        recognition_method, -- fcg-rewrite
        recognition_config, -- fcg-rewrite
        anonymization_method, -- fcg-rewrite
        anonymization_config, -- fcg-rewrite
        is_active, -- fcg-rewrite
        is_global, -- fcg-rewrite
        source_type, -- fcg-rewrite
        template_id -- fcg-rewrite
    ) SELECT -- fcg-rewrite
        gen_random_uuid(), -- fcg-rewrite
        admin_tenant_id, -- fcg-rewrite
        NULL,  -- NULL for global system templates -- fcg-rewrite
        'EMAIL_SYS', -- fcg-rewrite
        'Email', -- fcg-rewrite
        'low', -- fcg-rewrite
        'regex', -- fcg-rewrite
        '{"pattern": "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\\.[a-zA-Z]{2,}", "check_input": true, "check_output": true}', -- fcg-rewrite
        'mask', -- fcg-rewrite
        '{"mask_char": "*", "keep_prefix": 2, "keep_suffix": 0}', -- fcg-rewrite
        true, -- fcg-rewrite
        true, -- fcg-rewrite
        'system_template', -- fcg-rewrite
        NULL -- fcg-rewrite
    WHERE NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM data_security_entity_types -- fcg-rewrite
        WHERE entity_type = 'EMAIL_SYS' AND source_type = 'system_template' -- fcg-rewrite
    ); -- fcg-rewrite

    IF FOUND THEN -- fcg-rewrite
        created_count := created_count + 1; -- fcg-rewrite
    END IF; -- fcg-rewrite

    RAISE NOTICE 'Created % global system entity type templates', created_count; -- fcg-rewrite

END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 4: Verification -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    template_count INTEGER; -- fcg-rewrite
    global_count INTEGER; -- fcg-rewrite
BEGIN -- fcg-rewrite
    SELECT COUNT(*) INTO template_count -- fcg-rewrite
    FROM data_security_entity_types -- fcg-rewrite
    WHERE source_type = 'system_template'; -- fcg-rewrite

    SELECT COUNT(*) INTO global_count -- fcg-rewrite
    FROM data_security_entity_types -- fcg-rewrite
    WHERE is_global = true; -- fcg-rewrite

    RAISE NOTICE '=== Migration 056 Complete ==='; -- fcg-rewrite
    RAISE NOTICE 'System templates: %', template_count; -- fcg-rewrite
    RAISE NOTICE 'Global entity types: %', global_count; -- fcg-rewrite
    RAISE NOTICE 'application_id constraint now allows NULL for global templates'; -- fcg-rewrite
    RAISE NOTICE '================================'; -- fcg-rewrite
END $$; -- fcg-rewrite