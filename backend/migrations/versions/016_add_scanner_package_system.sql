-- Migration: Add Scanner Package System -- fcg-rewrite
-- Description: Replace hardcoded risk types with flexible scanner package system -- fcg-rewrite
-- Version: 016 -- fcg-rewrite
-- Date: 2025-11-05 -- fcg-rewrite

-- ===================================================== -- fcg-rewrite
-- Step 1: Create scanner_packages table -- fcg-rewrite
-- ===================================================== -- fcg-rewrite

CREATE TABLE IF NOT EXISTS scanner_packages ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    package_code VARCHAR(100) UNIQUE NOT NULL, -- fcg-rewrite
    package_name VARCHAR(200) NOT NULL, -- fcg-rewrite
    author VARCHAR(200) NOT NULL DEFAULT 'FangcunGuard', -- fcg-rewrite
    description TEXT, -- fcg-rewrite
    version VARCHAR(50) NOT NULL DEFAULT '1.0.0', -- fcg-rewrite
    license VARCHAR(100) DEFAULT 'proprietary', -- fcg-rewrite

    -- Package type -- fcg-rewrite
    package_type VARCHAR(50) NOT NULL, -- fcg-rewrite
    is_official BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite
    requires_purchase BOOLEAN NOT NULL DEFAULT FALSE, -- fcg-rewrite

    -- Purchase settings (for premium packages) -- fcg-rewrite
    price_display VARCHAR(100), -- fcg-rewrite
    file_path VARCHAR(512), -- fcg-rewrite

    -- Metadata -- fcg-rewrite
    is_active BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite
    display_order INTEGER DEFAULT 0, -- fcg-rewrite
    scanner_count INTEGER DEFAULT 0, -- fcg-rewrite

    -- Timestamps -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite

    -- Constraints -- fcg-rewrite
    CONSTRAINT chk_package_type CHECK (package_type IN ('builtin', 'purchasable'))  -- 'builtin' = basic, 'purchasable' = premium -- fcg-rewrite
); -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_scanner_packages_type ON scanner_packages(package_type); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_scanner_packages_active ON scanner_packages(is_active); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_scanner_packages_code ON scanner_packages(package_code); -- fcg-rewrite

-- ===================================================== -- fcg-rewrite
-- Step 2: Create scanners table -- fcg-rewrite
-- ===================================================== -- fcg-rewrite

CREATE TABLE IF NOT EXISTS scanners ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    package_id UUID REFERENCES scanner_packages(id) ON DELETE CASCADE, -- fcg-rewrite

    -- Scanner identification -- fcg-rewrite
    tag VARCHAR(50) UNIQUE NOT NULL, -- fcg-rewrite
    name VARCHAR(200) NOT NULL, -- fcg-rewrite
    description TEXT, -- fcg-rewrite

    -- Scanner configuration -- fcg-rewrite
    scanner_type VARCHAR(50) NOT NULL, -- fcg-rewrite
    definition TEXT NOT NULL, -- fcg-rewrite

    -- Default behavior (package defaults) -- fcg-rewrite
    default_risk_level VARCHAR(20) NOT NULL, -- fcg-rewrite
    default_scan_prompt BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite
    default_scan_response BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite

    -- Metadata -- fcg-rewrite
    is_active BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite
    display_order INTEGER DEFAULT 0, -- fcg-rewrite

    -- Timestamps -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite

    -- Constraints -- fcg-rewrite
    CONSTRAINT chk_scanner_type CHECK (scanner_type IN ('genai', 'regex', 'keyword')), -- fcg-rewrite
    CONSTRAINT chk_default_risk_level CHECK (default_risk_level IN ('high_risk', 'medium_risk', 'low_risk')) -- fcg-rewrite
); -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_scanners_package ON scanners(package_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_scanners_tag ON scanners(tag); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_scanners_type ON scanners(scanner_type); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_scanners_active ON scanners(is_active); -- fcg-rewrite

-- ===================================================== -- fcg-rewrite
-- Step 3: Create application_scanner_configs table -- fcg-rewrite
-- ===================================================== -- fcg-rewrite

CREATE TABLE IF NOT EXISTS application_scanner_configs ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE, -- fcg-rewrite
    scanner_id UUID NOT NULL REFERENCES scanners(id) ON DELETE CASCADE, -- fcg-rewrite

    -- Override settings (NULL = use package defaults) -- fcg-rewrite
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE, -- fcg-rewrite
    risk_level_override VARCHAR(20), -- fcg-rewrite
    scan_prompt_override BOOLEAN, -- fcg-rewrite
    scan_response_override BOOLEAN, -- fcg-rewrite

    -- Timestamps -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite

    -- Constraints -- fcg-rewrite
    CONSTRAINT chk_risk_level_override CHECK ( -- fcg-rewrite
        risk_level_override IS NULL OR -- fcg-rewrite
        risk_level_override IN ('high_risk', 'medium_risk', 'low_risk') -- fcg-rewrite
    ) -- fcg-rewrite
); -- fcg-rewrite

