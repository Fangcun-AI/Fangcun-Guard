-- Migration: Add scanner_name field to response_templates and knowledge_bases -- fcg-rewrite
-- Description: Add scanner_name column to store human-readable scanner names for display -- fcg-rewrite
-- Date: 2025-11-17 -- fcg-rewrite

-- ========================================== -- fcg-rewrite
-- 1. Add scanner_name column to response_templates -- fcg-rewrite
-- ========================================== -- fcg-rewrite

ALTER TABLE response_templates -- fcg-rewrite
ADD COLUMN IF NOT EXISTS scanner_name VARCHAR(255); -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_response_templates_scanner_name -- fcg-rewrite
ON response_templates(scanner_name) -- fcg-rewrite
WHERE scanner_name IS NOT NULL; -- fcg-rewrite

COMMENT ON COLUMN response_templates.scanner_name IS 'Human-readable scanner name for display (e.g., "Bank Fraud", "Travel Discussion")'; -- fcg-rewrite

-- ========================================== -- fcg-rewrite
-- 2. Add scanner_name column to knowledge_bases -- fcg-rewrite
-- ========================================== -- fcg-rewrite

ALTER TABLE knowledge_bases -- fcg-rewrite
ADD COLUMN IF NOT EXISTS scanner_name VARCHAR(255); -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_knowledge_bases_scanner_name -- fcg-rewrite
ON knowledge_bases(scanner_name) -- fcg-rewrite
WHERE scanner_name IS NOT NULL; -- fcg-rewrite

COMMENT ON COLUMN knowledge_bases.scanner_name IS 'Human-readable scanner name for display (e.g., "Bank Fraud", "Travel Discussion")'; -- fcg-rewrite

-- ========================================== -- fcg-rewrite
-- 3. Populate scanner_name from related tables -- fcg-rewrite
-- ========================================== -- fcg-rewrite

-- For blacklist scanner type: get name from blacklist table -- fcg-rewrite
UPDATE response_templates rt -- fcg-rewrite
SET scanner_name = bl.name -- fcg-rewrite
FROM blacklist bl -- fcg-rewrite
WHERE -- fcg-rewrite
    rt.scanner_type = 'blacklist' -- fcg-rewrite
    AND rt.scanner_identifier = bl.name -- fcg-rewrite
    AND rt.scanner_name IS NULL; -- fcg-rewrite

UPDATE knowledge_bases kb -- fcg-rewrite
SET scanner_name = bl.name -- fcg-rewrite
FROM blacklist bl -- fcg-rewrite
WHERE -- fcg-rewrite
    kb.scanner_type = 'blacklist' -- fcg-rewrite
    AND kb.scanner_identifier = bl.name -- fcg-rewrite
    AND kb.scanner_name IS NULL; -- fcg-rewrite

-- For whitelist scanner type: get name from whitelist table -- fcg-rewrite
UPDATE response_templates rt -- fcg-rewrite
SET scanner_name = wl.name -- fcg-rewrite
FROM whitelist wl -- fcg-rewrite
WHERE -- fcg-rewrite
    rt.scanner_type = 'whitelist' -- fcg-rewrite
    AND rt.scanner_identifier = wl.name -- fcg-rewrite
    AND rt.scanner_name IS NULL; -- fcg-rewrite

UPDATE knowledge_bases kb -- fcg-rewrite
SET scanner_name = wl.name -- fcg-rewrite
FROM whitelist wl -- fcg-rewrite
WHERE -- fcg-rewrite
    kb.scanner_type = 'whitelist' -- fcg-rewrite
    AND kb.scanner_identifier = wl.name -- fcg-rewrite
    AND kb.scanner_name IS NULL; -- fcg-rewrite

-- For custom_scanner and marketplace_scanner types: get name from scanners table (via tag) -- fcg-rewrite
UPDATE response_templates rt -- fcg-rewrite
SET scanner_name = s.name -- fcg-rewrite
FROM scanners s -- fcg-rewrite
WHERE -- fcg-rewrite
    rt.scanner_type IN ('custom_scanner', 'marketplace_scanner', 'official_scanner') -- fcg-rewrite
    AND rt.scanner_identifier = s.tag -- fcg-rewrite
    AND rt.scanner_name IS NULL; -- fcg-rewrite

