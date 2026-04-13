-- Migration 063: Add Agent Safety and Hallucination Detection
-- Description: Creates agent_safety_policies and hallucination_policies tables,
--              extends detection_results with new detection dimensions.

-- ============================================================
-- 1. Agent Safety Policies (per-application configuration)
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_safety_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,

    -- Feature toggle
    enabled BOOLEAN NOT NULL DEFAULT false,

    -- Tool whitelist: NULL = allow all tools; ["func1", "func2"] = only allow listed
    tool_whitelist JSON DEFAULT NULL,
    -- Tool blacklist: [] = block none; ["func1"] = block listed tools
    tool_blacklist JSON DEFAULT '[]'::json,

    -- Limits
    max_tool_calls_per_request INTEGER NOT NULL DEFAULT 20,

    -- Suspicious argument detection
    enable_argument_inspection BOOLEAN NOT NULL DEFAULT true,
    -- Custom suspicious patterns (regex strings), in addition to built-in patterns
    argument_patterns JSON DEFAULT '[]'::json,

    -- Reasoning / Chain-of-Thought safety
    enable_reasoning_safety BOOLEAN NOT NULL DEFAULT false,

    -- Violation actions
    tool_violation_action VARCHAR(20) NOT NULL DEFAULT 'block',
    reasoning_violation_action VARCHAR(20) NOT NULL DEFAULT 'warn',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_agent_safety_policy_app UNIQUE(application_id),
    CONSTRAINT chk_tool_violation_action CHECK (tool_violation_action IN ('block', 'warn', 'log')),
    CONSTRAINT chk_reasoning_violation_action CHECK (reasoning_violation_action IN ('block', 'warn', 'log'))
);

CREATE INDEX IF NOT EXISTS idx_agent_safety_policies_tenant ON agent_safety_policies(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_safety_policies_app ON agent_safety_policies(application_id);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_agent_safety_policies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agent_safety_policies_updated_at ON agent_safety_policies;
CREATE TRIGGER trg_agent_safety_policies_updated_at
    BEFORE UPDATE ON agent_safety_policies
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_safety_policies_updated_at();


-- ============================================================
-- 2. Hallucination Policies (per-application configuration)
-- ============================================================
CREATE TABLE IF NOT EXISTS hallucination_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,

    -- Feature toggles
    enabled BOOLEAN NOT NULL DEFAULT false,
    enable_groundedness BOOLEAN NOT NULL DEFAULT true,
    enable_consistency BOOLEAN NOT NULL DEFAULT true,

    -- Thresholds (0.0 to 1.0, higher = stricter)
    groundedness_threshold FLOAT NOT NULL DEFAULT 0.7,
    consistency_threshold FLOAT NOT NULL DEFAULT 0.7,

    -- Where to find reference context in the request
    -- 'system_message' | 'extra_body.context' | 'extra_body.documents'
    source_context_field VARCHAR(100) NOT NULL DEFAULT 'system_message',

    -- Violation action: 'block' | 'flag' | 'warn' | 'log'
    violation_action VARCHAR(20) NOT NULL DEFAULT 'flag',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_hallucination_policy_app UNIQUE(application_id),
    CONSTRAINT chk_hallucination_action CHECK (violation_action IN ('block', 'flag', 'warn', 'log'))
);

CREATE INDEX IF NOT EXISTS idx_hallucination_policies_tenant ON hallucination_policies(tenant_id);
CREATE INDEX IF NOT EXISTS idx_hallucination_policies_app ON hallucination_policies(application_id);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_hallucination_policies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_hallucination_policies_updated_at ON hallucination_policies;
CREATE TRIGGER trg_hallucination_policies_updated_at
    BEFORE UPDATE ON hallucination_policies
    FOR EACH ROW
    EXECUTE FUNCTION update_hallucination_policies_updated_at();


-- ============================================================
-- 3. Extend detection_results with new detection dimensions
-- ============================================================

-- Agent safety detection results
ALTER TABLE detection_results ADD COLUMN IF NOT EXISTS agent_safety_risk_level VARCHAR(20) DEFAULT 'no_risk';
ALTER TABLE detection_results ADD COLUMN IF NOT EXISTS agent_safety_categories JSON DEFAULT '[]'::json;

-- Hallucination detection results
ALTER TABLE detection_results ADD COLUMN IF NOT EXISTS hallucination_risk_level VARCHAR(20) DEFAULT 'no_risk';
ALTER TABLE detection_results ADD COLUMN IF NOT EXISTS hallucination_categories JSON DEFAULT '[]'::json;
ALTER TABLE detection_results ADD COLUMN IF NOT EXISTS groundedness_score FLOAT DEFAULT NULL;
ALTER TABLE detection_results ADD COLUMN IF NOT EXISTS consistency_score FLOAT DEFAULT NULL;
