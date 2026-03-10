-- SQL Queries to Check Recovery Token Expiry
-- Note: Supabase auth configuration is NOT stored in regular tables,
-- so these queries may not return the expiry setting directly.
-- However, they can help check for stored tokens or related data.

-- 1. Check if there are any stored recovery tokens in custom tables
SELECT 
    'password_reset_tokens' as table_name,
    COUNT(*) as token_count,
    MIN(expires_at - created_at) as min_expiry,
    MAX(expires_at - created_at) as max_expiry,
    AVG(EXTRACT(EPOCH FROM (expires_at - created_at))) as avg_expiry_seconds
FROM password_reset_tokens
WHERE used = false AND expires_at > NOW();

-- 2. Check recent recovery tokens and their expiry times
SELECT 
    email,
    created_at,
    expires_at,
    EXTRACT(EPOCH FROM (expires_at - created_at)) as expiry_seconds,
    EXTRACT(EPOCH FROM (expires_at - created_at)) / 60 as expiry_minute
    expires_at - NOW() as time_remaining
FROM password_reset_tokens
WHERE used = false 
    AND expires_at > NOW()
ORDER BY created_at DESC
LIMIT 10;

-- 3. Check Supabase auth configuration (if accessible)
-- This usually doesn't work as config is in Supabase's internal system
SELECT 
    name,
    value,
    description
FROM pg_settings
WHERE name LIKE '%auth%' OR name LIKE '%token%' OR name LIKE '%expiry%'
ORDER BY name;

-- 4. Check for any auth-related configuration tables
SELECT 
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_name LIKE '%auth%' 
    OR table_name LIKE '%token%'
    OR table_name LIKE '%config%'
ORDER BY table_schema, table_name;

-- 5. Check actual token expiration from auth.flow_state (Supabase internal)
-- This might show recovery tokens if they're stored
SELECT 
    id,
    user_id,
    auth_code,
    code_challenge_method,
    created_at,
    updated_at,
    expires_at,
    EXTRACT(EPOCH FROM (expires_at - created_at)) as expiry_seconds
FROM auth.flow_state
WHERE auth_code IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;

-- Note: The actual "Recovery Token Expiry" setting is in Supabase Dashboard
-- and cannot be queried via SQL. Use the Python script instead:
-- python3 check_recovery_token_expiry.py your-email@example.com
