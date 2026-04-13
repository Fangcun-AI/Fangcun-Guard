-- Basic guard policy table (per-application configuration)
-- Replaces streaming_safety_policies with broader scope
CREATE TABLE IF NOT EXISTS basic_guard_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- Streaming output safety engine toggles
    enable_content_pattern_check BOOLEAN NOT NULL DEFAULT TRUE,
    enable_reasoning_divergence_check BOOLEAN NOT NULL DEFAULT TRUE,
    enable_output_anomaly_check BOOLEAN NOT NULL DEFAULT TRUE,
    max_repetition_ratio FLOAT NOT NULL DEFAULT 0.4,
    min_content_length INTEGER NOT NULL DEFAULT 10,

    -- Violation action: block | warn | log
    violation_action VARCHAR(20) NOT NULL DEFAULT 'warn',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_basic_guard_policy_app UNIQUE (application_id)
);

CREATE INDEX IF NOT EXISTS idx_basic_guard_policies_app
ON basic_guard_policies(application_id);

CREATE INDEX IF NOT EXISTS idx_basic_guard_policies_tenant
ON basic_guard_policies(tenant_id);

-- Migrate existing streaming_safety_policies data if table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'streaming_safety_policies') THEN
        INSERT INTO basic_guard_policies (
            id, tenant_id, application_id,
            enabled, enable_content_pattern_check, enable_reasoning_divergence_check,
            enable_output_anomaly_check, max_repetition_ratio, min_content_length,
            violation_action, created_at, updated_at
        )
        SELECT
            id, tenant_id, application_id,
            enabled, enable_content_pattern_check, enable_reasoning_divergence_check,
            enable_output_anomaly_check, max_repetition_ratio, min_content_length,
            violation_action, created_at, updated_at
        FROM streaming_safety_policies
        ON CONFLICT (application_id) DO NOTHING;

        RAISE NOTICE 'Migrated streaming_safety_policies data to basic_guard_policies';
    END IF;
END $$;
