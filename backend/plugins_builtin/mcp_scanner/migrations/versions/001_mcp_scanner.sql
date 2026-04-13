-- MCP Scanner policy table (per-application configuration)
CREATE TABLE IF NOT EXISTS mcp_scanner_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,

    enabled BOOLEAN NOT NULL DEFAULT FALSE,

    -- Engine toggles
    enable_yara_rules BOOLEAN NOT NULL DEFAULT TRUE,
    enable_llm_semantic BOOLEAN NOT NULL DEFAULT FALSE,
    enable_behavior_analysis BOOLEAN NOT NULL DEFAULT TRUE,
    llm_auto_trigger_on_medium BOOLEAN NOT NULL DEFAULT TRUE,

    -- Scan scope toggles
    enable_tool_scan BOOLEAN NOT NULL DEFAULT TRUE,
    enable_prompt_scan BOOLEAN NOT NULL DEFAULT TRUE,
    enable_resource_scan BOOLEAN NOT NULL DEFAULT TRUE,
    enable_instruction_scan BOOLEAN NOT NULL DEFAULT TRUE,
    enable_supply_chain BOOLEAN NOT NULL DEFAULT FALSE,

    -- Policy mode: strict | balanced | permissive
    policy_mode VARCHAR(20) NOT NULL DEFAULT 'balanced',

    -- Per-severity actions: block | warn | log
    critical_action VARCHAR(20) NOT NULL DEFAULT 'block',
    high_action VARCHAR(20) NOT NULL DEFAULT 'warn',
    medium_action VARCHAR(20) NOT NULL DEFAULT 'log',
    low_action VARCHAR(20) NOT NULL DEFAULT 'log',

    -- Custom YARA rules and trusted servers (JSON arrays)
    custom_yara_rules JSON DEFAULT '[]'::json,
    trusted_servers JSON DEFAULT '[]'::json,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_mcp_scanner_policy_app UNIQUE (application_id)
);

CREATE INDEX IF NOT EXISTS idx_mcp_scanner_policies_app
ON mcp_scanner_policies(application_id);

CREATE INDEX IF NOT EXISTS idx_mcp_scanner_policies_tenant
ON mcp_scanner_policies(tenant_id);
