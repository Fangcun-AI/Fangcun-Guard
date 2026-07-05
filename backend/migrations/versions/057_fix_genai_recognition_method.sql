-- Migration: Fix recognition_method for genai entity types -- fcg-rewrite
-- Version: 057 -- fcg-rewrite
-- Date: 2026-01-04 (renumbered from 029 to fix duplicate version) -- fcg-rewrite
-- Description: Correct recognition_method from 'regex' to 'genai' for entities that have: -- fcg-rewrite
--              1. anonymization_method = 'genai', OR -- fcg-rewrite
--              2. entity_definition in recognition_config but no pattern -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 1: Find and fix entities with genai anonymization but regex recognition -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    fixed_count INTEGER := 0; -- fcg-rewrite
    entity_record RECORD; -- fcg-rewrite
BEGIN -- fcg-rewrite
    RAISE NOTICE 'Starting fix for genai recognition_method...'; -- fcg-rewrite

    -- Fix entities where anonymization_method is 'genai' but recognition_method is 'regex' -- fcg-rewrite
    FOR entity_record IN -- fcg-rewrite
        SELECT id, entity_type, entity_type_name, recognition_method, anonymization_method, recognition_config -- fcg-rewrite
        FROM data_security_entity_types -- fcg-rewrite
        WHERE recognition_method = 'regex' -- fcg-rewrite
          AND anonymization_method = 'genai' -- fcg-rewrite
    LOOP -- fcg-rewrite
        -- Update recognition_method to 'genai' -- fcg-rewrite
        UPDATE data_security_entity_types -- fcg-rewrite
        SET recognition_method = 'genai', -- fcg-rewrite
            updated_at = NOW() -- fcg-rewrite
        WHERE id = entity_record.id; -- fcg-rewrite

        fixed_count := fixed_count + 1; -- fcg-rewrite
        RAISE NOTICE 'Fixed entity: % (%) - changed recognition_method from regex to genai', -- fcg-rewrite
            entity_record.entity_type, entity_record.entity_type_name; -- fcg-rewrite
    END LOOP; -- fcg-rewrite

    RAISE NOTICE 'Fixed % entities with mismatched recognition_method', fixed_count; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 2: Fix entities that have entity_definition but no pattern -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    fixed_count INTEGER := 0; -- fcg-rewrite
    entity_record RECORD; -- fcg-rewrite
    has_pattern BOOLEAN; -- fcg-rewrite
    has_entity_definition BOOLEAN; -- fcg-rewrite
BEGIN -- fcg-rewrite
    RAISE NOTICE 'Checking entities with entity_definition in recognition_config...'; -- fcg-rewrite

    -- Fix entities where recognition_config has entity_definition but recognition_method is 'regex' -- fcg-rewrite
    FOR entity_record IN -- fcg-rewrite
        SELECT id, entity_type, entity_type_name, recognition_method, recognition_config -- fcg-rewrite
        FROM data_security_entity_types -- fcg-rewrite
        WHERE recognition_method = 'regex' -- fcg-rewrite
          AND recognition_config IS NOT NULL -- fcg-rewrite
    LOOP -- fcg-rewrite
        -- Check if recognition_config has entity_definition -- fcg-rewrite
        has_entity_definition := (entity_record.recognition_config->>'entity_definition') IS NOT NULL -- fcg-rewrite
                                 AND (entity_record.recognition_config->>'entity_definition') != ''; -- fcg-rewrite
        has_pattern := (entity_record.recognition_config->>'pattern') IS NOT NULL -- fcg-rewrite
                       AND (entity_record.recognition_config->>'pattern') != '' -- fcg-rewrite
                       AND (entity_record.recognition_config->>'pattern') != 'null'; -- fcg-rewrite

        -- If has entity_definition but no valid pattern, it should be genai type -- fcg-rewrite
        IF has_entity_definition AND NOT has_pattern THEN -- fcg-rewrite
            UPDATE data_security_entity_types -- fcg-rewrite
            SET recognition_method = 'genai', -- fcg-rewrite
                anonymization_method = 'genai', -- fcg-rewrite
                updated_at = NOW() -- fcg-rewrite
            WHERE id = entity_record.id; -- fcg-rewrite

            fixed_count := fixed_count + 1; -- fcg-rewrite
            RAISE NOTICE 'Fixed entity: % (%) - changed to genai based on entity_definition', -- fcg-rewrite
                entity_record.entity_type, entity_record.entity_type_name; -- fcg-rewrite
        END IF; -- fcg-rewrite
    END LOOP; -- fcg-rewrite

    RAISE NOTICE 'Fixed % additional entities based on recognition_config', fixed_count; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ============================================================================ -- fcg-rewrite
-- STEP 3: Verification -- fcg-rewrite
-- ============================================================================ -- fcg-rewrite

DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    genai_count INTEGER; -- fcg-rewrite
    mismatched_count INTEGER; -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Count genai entities -- fcg-rewrite
    SELECT COUNT(*) INTO genai_count -- fcg-rewrite
    FROM data_security_entity_types -- fcg-rewrite
    WHERE recognition_method = 'genai'; -- fcg-rewrite

    -- Check for any remaining mismatches -- fcg-rewrite
    SELECT COUNT(*) INTO mismatched_count -- fcg-rewrite
    FROM data_security_entity_types -- fcg-rewrite
    WHERE recognition_method = 'regex' AND anonymization_method = 'genai'; -- fcg-rewrite

    RAISE NOTICE '=== Migration 057 Complete ==='; -- fcg-rewrite
    RAISE NOTICE 'Total genai entities: %', genai_count; -- fcg-rewrite
    RAISE NOTICE 'Remaining mismatches: %', mismatched_count; -- fcg-rewrite

    IF mismatched_count > 0 THEN -- fcg-rewrite
        RAISE WARNING 'There are still % entities with mismatched recognition/anonymization methods', mismatched_count; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'All genai entity types are now correctly configured'; -- fcg-rewrite
    END IF; -- fcg-rewrite
    RAISE NOTICE '================================'; -- fcg-rewrite
END $$; -- fcg-rewrite
