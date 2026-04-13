-- Skill Scanner policy table (per-application configuration)
CREATE TABLE IF NOT EXISTS skill_scanner_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,

    enabled BOOLEAN NOT NULL DEFAULT FALSE,

    -- Engine toggles
    enable_static_pattern BOOLEAN NOT NULL DEFAULT TRUE,
    enable_structural_validation BOOLEAN NOT NULL DEFAULT TRUE,
    enable_capability_risk BOOLEAN NOT NULL DEFAULT TRUE,
    enable_llm_semantic BOOLEAN NOT NULL DEFAULT FALSE,
    llm_auto_trigger_on_medium BOOLEAN NOT NULL DEFAULT TRUE,

    -- Policy mode: strict | balanced | permissive
    policy_mode VARCHAR(20) NOT NULL DEFAULT 'balanced',

    -- Per-severity actions: block | warn | log
    critical_action VARCHAR(20) NOT NULL DEFAULT 'block',
    high_action VARCHAR(20) NOT NULL DEFAULT 'warn',
    medium_action VARCHAR(20) NOT NULL DEFAULT 'log',
    low_action VARCHAR(20) NOT NULL DEFAULT 'log',

    -- Custom patterns and keywords (JSON arrays)
    custom_patterns JSON DEFAULT '[]'::json,
    dangerous_capability_keywords JSON DEFAULT '[]'::json,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_skill_scanner_policy_app UNIQUE (application_id)
);

CREATE INDEX IF NOT EXISTS idx_skill_scanner_policies_app
ON skill_scanner_policies(application_id);

CREATE INDEX IF NOT EXISTS idx_skill_scanner_policies_tenant
ON skill_scanner_policies(tenant_id);
