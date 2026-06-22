-- Implementation task / substep completions (source of truth for Progress UI)
-- Run in Supabase SQL Editor. Then: NOTIFY pgrst, 'reload schema';

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS implementation_completions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    task_id VARCHAR(100) NOT NULL,
    substep_number INTEGER,
    -- Matches legacy ids: business_structure_selection or business_structure_selection_substep_1
    completion_key VARCHAR(150) NOT NULL,
    phase VARCHAR(50) NOT NULL,
    completion_notes TEXT,
    decision TEXT,
    actions TEXT,
    documents TEXT,
    file_id VARCHAR(255),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT implementation_completions_session_key_unique UNIQUE (session_id, completion_key)
);

CREATE INDEX IF NOT EXISTS idx_impl_completions_session
    ON implementation_completions (session_id, completed_at DESC);

CREATE INDEX IF NOT EXISTS idx_impl_completions_task
    ON implementation_completions (session_id, task_id);

COMMENT ON TABLE implementation_completions IS
    'One row per completed implementation task or substep. Drives Progress metrics.';

ALTER TABLE implementation_completions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their implementation completions" ON implementation_completions;
CREATE POLICY "Users can view their implementation completions"
    ON implementation_completions FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their implementation completions" ON implementation_completions;
CREATE POLICY "Users can insert their implementation completions"
    ON implementation_completions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their implementation completions" ON implementation_completions;
CREATE POLICY "Users can update their implementation completions"
    ON implementation_completions FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their implementation completions" ON implementation_completions;
CREATE POLICY "Users can delete their implementation completions"
    ON implementation_completions FOR DELETE
    USING (auth.uid() = user_id);

-- NOTIFY pgrst, 'reload schema';
