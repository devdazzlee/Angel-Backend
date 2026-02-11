-- Function to get user by email from auth.users table
-- This efficiently queries auth.users directly without pagination
-- Returns user data as JSON if found, NULL otherwise
-- Run this in your Supabase SQL Editor

CREATE OR REPLACE FUNCTION get_user_by_email(email_address TEXT)
RETURNS JSON AS $$
DECLARE
    user_record RECORD;
    result JSON;
BEGIN
    -- Query auth.users table directly (case-insensitive)
    SELECT 
        id,
        email,
        email_confirmed_at,
        created_at,
        updated_at,
        raw_user_meta_data,
        raw_app_meta_data
    INTO user_record
    FROM auth.users 
    WHERE LOWER(TRIM(email)) = LOWER(TRIM(email_address))
    LIMIT 1;
    
    -- If user found, return as JSON
    IF user_record.id IS NOT NULL THEN
        result := json_build_object(
            'id', user_record.id,
            'email', user_record.email,
            'email_confirmed_at', user_record.email_confirmed_at,
            'created_at', user_record.created_at,
            'updated_at', user_record.updated_at,
            'user_metadata', user_record.raw_user_meta_data,
            'app_metadata', user_record.raw_app_meta_data
        );
        RETURN result;
    END IF;
    
    -- User not found
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION get_user_by_email(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_by_email(TEXT) TO service_role;