UPDATE knowledge_bases kb -- fcg-rewrite
SET scanner_name = s.name -- fcg-rewrite
FROM scanners s -- fcg-rewrite
WHERE -- fcg-rewrite
    kb.scanner_type IN ('custom_scanner', 'marketplace_scanner', 'official_scanner') -- fcg-rewrite
    AND kb.scanner_identifier = s.tag -- fcg-rewrite
    AND kb.scanner_name IS NULL; -- fcg-rewrite

-- For legacy official_scanner type (S1-S21 not in scanners table): set scanner_name from category mapping -- fcg-rewrite
-- Use a DO block to populate official scanner names -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    category_mapping RECORD; -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Map S1-S21 tags to human-readable names -- fcg-rewrite
    FOR category_mapping IN -- fcg-rewrite
        SELECT unnest(ARRAY['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9', 'S10', -- fcg-rewrite
                            'S11', 'S12', 'S13', 'S14', 'S15', 'S16', 'S17', 'S18', 'S19', 'S20', 'S21']) AS tag, -- fcg-rewrite
               unnest(ARRAY[ -- fcg-rewrite
                   'General Political Topics', -- fcg-rewrite
                   'Sensitive Political Topics', -- fcg-rewrite
                   'Insult to National Symbols or Leaders', -- fcg-rewrite
                   'Harm to Minors', -- fcg-rewrite
                   'Violent Crime', -- fcg-rewrite
                   'Non-Violent Crime', -- fcg-rewrite
                   'Pornography', -- fcg-rewrite
                   'Hate & Discrimination', -- fcg-rewrite
                   'Prompt Attacks', -- fcg-rewrite
                   'Profanity', -- fcg-rewrite
                   'Privacy Invasion', -- fcg-rewrite
                   'Commercial Violations', -- fcg-rewrite
                   'Intellectual Property Infringement', -- fcg-rewrite
                   'Harassment', -- fcg-rewrite
                   'Weapons of Mass Destruction', -- fcg-rewrite
                   'Self-Harm', -- fcg-rewrite
                   'Sexual Crimes', -- fcg-rewrite
                   'Threats', -- fcg-rewrite
                   'Professional Financial Advice', -- fcg-rewrite
                   'Professional Medical Advice', -- fcg-rewrite
                   'Professional Legal Advice' -- fcg-rewrite
               ]) AS name -- fcg-rewrite
    LOOP -- fcg-rewrite
        -- Update response_templates -- fcg-rewrite
        UPDATE response_templates -- fcg-rewrite
        SET scanner_name = category_mapping.name -- fcg-rewrite
        WHERE -- fcg-rewrite
            scanner_type = 'official_scanner' -- fcg-rewrite
            AND scanner_identifier = category_mapping.tag -- fcg-rewrite
            AND scanner_name IS NULL; -- fcg-rewrite

        -- Update knowledge_bases -- fcg-rewrite
        UPDATE knowledge_bases -- fcg-rewrite
        SET scanner_name = category_mapping.name -- fcg-rewrite
        WHERE -- fcg-rewrite
            scanner_type = 'official_scanner' -- fcg-rewrite
            AND scanner_identifier = category_mapping.tag -- fcg-rewrite
            AND scanner_name IS NULL; -- fcg-rewrite
    END LOOP; -- fcg-rewrite

    RAISE NOTICE 'Populated scanner_name for official scanners (S1-S21)'; -- fcg-rewrite
END $$; -- fcg-rewrite

-- ========================================== -- fcg-rewrite
-- Migration complete -- fcg-rewrite
-- ========================================== -- fcg-rewrite
-- Summary: -- fcg-rewrite
-- 1. Added scanner_name column to response_templates and knowledge_bases -- fcg-rewrite
-- 2. Created indexes for better query performance -- fcg-rewrite
-- 3. Populated scanner_name from related tables (blacklist, whitelist, custom_scanners) -- fcg-rewrite
-- 4. Populated scanner_name for official scanners (S1-S21) -- fcg-rewrite
-- -- fcg-rewrite
-- Next steps: -- fcg-rewrite
-- - Update database models to include scanner_name field -- fcg-rewrite
-- - Update config_api.py to return scanner_name in API responses -- fcg-rewrite
-- - Frontend will automatically display scanner_name -- fcg-rewrite
