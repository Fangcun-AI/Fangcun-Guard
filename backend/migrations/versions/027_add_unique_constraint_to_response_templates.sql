-- Add unique constraint to prevent duplicate response templates -- fcg-rewrite
-- This constraint ensures no duplicate templates can be created for the same -- fcg-rewrite
-- combination of tenant, application, and scanner (by identifier or name) -- fcg-rewrite

-- First clean any remaining duplicates that might exist -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    duplicate_count INTEGER; -- fcg-rewrite
    total_cleaned INTEGER := 0; -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Clean duplicates for records with category (legacy format) -- fcg-rewrite
    -- Keep the latest record (highest ID) for each unique combination -- fcg-rewrite
    CREATE TEMPORARY TABLE category_templates_to_keep AS -- fcg-rewrite
    SELECT DISTINCT ON (tenant_id, application_id, category) -- fcg-rewrite
        id -- fcg-rewrite
    FROM response_templates -- fcg-rewrite
    WHERE category IS NOT NULL -- fcg-rewrite
    ORDER BY tenant_id, application_id, category, id DESC; -- fcg-rewrite

    -- Delete category duplicates -- fcg-rewrite
    DELETE FROM response_templates -- fcg-rewrite
    WHERE category IS NOT NULL -- fcg-rewrite
      AND id NOT IN (SELECT id FROM category_templates_to_keep); -- fcg-rewrite

    GET DIAGNOSTICS duplicate_count = ROW_COUNT; -- fcg-rewrite
    total_cleaned := total_cleaned + duplicate_count; -- fcg-rewrite
    RAISE NOTICE 'Cleaned % duplicate response templates (category-based)', duplicate_count; -- fcg-rewrite

    DROP TABLE category_templates_to_keep; -- fcg-rewrite

    -- Clean duplicates for records with scanner_identifier (new format) -- fcg-rewrite
    CREATE TEMPORARY TABLE scanner_templates_to_keep AS -- fcg-rewrite
    SELECT DISTINCT ON (tenant_id, application_id, scanner_identifier) -- fcg-rewrite
        id -- fcg-rewrite
    FROM response_templates -- fcg-rewrite
    WHERE scanner_identifier IS NOT NULL -- fcg-rewrite
    ORDER BY tenant_id, application_id, scanner_identifier, id DESC; -- fcg-rewrite

    -- Delete scanner_identifier duplicates -- fcg-rewrite
    DELETE FROM response_templates -- fcg-rewrite
    WHERE scanner_identifier IS NOT NULL -- fcg-rewrite
      AND id NOT IN (SELECT id FROM scanner_templates_to_keep); -- fcg-rewrite

    GET DIAGNOSTICS duplicate_count = ROW_COUNT; -- fcg-rewrite
    total_cleaned := total_cleaned + duplicate_count; -- fcg-rewrite
    RAISE NOTICE 'Cleaned % duplicate response templates (scanner_identifier-based)', duplicate_count; -- fcg-rewrite

    DROP TABLE scanner_templates_to_keep; -- fcg-rewrite

    -- Clean duplicates for records with scanner_name -- fcg-rewrite
    CREATE TEMPORARY TABLE scanner_name_templates_to_keep AS -- fcg-rewrite
    SELECT DISTINCT ON (tenant_id, application_id, scanner_name) -- fcg-rewrite
        id -- fcg-rewrite
    FROM response_templates -- fcg-rewrite
    WHERE scanner_name IS NOT NULL -- fcg-rewrite
    ORDER BY tenant_id, application_id, scanner_name, id DESC; -- fcg-rewrite

    -- Delete scanner_name duplicates -- fcg-rewrite
    DELETE FROM response_templates -- fcg-rewrite
    WHERE scanner_name IS NOT NULL -- fcg-rewrite
      AND id NOT IN (SELECT id FROM scanner_name_templates_to_keep); -- fcg-rewrite

    GET DIAGNOSTICS duplicate_count = ROW_COUNT; -- fcg-rewrite
    total_cleaned := total_cleaned + duplicate_count; -- fcg-rewrite
    RAISE NOTICE 'Cleaned % duplicate response templates (scanner_name-based)', duplicate_count; -- fcg-rewrite

    DROP TABLE scanner_name_templates_to_keep; -- fcg-rewrite

    RAISE NOTICE 'Total cleaned: % duplicate response templates', total_cleaned; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Add unique constraint to prevent future duplicates -- fcg-rewrite
-- PostgreSQL doesn't support COALESCE in UNIQUE constraints, so we'll use a functional index -- fcg-rewrite
CREATE UNIQUE INDEX IF NOT EXISTS idx_response_templates_unique_tenant_app_scanner -- fcg-rewrite
ON response_templates (tenant_id, application_id, COALESCE(scanner_identifier, category)) -- fcg-rewrite
WHERE scanner_name IS NOT NULL; -- fcg-rewrite

-- Add additional partial unique indexes for different field combinations -- fcg-rewrite
CREATE UNIQUE INDEX IF NOT EXISTS idx_response_templates_unique_scanner_identifier -- fcg-rewrite
ON response_templates (tenant_id, application_id, scanner_identifier) -- fcg-rewrite
WHERE scanner_identifier IS NOT NULL; -- fcg-rewrite

CREATE UNIQUE INDEX IF NOT EXISTS idx_response_templates_unique_category -- fcg-rewrite
ON response_templates (tenant_id, application_id, category) -- fcg-rewrite
WHERE category IS NOT NULL; -- fcg-rewrite

CREATE UNIQUE INDEX IF NOT EXISTS idx_response_templates_unique_scanner_name -- fcg-rewrite
ON response_templates (tenant_id, application_id, scanner_name) -- fcg-rewrite
WHERE scanner_name IS NOT NULL; -- fcg-rewrite

COMMENT ON INDEX idx_response_templates_unique_tenant_app_scanner IS -- fcg-rewrite
'Unique functional index that prevents duplicate response templates for the same tenant, application, and scanner combination. Uses COALESCE to handle both new format (scanner_identifier) and legacy format (category).'; -- fcg-rewrite

COMMENT ON INDEX idx_response_templates_unique_scanner_identifier IS -- fcg-rewrite
'Unique index for scanner_identifier field to prevent duplicates in new format.'; -- fcg-rewrite

COMMENT ON INDEX idx_response_templates_unique_category IS -- fcg-rewrite
'Unique index for category field to prevent duplicates in legacy format.'; -- fcg-rewrite

COMMENT ON INDEX idx_response_templates_unique_scanner_name IS -- fcg-rewrite
'Additional unique index for scanner_name to prevent duplicates based on display name.'; -- fcg-rewrite