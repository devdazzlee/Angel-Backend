-- =============================================
-- TERMS AND PRIVACY POLICY ACCEPTANCE TABLE
-- Run this in your Supabase SQL Editor
-- =============================================

-- User Legal Acceptances Table
CREATE TABLE IF NOT EXISTS user_legal_acceptances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    terms_accepted BOOLEAN DEFAULT false,
    terms_accepted_at TIMESTAMP WITH TIME ZONE,
    terms_accepted_name VARCHAR(255),
    terms_accepted_date DATE,
    privacy_accepted BOOLEAN DEFAULT false,
    privacy_accepted_at TIMESTAMP WITH TIME ZONE,
    privacy_accepted_name VARCHAR(255),
    privacy_accepted_date DATE,
    email_confirmation_sent BOOLEAN DEFAULT false,
    email_confirmation_sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_legal_acceptances_user_id ON user_legal_acceptances(user_id);

-- Enable RLS
ALTER TABLE user_legal_acceptances ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view their own acceptances" 
    ON user_legal_acceptances FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert acceptances" 
    ON user_legal_acceptances FOR INSERT 
    WITH CHECK (true);

CREATE POLICY "Service role can update acceptances" 
    ON user_legal_acceptances FOR UPDATE 
    USING (true);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_legal_acceptances_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_user_legal_acceptances_updated_at 
    BEFORE UPDATE ON user_legal_acceptances 
    FOR EACH ROW 
    EXECUTE FUNCTION update_legal_acceptances_updated_at();


