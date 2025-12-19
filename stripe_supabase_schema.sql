-- =============================================
-- STRIPE PAYMENT TABLES FOR ANGEL AI
-- Run this in your Supabase SQL Editor
-- =============================================

-- User Payments Table (tracks one-time payments and premium access)
CREATE TABLE IF NOT EXISTS user_payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    stripe_session_id VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    stripe_payment_intent_id VARCHAR(255),
    customer_email VARCHAR(255),
    amount DECIMAL(10, 2),
    currency VARCHAR(10) DEFAULT 'usd',
    payment_status VARCHAR(50) DEFAULT 'pending' CHECK (payment_status IN ('pending', 'paid', 'failed', 'refunded')),
    product_name VARCHAR(255) DEFAULT 'Angel AI Premium',
    has_premium_access BOOLEAN DEFAULT false,
    paid_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_payments_user_id ON user_payments(user_id);
CREATE INDEX IF NOT EXISTS idx_user_payments_status ON user_payments(payment_status);
CREATE INDEX IF NOT EXISTS idx_user_payments_stripe_session ON user_payments(stripe_session_id);
CREATE INDEX IF NOT EXISTS idx_user_payments_premium_access ON user_payments(has_premium_access);

-- Enable RLS
ALTER TABLE user_payments ENABLE ROW LEVEL SECURITY;

-- RLS Policies for user_payments
CREATE POLICY "Users can view their own payments" 
    ON user_payments FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert payments" 
    ON user_payments FOR INSERT 
    WITH CHECK (true);

CREATE POLICY "Service role can update payments" 
    ON user_payments FOR UPDATE 
    USING (true);

-- Trigger for updated_at
CREATE TRIGGER update_user_payments_updated_at 
    BEFORE UPDATE ON user_payments 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- HELPER FUNCTION: Check if user has premium access
-- =============================================

CREATE OR REPLACE FUNCTION check_premium_access(check_user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 
        FROM user_payments 
        WHERE user_id = check_user_id 
        AND payment_status = 'paid'
        AND has_premium_access = true
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION check_premium_access(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION check_premium_access(UUID) TO service_role;

-- =============================================
-- VERIFICATION: Check table was created
-- =============================================

SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_payments'
ORDER BY ordinal_position;


