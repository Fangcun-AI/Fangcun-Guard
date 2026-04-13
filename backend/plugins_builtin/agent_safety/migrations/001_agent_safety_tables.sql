-- Agent Safety Plugin: tables created by main migration 063
-- This file is a no-op placeholder since the tables already exist.
-- Future agent_safety-specific schema changes go here.

-- Tables: agent_safety_policies (created in migration 063)
-- No action needed if tables already exist.
DO $$ BEGIN
    RAISE NOTICE 'Agent safety plugin migration 001: tables already managed by main migrations';
END $$;
