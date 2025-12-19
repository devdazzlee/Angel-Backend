-- =============================================
-- STRIPE SUBSCRIPTION TABLE FOR ANGEL AI
-- Run this in your Supabase SQL Editor
-- =============================================

CREATE TABLE IF NOT EXISTS user_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    stripe_subscription_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255),
    subscription_status VARCHAR(50) DEFAULT 'incomplete' CHECK (subscription_status IN ('incomplete', 'incomplete_expired', 'trialing', 'active', 'past_due', 'canceled', 'unpaid')),
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN DEFAULT false,
    amount DECIMAL(10, 2),
    currency VARCHAR(10) DEFAULT 'usd',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX idx_user_subscriptions_status ON user_subscriptions(subscription_status);
CREATE INDEX idx_user_subscriptions_stripe_id ON user_subscriptions(stripe_subscription_id);
CREATE INDEX idx_user_subscriptions_period_end ON user_subscriptions(current_period_end);

ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own subscriptions" 
    ON user_subscriptions FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Service can insert subscriptions" 
    ON user_subscriptions FOR INSERT 
    WITH CHECK (true);

CREATE POLICY "Service can update subscriptions" 
    ON user_subscriptions FOR UPDATE 
    USING (true);

CREATE TRIGGER update_user_subscriptions_updated_at 
    BEFORE UPDATE ON user_subscriptions 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- HELPER FUNCTION: Check if user has active subscription
-- =============================================

CREATE OR REPLACE FUNCTION check_active_subscription(check_user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 
        FROM user_subscriptions 
        WHERE user_id = check_user_id 
        AND subscription_status = 'active'
        AND (current_period_end IS NULL OR current_period_end > NOW())
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION check_active_subscription(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION check_active_subscription(UUID) TO service_role;

