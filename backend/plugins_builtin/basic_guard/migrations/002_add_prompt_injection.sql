-- Add prompt injection detection columns to basic_guard_policies
-- Idempotent: safe to run multiple times

ALTER TABLE basic_guard_policies
    ADD COLUMN IF NOT EXISTS enable_prompt_injection_check BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE basic_guard_policies
    ADD COLUMN IF NOT EXISTS prompt_injection_threshold FLOAT NOT NULL DEFAULT 0.5;

ALTER TABLE basic_guard_policies
    ADD COLUMN IF NOT EXISTS prompt_injection_action VARCHAR(20) NOT NULL DEFAULT 'block';

ALTER TABLE basic_guard_policies
    ADD COLUMN IF NOT EXISTS scan_user_messages BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE basic_guard_policies
    ADD COLUMN IF NOT EXISTS scan_system_messages BOOLEAN NOT NULL DEFAULT TRUE;
