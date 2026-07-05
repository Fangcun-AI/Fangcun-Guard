-- Migration: add_english_content_to_response_templates -- fcg-rewrite
-- Version: 015 -- fcg-rewrite
-- Date: 2025-11-04 -- fcg-rewrite
-- Author: Claude Code Assistant -- fcg-rewrite

-- Description: -- fcg-rewrite
-- Add English content to existing response templates that only have Chinese content. -- fcg-rewrite
-- This migration adds default English translations for all risk categories. -- fcg-rewrite

-- Default English content for each category -- fcg-rewrite
DO $$ -- fcg-rewrite
DECLARE -- fcg-rewrite
    template_record RECORD; -- fcg-rewrite
    new_content JSONB; -- fcg-rewrite
    english_text TEXT; -- fcg-rewrite
    template_count INTEGER; -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Check if response_templates table has any data -- fcg-rewrite
    SELECT COUNT(*) INTO template_count FROM response_templates; -- fcg-rewrite

    IF template_count = 0 THEN -- fcg-rewrite
        RAISE NOTICE 'No response templates found, skipping migration 015'; -- fcg-rewrite
        RETURN; -- fcg-rewrite
    END IF; -- fcg-rewrite

    -- Loop through all response templates -- fcg-rewrite
    FOR template_record IN -- fcg-rewrite
        SELECT id, category, template_content::jsonb as template_content -- fcg-rewrite
        FROM response_templates -- fcg-rewrite
        WHERE (template_content::jsonb) ? 'zh' AND NOT ((template_content::jsonb) ? 'en') -- fcg-rewrite
    LOOP -- fcg-rewrite
        -- Determine English content based on category -- fcg-rewrite
        -- Format: "Request blocked by FangcunGuard due to content potentially involving [topic]." -- fcg-rewrite
        CASE template_record.category -- fcg-rewrite
            WHEN 'S1' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving general political topics.'; -- fcg-rewrite
            WHEN 'S2' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving sensitive political topics.'; -- fcg-rewrite
            WHEN 'S3' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving insult to national symbols or leaders.'; -- fcg-rewrite
            WHEN 'S4' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving harm to minors.'; -- fcg-rewrite
            WHEN 'S5' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving violent crime.'; -- fcg-rewrite
            WHEN 'S6' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving non-violent crime.'; -- fcg-rewrite
            WHEN 'S7' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving pornography.'; -- fcg-rewrite
            WHEN 'S8' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving hate and discrimination.'; -- fcg-rewrite
            WHEN 'S9' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving prompt injection attacks.'; -- fcg-rewrite
            WHEN 'S10' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving profanity.'; -- fcg-rewrite
            WHEN 'S11' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving privacy invasion.'; -- fcg-rewrite
            WHEN 'S12' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving commercial violations.'; -- fcg-rewrite
            WHEN 'S13' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving intellectual property infringement.'; -- fcg-rewrite
            WHEN 'S14' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving harassment.'; -- fcg-rewrite
            WHEN 'S15' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving weapons of mass destruction.'; -- fcg-rewrite
            WHEN 'S16' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving self-harm.'; -- fcg-rewrite
            WHEN 'S17' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving sexual crimes.'; -- fcg-rewrite
            WHEN 'S18' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving threats.'; -- fcg-rewrite
            WHEN 'S19' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving professional financial advice.'; -- fcg-rewrite
            WHEN 'S20' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving professional medical advice.'; -- fcg-rewrite
            WHEN 'S21' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content potentially involving professional legal advice.'; -- fcg-rewrite
            WHEN 'default' THEN -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content policy violation.'; -- fcg-rewrite
            ELSE -- fcg-rewrite
                english_text := 'Request blocked by FangcunGuard due to content policy violation.'; -- fcg-rewrite
        END CASE; -- fcg-rewrite

        -- Add English content to existing JSONB -- fcg-rewrite
        new_content := jsonb_set( -- fcg-rewrite
            template_record.template_content, -- fcg-rewrite
            '{en}', -- fcg-rewrite
            to_jsonb(english_text) -- fcg-rewrite
        ); -- fcg-rewrite

        -- Update the record -- fcg-rewrite
        UPDATE response_templates -- fcg-rewrite
        SET template_content = new_content, -- fcg-rewrite
            updated_at = CURRENT_TIMESTAMP -- fcg-rewrite
        WHERE id = template_record.id; -- fcg-rewrite

        RAISE NOTICE 'Added English content to template ID % (category: %)', template_record.id, template_record.category; -- fcg-rewrite
    END LOOP; -- fcg-rewrite

    RAISE NOTICE 'Migration completed: Added English content to response templates'; -- fcg-rewrite
END $$; -- fcg-rewrite
