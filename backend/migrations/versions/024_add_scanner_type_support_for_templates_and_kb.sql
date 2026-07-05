-- Migration: Add scanner type support for response templates and knowledge base -- fcg-rewrite
-- Description: Extend response_templates and knowledge_bases tables to support all scanner types -- fcg-rewrite
--              (blacklist, whitelist, official scanners, marketplace scanners, custom scanners) -- fcg-rewrite
-- Date: 2025-11-17 -- fcg-rewrite

-- ========================================== -- fcg-rewrite
-- 1. Add new columns to response_templates -- fcg-rewrite
-- ========================================== -- fcg-rewrite

-- Add scanner_type column (type of scanner: blacklist, whitelist, official_scanner, marketplace_scanner, custom_scanner) -- fcg-rewrite
ALTER TABLE response_templates -- fcg-rewrite
ADD COLUMN IF NOT EXISTS scanner_type VARCHAR(50); -- fcg-rewrite

-- Add scanner_identifier column (blacklist name, whitelist name, or scanner tag like S1, S2, S100, etc.) -- fcg-rewrite
ALTER TABLE response_templates -- fcg-rewrite
ADD COLUMN IF NOT EXISTS scanner_identifier VARCHAR(255); -- fcg-rewrite

-- Make category column nullable (for backward compatibility, keep existing S1-S21 data) -- fcg-rewrite
-- Note: PostgreSQL ALTER COLUMN syntax -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    ALTER TABLE response_templates ALTER COLUMN category DROP NOT NULL; -- fcg-rewrite
EXCEPTION -- fcg-rewrite
    WHEN others THEN -- fcg-rewrite
        -- Column might already be nullable -- fcg-rewrite
        NULL; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Add index on scanner_type for faster queries -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_response_templates_scanner_type -- fcg-rewrite
ON response_templates(scanner_type); -- fcg-rewrite

-- Add composite index on scanner_type + scanner_identifier for faster lookups -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_response_templates_scanner_lookup -- fcg-rewrite
ON response_templates(scanner_type, scanner_identifier) -- fcg-rewrite
WHERE scanner_type IS NOT NULL AND scanner_identifier IS NOT NULL; -- fcg-rewrite

-- ========================================== -- fcg-rewrite
-- 2. Add new columns to knowledge_bases -- fcg-rewrite
-- ========================================== -- fcg-rewrite

-- Add scanner_type column -- fcg-rewrite
ALTER TABLE knowledge_bases -- fcg-rewrite
ADD COLUMN IF NOT EXISTS scanner_type VARCHAR(50); -- fcg-rewrite

-- Add scanner_identifier column -- fcg-rewrite
ALTER TABLE knowledge_bases -- fcg-rewrite
ADD COLUMN IF NOT EXISTS scanner_identifier VARCHAR(255); -- fcg-rewrite

-- Make category column nullable (for backward compatibility) -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    ALTER TABLE knowledge_bases ALTER COLUMN category DROP NOT NULL; -- fcg-rewrite
EXCEPTION -- fcg-rewrite
    WHEN others THEN -- fcg-rewrite
        NULL; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Add index on scanner_type for faster queries -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_scanner_type -- fcg-rewrite
ON knowledge_bases(scanner_type); -- fcg-rewrite

-- Add composite index on scanner_type + scanner_identifier for faster lookups -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_scanner_lookup -- fcg-rewrite
ON knowledge_bases(scanner_type, scanner_identifier) -- fcg-rewrite
WHERE scanner_type IS NOT NULL AND scanner_identifier IS NOT NULL; -- fcg-rewrite

-- ========================================== -- fcg-rewrite
-- 3. Migrate existing data (S1-S21 -> official_scanner) -- fcg-rewrite
-- ========================================== -- fcg-rewrite

-- Migrate existing response_templates with category S1-S21 to official_scanner type -- fcg-rewrite
UPDATE response_templates -- fcg-rewrite
SET -- fcg-rewrite
    scanner_type = 'official_scanner', -- fcg-rewrite
    scanner_identifier = category -- fcg-rewrite
WHERE -- fcg-rewrite
    category IS NOT NULL -- fcg-rewrite
    AND category ~ '^S[0-9]+$'  -- Match S1, S2, ..., S21 -- fcg-rewrite
    AND scanner_type IS NULL;  -- Only migrate if not already set -- fcg-rewrite

-- Migrate existing knowledge_bases with category S1-S21 to official_scanner type -- fcg-rewrite
UPDATE knowledge_bases -- fcg-rewrite
SET -- fcg-rewrite
    scanner_type = 'official_scanner', -- fcg-rewrite
    scanner_identifier = category -- fcg-rewrite
WHERE -- fcg-rewrite
    category IS NOT NULL -- fcg-rewrite
    AND category ~ '^S[0-9]+$'  -- Match S1, S2, ..., S21 -- fcg-rewrite
    AND scanner_type IS NULL;  -- Only migrate if not already set -- fcg-rewrite

-- ========================================== -- fcg-rewrite
-- 4. Add check constraints (optional, for data integrity) -- fcg-rewrite
-- ========================================== -- fcg-rewrite

