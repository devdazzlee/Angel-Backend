-- Implementation task proof-of-completion documents (metadata + Supabase Storage linkage)
-- Run in Supabase SQL Editor after creating the storage bucket (see bottom).

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS implementation_task_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    task_id VARCHAR(100) NOT NULL,
    file_id VARCHAR(255) NOT NULL,
    original_filename TEXT NOT NULL,
    content_type VARCHAR(120) NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    storage_bucket VARCHAR(120) NOT NULL,
    storage_path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT implementation_task_documents_file_id_unique UNIQUE (file_id)
);

CREATE INDEX IF NOT EXISTS idx_impl_task_docs_session_task
    ON implementation_task_documents (session_id, task_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_impl_task_docs_user_id
    ON implementation_task_documents (user_id);

COMMENT ON TABLE implementation_task_documents IS
    'Proof-of-completion uploads for Implementation tasks; bytes live in Supabase Storage.';

ALTER TABLE implementation_task_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their implementation documents" ON implementation_task_documents;
CREATE POLICY "Users can view their implementation documents"
    ON implementation_task_documents FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their implementation documents" ON implementation_task_documents;
CREATE POLICY "Users can delete their implementation documents"
    ON implementation_task_documents FOR DELETE
    USING (auth.uid() = user_id);

-- Refresh PostgREST schema cache after creating the table (run once if API still 404s)
-- NOTIFY pgrst, 'reload schema';

-- =============================================
-- Storage bucket
-- If you already created a bucket in the Supabase dashboard (e.g. "Founderport Docuemnts"),
-- you do NOT need to run the INSERT below — set SUPABASE_IMPLEMENTATION_BUCKET in .env instead.
-- Optional: create a dedicated private bucket via:
-- =============================================
-- INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
-- VALUES (
--     'implementation-documents',
--     'implementation-documents',
--     false,
--     10485760,
--     ARRAY[
--         'application/pdf',
--         'application/msword',
--         'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
--         'image/jpeg',
--         'image/png'
--     ]::text[]
-- )
-- ON CONFLICT (id) DO NOTHING;