-- Create unique constraint with proper name -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_app_scanner_config' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE application_scanner_configs -- fcg-rewrite
        ADD CONSTRAINT uq_app_scanner_config UNIQUE(application_id, scanner_id); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_app_scanner_configs_app ON application_scanner_configs(application_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_app_scanner_configs_scanner ON application_scanner_configs(scanner_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_app_scanner_configs_enabled ON application_scanner_configs(application_id, is_enabled); -- fcg-rewrite

-- ===================================================== -- fcg-rewrite
-- Step 4: Create package_purchases table -- fcg-rewrite
-- ===================================================== -- fcg-rewrite

CREATE TABLE IF NOT EXISTS package_purchases ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    package_id UUID NOT NULL REFERENCES scanner_packages(id) ON DELETE CASCADE, -- fcg-rewrite

    -- Purchase lifecycle -- fcg-rewrite
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- fcg-rewrite
    request_email VARCHAR(255), -- fcg-rewrite
    request_message TEXT, -- fcg-rewrite

    -- Admin actions -- fcg-rewrite
    approved_by UUID REFERENCES tenants(id), -- fcg-rewrite
    approved_at TIMESTAMP WITH TIME ZONE, -- fcg-rewrite
    rejection_reason TEXT, -- fcg-rewrite

    -- Timestamps -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite

    -- Constraints -- fcg-rewrite
    CONSTRAINT chk_purchase_status CHECK (status IN ('pending', 'approved', 'rejected')) -- fcg-rewrite
); -- fcg-rewrite

-- Create unique constraint with proper name -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_tenant_package_purchase' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE package_purchases -- fcg-rewrite
        ADD CONSTRAINT uq_tenant_package_purchase UNIQUE(tenant_id, package_id); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_package_purchases_tenant ON package_purchases(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_package_purchases_package ON package_purchases(package_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_package_purchases_status ON package_purchases(status); -- fcg-rewrite

-- ===================================================== -- fcg-rewrite
-- Step 5: Create custom_scanners table -- fcg-rewrite
-- ===================================================== -- fcg-rewrite

CREATE TABLE IF NOT EXISTS custom_scanners ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE, -- fcg-rewrite
    scanner_id UUID NOT NULL REFERENCES scanners(id) ON DELETE CASCADE, -- fcg-rewrite
    created_by UUID NOT NULL REFERENCES tenants(id), -- fcg-rewrite

    -- Custom scanner metadata -- fcg-rewrite
    notes TEXT, -- fcg-rewrite

    -- Timestamps -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- fcg-rewrite
); -- fcg-rewrite

-- Create unique constraint with proper name -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_app_custom_scanner' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE custom_scanners -- fcg-rewrite
        ADD CONSTRAINT uq_app_custom_scanner UNIQUE(application_id, scanner_id); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

CREATE INDEX IF NOT EXISTS idx_custom_scanners_app ON custom_scanners(application_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_custom_scanners_scanner ON custom_scanners(scanner_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_custom_scanners_created_by ON custom_scanners(created_by); -- fcg-rewrite

-- ===================================================== -- fcg-rewrite
-- Step 6: Update detection_results table -- fcg-rewrite
-- ===================================================== -- fcg-rewrite

ALTER TABLE detection_results -- fcg-rewrite
ADD COLUMN IF NOT EXISTS matched_scanner_tags TEXT; -- fcg-rewrite

COMMENT ON COLUMN detection_results.matched_scanner_tags IS 'Comma-separated list of matched scanner tags (e.g., "S2,S5,S100")'; -- fcg-rewrite

-- ===================================================== -- fcg-rewrite
-- Step 7: Mark old tables as deprecated -- fcg-rewrite
-- ===================================================== -- fcg-rewrite

COMMENT ON TABLE risk_type_config IS 'DEPRECATED: Use scanner package system instead. Kept for backward compatibility and rollback. Will be removed in future version.'; -- fcg-rewrite

-- ===================================================== -- fcg-rewrite
-- Migration Complete -- fcg-rewrite
-- ===================================================== -- fcg-rewrite

-- Note: Built-in packages and data migration will be handled by Python script (017_migrate_to_scanner_system.py) -- fcg-rewrite
