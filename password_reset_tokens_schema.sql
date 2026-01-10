-- Password Reset Tokens Table
-- Stores password reset tokens with 10-minute expiration for validation
-- This table tracks reset tokens separately from Supabase's built-in tokens
-- to enforce our custom 10-minute expiration policy

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    used_at TIMESTAMPTZ,
    CONSTRAINT token_not_expired CHECK (expires_at > created_at)
);

-- Index for fast token lookups
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at);

-- Index for cleanup of expired tokens
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_unused_expired ON password_reset_tokens(used, expires_at) WHERE used = FALSE;

-- Function to clean up expired tokens (run periodically via cron or scheduled job)
CREATE OR REPLACE FUNCTION cleanup_expired_reset_tokens()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM password_reset_tokens
    WHERE expires_at < NOW() OR (used = TRUE AND used_at < NOW() - INTERVAL '7 days');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- Enable Row Level Security (RLS)
ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;

-- Policy: Only service role can access this table
CREATE POLICY "Service role can manage password reset tokens"
    ON password_reset_tokens
    FOR ALL
    USING (auth.role() = 'service_role');

-- Comment for documentation
COMMENT ON TABLE password_reset_tokens IS 'Stores password reset tokens with 10-minute expiration for validation';
COMMENT ON COLUMN password_reset_tokens.expires_at IS 'Token expiration time (10 minutes from creation)';
COMMENT ON COLUMN password_reset_tokens.used IS 'Whether this token has been used to reset a password';

