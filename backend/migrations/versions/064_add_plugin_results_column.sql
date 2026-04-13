-- Add generic plugin_results JSON column to detection_results table
-- This allows any plugin to store its detection data without requiring schema changes.
-- Existing P0 columns (agent_safety_*, hallucination_*) are kept for backward compatibility.

ALTER TABLE detection_results ADD COLUMN IF NOT EXISTS plugin_results JSON DEFAULT NULL;

-- Ensure column is JSONB (SQLAlchemy may create it as JSON; GIN index requires JSONB)
ALTER TABLE detection_results ALTER COLUMN plugin_results TYPE JSONB USING plugin_results::jsonb;

-- Add index for querying plugin results (GIN index for JSONB containment queries)
CREATE INDEX IF NOT EXISTS idx_detection_results_plugin_results
ON detection_results USING gin (plugin_results jsonb_ops) WHERE plugin_results IS NOT NULL;

-- Add plugin_migrations tracking table (used by plugin migration runner)
CREATE TABLE IF NOT EXISTS plugin_migrations (
    plugin_name VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL,
    description VARCHAR(255) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    PRIMARY KEY (plugin_name, version)
);
