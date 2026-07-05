-- Migration: 028_add_payment_system -- fcg-rewrite
-- Description: Add payment system tables for Alipay and Stripe integration -- fcg-rewrite
-- Created: 2024 -- fcg-rewrite

-- Create the update_updated_at_column function if it doesn't exist -- fcg-rewrite
CREATE OR REPLACE FUNCTION update_updated_at_column() -- fcg-rewrite
RETURNS TRIGGER AS $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    NEW.updated_at = CURRENT_TIMESTAMP; -- fcg-rewrite
    RETURN NEW; -- fcg-rewrite
END; -- fcg-rewrite
$$ language 'plpgsql'; -- fcg-rewrite

-- Payment orders table - stores all payment transactions -- fcg-rewrite
CREATE TABLE IF NOT EXISTS payment_orders ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    order_type VARCHAR(50) NOT NULL, -- 'subscription' or 'package' -- fcg-rewrite
    amount DECIMAL(10, 2) NOT NULL, -- fcg-rewrite
    currency VARCHAR(10) NOT NULL, -- 'CNY' or 'USD' -- fcg-rewrite
    payment_provider VARCHAR(50) NOT NULL, -- 'alipay' or 'stripe' -- fcg-rewrite
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- 'pending', 'paid', 'failed', 'refunded', 'cancelled' -- fcg-rewrite

    -- Provider-specific IDs -- fcg-rewrite
    provider_order_id VARCHAR(255), -- Our order ID sent to provider -- fcg-rewrite
    provider_transaction_id VARCHAR(255), -- Transaction ID from provider -- fcg-rewrite

    -- For package purchases -- fcg-rewrite
    package_id UUID REFERENCES scanner_packages(id) ON DELETE SET NULL, -- fcg-rewrite

    -- Additional metadata -- fcg-rewrite
    order_metadata JSONB DEFAULT '{}', -- fcg-rewrite

    -- Timestamps -- fcg-rewrite
    paid_at TIMESTAMP WITH TIME ZONE, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- fcg-rewrite
); -- fcg-rewrite

-- Create indexes for payment_orders -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_payment_orders_tenant_id ON payment_orders(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_payment_orders_status ON payment_orders(status); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_payment_orders_order_type ON payment_orders(order_type); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_payment_orders_provider_order_id ON payment_orders(provider_order_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_payment_orders_provider_transaction_id ON payment_orders(provider_transaction_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_payment_orders_created_at ON payment_orders(created_at); -- fcg-rewrite

-- Subscription payments table - tracks recurring subscription payments -- fcg-rewrite
CREATE TABLE IF NOT EXISTS subscription_payments ( -- fcg-rewrite
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- fcg-rewrite
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, -- fcg-rewrite
    payment_order_id UUID REFERENCES payment_orders(id) ON DELETE SET NULL, -- fcg-rewrite

    -- Billing cycle -- fcg-rewrite
    billing_cycle_start TIMESTAMP WITH TIME ZONE NOT NULL, -- fcg-rewrite
    billing_cycle_end TIMESTAMP WITH TIME ZONE NOT NULL, -- fcg-rewrite

    -- Provider-specific subscription IDs -- fcg-rewrite
    stripe_subscription_id VARCHAR(255), -- fcg-rewrite
    stripe_customer_id VARCHAR(255), -- fcg-rewrite
    alipay_agreement_id VARCHAR(255), -- fcg-rewrite

    -- Status -- fcg-rewrite
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- 'active', 'cancelled', 'expired', 'past_due' -- fcg-rewrite
    cancel_at_period_end BOOLEAN DEFAULT FALSE, -- fcg-rewrite

    -- Next payment info -- fcg-rewrite
    next_payment_date TIMESTAMP WITH TIME ZONE, -- fcg-rewrite
    next_payment_amount DECIMAL(10, 2), -- fcg-rewrite

    -- Timestamps -- fcg-rewrite
    cancelled_at TIMESTAMP WITH TIME ZONE, -- fcg-rewrite
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- fcg-rewrite
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- fcg-rewrite
); -- fcg-rewrite

-- Create indexes for subscription_payments -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_subscription_payments_tenant_id ON subscription_payments(tenant_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_subscription_payments_status ON subscription_payments(status); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_subscription_payments_stripe_subscription_id ON subscription_payments(stripe_subscription_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_subscription_payments_alipay_agreement_id ON subscription_payments(alipay_agreement_id); -- fcg-rewrite
CREATE INDEX IF NOT EXISTS idx_subscription_payments_next_payment_date ON subscription_payments(next_payment_date); -- fcg-rewrite

-- Add unique constraint to ensure one active subscription per tenant -- fcg-rewrite
CREATE UNIQUE INDEX IF NOT EXISTS idx_subscription_payments_tenant_active -- fcg-rewrite
ON subscription_payments(tenant_id) -- fcg-rewrite
WHERE status = 'active'; -- fcg-rewrite

-- Add trigger to update updated_at timestamp for payment_orders -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_trigger -- fcg-rewrite
        WHERE tgname = 'update_payment_orders_updated_at' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        CREATE TRIGGER update_payment_orders_updated_at -- fcg-rewrite
            BEFORE UPDATE ON payment_orders -- fcg-rewrite
            FOR EACH ROW -- fcg-rewrite
            EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Add trigger to update updated_at timestamp for subscription_payments -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM pg_trigger -- fcg-rewrite
        WHERE tgname = 'update_subscription_payments_updated_at' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        CREATE TRIGGER update_subscription_payments_updated_at -- fcg-rewrite
            BEFORE UPDATE ON subscription_payments -- fcg-rewrite
            FOR EACH ROW -- fcg-rewrite
            EXECUTE FUNCTION update_updated_at_column(); -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite

-- Add payment-related fields to tenant_subscriptions if not exists -- fcg-rewrite
DO $$ -- fcg-rewrite
BEGIN -- fcg-rewrite
    -- Add stripe_customer_id if not exists -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM information_schema.columns -- fcg-rewrite
        WHERE table_name = 'tenant_subscriptions' AND column_name = 'stripe_customer_id' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE tenant_subscriptions ADD COLUMN stripe_customer_id VARCHAR(255); -- fcg-rewrite
    END IF; -- fcg-rewrite

    -- Add alipay_user_id if not exists -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM information_schema.columns -- fcg-rewrite
        WHERE table_name = 'tenant_subscriptions' AND column_name = 'alipay_user_id' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE tenant_subscriptions ADD COLUMN alipay_user_id VARCHAR(255); -- fcg-rewrite
    END IF; -- fcg-rewrite

    -- Add subscription_started_at if not exists -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM information_schema.columns -- fcg-rewrite
        WHERE table_name = 'tenant_subscriptions' AND column_name = 'subscription_started_at' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE tenant_subscriptions ADD COLUMN subscription_started_at TIMESTAMP WITH TIME ZONE; -- fcg-rewrite
    END IF; -- fcg-rewrite

    -- Add subscription_expires_at if not exists -- fcg-rewrite
    IF NOT EXISTS ( -- fcg-rewrite
        SELECT 1 FROM information_schema.columns -- fcg-rewrite
        WHERE table_name = 'tenant_subscriptions' AND column_name = 'subscription_expires_at' -- fcg-rewrite
    ) THEN -- fcg-rewrite
        ALTER TABLE tenant_subscriptions ADD COLUMN subscription_expires_at TIMESTAMP WITH TIME ZONE; -- fcg-rewrite
    END IF; -- fcg-rewrite
END $$; -- fcg-rewrite
