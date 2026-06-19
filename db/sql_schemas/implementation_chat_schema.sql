-- Implementation Angel chat — per-venture persistent messages
-- Run this in the Supabase SQL Editor (safe to re-run; uses IF NOT EXISTS).

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- implementation_chat_messages
-- One thread per venture (chat_sessions.id), shared across Implementation tasks.
-- =============================================
CREATE TABLE IF NOT EXISTS implementation_chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    mode VARCHAR(20) DEFAULT NULL CHECK (mode IS NULL OR mode IN ('help', 'draft', 'brainstorm')),
    task_id VARCHAR(100) DEFAULT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_implementation_chat_session_created
    ON implementation_chat_messages (session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_implementation_chat_user_id
    ON implementation_chat_messages (user_id);

CREATE INDEX IF NOT EXISTS idx_implementation_chat_task_id
    ON implementation_chat_messages (session_id, task_id)
    WHERE task_id IS NOT NULL;

COMMENT ON TABLE implementation_chat_messages IS
    'Angel support-panel chat during Implementation; one conversation per venture (session).';

COMMENT ON COLUMN implementation_chat_messages.task_id IS
    'Implementation task id active when the message was sent (context only; thread is venture-wide).';

COMMENT ON COLUMN implementation_chat_messages.mode IS
    'help | draft | brainstorm — set on assistant turns and user turns when applicable.';

-- =============================================
-- Row Level Security
-- Backend uses service role; policies protect direct Supabase client access.
-- =============================================
ALTER TABLE implementation_chat_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own implementation chat" ON implementation_chat_messages;
CREATE POLICY "Users can view their own implementation chat"
    ON implementation_chat_messages FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own implementation chat" ON implementation_chat_messages;
CREATE POLICY "Users can insert their own implementation chat"
    ON implementation_chat_messages FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own implementation chat" ON implementation_chat_messages;
CREATE POLICY "Users can delete their own implementation chat"
    ON implementation_chat_messages FOR DELETE
    USING (auth.uid() = user_id);
