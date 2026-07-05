-- Migration: Fix US_BANK_NUMBER_SYS pattern in all records (templates and copies) -- fcg-rewrite
-- Version: 030 -- fcg-rewrite
-- Date: 2025-11-20 -- fcg-rewrite
-- Description: Update the regex pattern for US_BANK_NUMBER_SYS from \d{8,17} to \d{8,19} -- fcg-rewrite
--              in ALL records including system templates, system copies, and custom instances -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 1: Update ALL US_BANK_NUMBER_SYS records -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    updated_count INTEGER := 0; -- fcg-rewrite
    total_count INTEGER := 0; -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Count total records before update -- fcg-rewrite
    SELECT COUNT(*) INTO total_count -- fcg-rewrite
    FROM data_security_entity_types -- fcg-rewrite
    WHERE entity_type = 'US_BANK_NUMBER_SYS'; -- fcg-rewrite
    
    RAISE NOTICE 'Found % total US_BANK_NUMBER_SYS records', total_count; -- fcg-rewrite
    
    -- Update ALL US_BANK_NUMBER_SYS records regardless of source_type -- fcg-rewrite
    -- This includes system_template, system_copy, and any custom instances -- fcg-rewrite
    UPDATE data_security_entity_types -- fcg-rewrite
    SET recognition_config = jsonb_set( -- fcg-rewrite
        recognition_config::jsonb, -- fcg-rewrite
        '{pattern}', -- fcg-rewrite
        to_jsonb('\d{8,19}'::text) -- fcg-rewrite
    )::json -- fcg-rewrite
    WHERE entity_type = 'US_BANK_NUMBER_SYS' -- fcg-rewrite
    AND ( -- fcg-rewrite
        recognition_config->>'pattern' = '\d{8,17}'  -- fcg-rewrite
        OR recognition_config->>'pattern' = '\\d{8,17}' -- fcg-rewrite
        OR recognition_config->>'pattern' LIKE '%8,17%' -- fcg-rewrite
    ); -- fcg-rewrite
    
    GET DIAGNOSTICS updated_count = ROW_COUNT; -- fcg-rewrite
    
    RAISE NOTICE 'Updated % US_BANK_NUMBER_SYS records with corrected pattern', updated_count; -- fcg-rewrite
    
    IF updated_count = 0 THEN -- fcg-rewrite
        RAISE NOTICE 'No records needed updating (pattern may already be correct)'; -- fcg-rewrite
    ELSIF updated_count < total_count THEN -- fcg-rewrite
        RAISE NOTICE '% records were already correct', (total_count - updated_count); -- fcg-rewrite
    END IF; -- fcg-rewrite
    
EXCEPTION -- fcg-rewrite
    WHEN others THEN -- fcg-rewrite
        RAISE WARNING 'Error updating US_BANK_NUMBER_SYS pattern: %', SQLERRM; -- fcg-rewrite
        RAISE; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 2: Verification -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    correct_pattern_count INTEGER; -- fcg-rewrite
    old_pattern_count INTEGER; -- fcg-rewrite
    total_count INTEGER; -- fcg-rewrite
    template_correct INTEGER; -- fcg-rewrite
    copy_correct INTEGER; -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Count total records -- fcg-rewrite
    SELECT COUNT(*) INTO total_count -- fcg-rewrite
    FROM data_security_entity_types -- fcg-rewrite
    WHERE entity_type = 'US_BANK_NUMBER_SYS'; -- fcg-rewrite
    
    -- Count records with the new correct pattern -- fcg-rewrite
    SELECT COUNT(*) INTO correct_pattern_count -- fcg-rewrite
    FROM data_security_entity_types -- fcg-rewrite
    WHERE entity_type = 'US_BANK_NUMBER_SYS' -- fcg-rewrite
    AND recognition_config->>'pattern' = '\d{8,19}'; -- fcg-rewrite
    
    -- Count records still with the old pattern -- fcg-rewrite
    SELECT COUNT(*) INTO old_pattern_count -- fcg-rewrite
    FROM data_security_entity_types -- fcg-rewrite
    WHERE entity_type = 'US_BANK_NUMBER_SYS' -- fcg-rewrite
    AND ( -- fcg-rewrite
        recognition_config->>'pattern' = '\d{8,17}' -- fcg-rewrite
        OR recognition_config->>'pattern' LIKE '%8,17%' -- fcg-rewrite
    ); -- fcg-rewrite
    
    -- Count templates with correct pattern -- fcg-rewrite
    SELECT COUNT(*) INTO template_correct -- fcg-rewrite
    FROM data_security_entity_types -- fcg-rewrite
    WHERE entity_type = 'US_BANK_NUMBER_SYS' -- fcg-rewrite
    AND source_type = 'system_template' -- fcg-rewrite
    AND recognition_config->>'pattern' = '\d{8,19}'; -- fcg-rewrite
    
    -- Count copies with correct pattern -- fcg-rewrite
    SELECT COUNT(*) INTO copy_correct -- fcg-rewrite
    FROM data_security_entity_types -- fcg-rewrite
    WHERE entity_type = 'US_BANK_NUMBER_SYS' -- fcg-rewrite
    AND source_type = 'system_copy' -- fcg-rewrite
    AND recognition_config->>'pattern' = '\d{8,19}'; -- fcg-rewrite
    
    RAISE NOTICE '=== Migration 030 Complete ==='; -- fcg-rewrite
    RAISE NOTICE 'Total US_BANK_NUMBER_SYS records: %', total_count; -- fcg-rewrite
    RAISE NOTICE 'Records with correct pattern (\d{8,19}): %', correct_pattern_count; -- fcg-rewrite
    RAISE NOTICE 'Records with old pattern (\d{8,17}): %', old_pattern_count; -- fcg-rewrite
    RAISE NOTICE 'System templates corrected: %', template_correct; -- fcg-rewrite
    RAISE NOTICE 'System copies corrected: %', copy_correct; -- fcg-rewrite
    
    IF old_pattern_count > 0 THEN -- fcg-rewrite
        RAISE WARNING 'Some records still have the old pattern - manual review may be needed'; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'All records successfully updated!'; -- fcg-rewrite
    END IF; -- fcg-rewrite
    
    RAISE NOTICE '================================'; -- fcg-rewrite
END $$; -- fcg-rewrite