-- Ensure scanner_type is one of the allowed values -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint -- fcg-rewrite
        WHERE conname = 'response_templates_scanner_type_check' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE response_templates -- fcg-rewrite
        ADD CONSTRAINT response_templates_scanner_type_check -- fcg-rewrite
        CHECK (scanner_type IN ('blacklist', 'whitelist', 'official_scanner', 'marketplace_scanner', 'custom_scanner') OR scanner_type IS NULL); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint -- fcg-rewrite
        WHERE conname = 'knowledge_bases_scanner_type_check' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE knowledge_bases -- fcg-rewrite
        ADD CONSTRAINT knowledge_bases_scanner_type_check -- fcg-rewrite
        CHECK (scanner_type IN ('blacklist', 'whitelist', 'official_scanner', 'marketplace_scanner', 'custom_scanner') OR scanner_type IS NULL); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Ensure either (category) or (scanner_type + scanner_identifier) is set -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint -- fcg-rewrite
        WHERE conname = 'response_templates_scanner_info_check' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE response_templates -- fcg-rewrite
        ADD CONSTRAINT response_templates_scanner_info_check -- fcg-rewrite
        CHECK ( -- fcg-rewrite
            category IS NOT NULL OR -- fcg-rewrite
            (scanner_type IS NOT NULL AND scanner_identifier IS NOT NULL) -- fcg-rewrite
        ); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint -- fcg-rewrite
        WHERE conname = 'knowledge_bases_scanner_info_check' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE knowledge_bases -- fcg-rewrite
        ADD CONSTRAINT knowledge_bases_scanner_info_check -- fcg-rewrite
        CHECK ( -- fcg-rewrite
            category IS NOT NULL OR -- fcg-rewrite
            (scanner_type IS NOT NULL AND scanner_identifier IS NOT NULL) -- fcg-rewrite
        ); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ========================================== -- fcg-rewrite
-- 5. Convert template_content from string to multilingual dictionary format -- fcg-rewrite
-- ========================================== -- fcg-rewrite

-- Convert string template_content to JSON object format {"en": "...", "zh": "..."} -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    template_record RECORD; -- fcg-rewrite
    old_content TEXT; -- fcg-rewrite
    new_content JSONB; -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Loop through all templates that have string content (not JSON object) -- fcg-rewrite
    FOR template_record IN -- fcg-rewrite
        SELECT id, template_content -- fcg-rewrite
        FROM response_templates -- fcg-rewrite
        WHERE jsonb_typeof(template_content::jsonb) = 'string' -- fcg-rewrite
    LOOP -- fcg-rewrite
        -- Extract the string value from the JSON string -- fcg-rewrite
        old_content := template_record.template_content::jsonb#>>'{}'; -- fcg-rewrite

        -- Create new multilingual JSON object with both en and zh using the same content -- fcg-rewrite
        new_content := jsonb_build_object('en', old_content, 'zh', old_content); -- fcg-rewrite

        -- Update the record -- fcg-rewrite
        UPDATE response_templates -- fcg-rewrite
        SET template_content = new_content -- fcg-rewrite
        WHERE id = template_record.id; -- fcg-rewrite

        RAISE NOTICE 'Updated template ID %: % -> %', template_record.id, old_content, new_content; -- fcg-rewrite
    END LOOP; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Add comment to document the expected format -- fcg-rewrite
COMMENT ON COLUMN response_templates.template_content IS 'Multilingual response template content in JSON format: {"en": "English text", "zh": "中文文本", ...}'; -- fcg-rewrite

-- Verify all templates now have object format -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    string_count INTEGER; -- fcg-rewrite
BEGIN -- fcg-rewrite
    SELECT COUNT(*) INTO string_count -- fcg-rewrite
    FROM response_templates -- fcg-rewrite
    WHERE jsonb_typeof(template_content::jsonb) = 'string'; -- fcg-rewrite

    IF string_count > 0 THEN -- fcg-rewrite
        RAISE WARNING 'Still % templates with string format after migration', string_count; -- fcg-rewrite
    ELSE -- fcg-rewrite
        RAISE NOTICE 'All templates successfully migrated to multilingual format'; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ========================================== -- fcg-rewrite
-- Migration complete -- fcg-rewrite
-- ========================================== -- fcg-rewrite
-- Summary: -- fcg-rewrite
-- 1. Added scanner_type and scanner_identifier columns to response_templates and knowledge_bases -- fcg-rewrite
-- 2. Made category column nullable for backward compatibility -- fcg-rewrite
-- 3. Migrated existing S1-S21 data to official_scanner type -- fcg-rewrite
-- 4. Added indexes for better query performance -- fcg-rewrite
-- 5. Added check constraints for data integrity -- fcg-rewrite
-- 6. Converted template_content from string to multilingual dictionary format -- fcg-rewrite
-- -- fcg-rewrite
-- Next steps: -- fcg-rewrite
-- - Update backend models (database/models.py) -- fcg-rewrite
-- - Update enhanced_template_service.py to support all scanner types -- fcg-rewrite
-- - Update detection services to use unified response system -- fcg-rewrite
-- - Update frontend UI to configure templates/KB for all scanner types -- fcg-rewrite
