-- Add tool definition scanning fields to agent_safety_policies
-- This enables JSON tool definition security scanning (moved from skill_scanner)

ALTER TABLE agent_safety_policies
    ADD COLUMN IF NOT EXISTS enable_tool_definition_scan BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE agent_safety_policies
    ADD COLUMN IF NOT EXISTS tool_definition_scan_action VARCHAR(20) NOT NULL DEFAULT 'warn';
