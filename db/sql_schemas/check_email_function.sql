-- Function to check if email already exists in auth.users
-- This prevents duplicate signups by checking BEFORE user creation
-- Run this in your Supabase SQL Editor

CREATE OR REPLACE FUNCTION check_email_exists(email_address TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check if email exists in auth.users table (case-insensitive)
    RETURN EXISTS (
        SELECT 1 
        FROM auth.users 
        WHERE LOWER(TRIM(email)) = LOWER(TRIM(email_address))
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION check_email_exists(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION check_email_exists(TEXT) TO service_role;

