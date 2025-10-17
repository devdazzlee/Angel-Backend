-- Angle-Ai Database Schema for New Supabase Project
-- Run this in your Supabase SQL Editor to create all necessary tables

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- CORE TABLES
-- =============================================

-- Chat Sessions Table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title VARCHAR(120) NOT NULL DEFAULT 'Untitled',
    current_phase VARCHAR(50) NOT NULL DEFAULT 'KYC',
    asked_q VARCHAR(20) NOT NULL DEFAULT 'KYC.01',
    answered_count INTEGER NOT NULL DEFAULT 0,
    business_context JSONB DEFAULT '{}',
    roadmap_data JSONB DEFAULT NULL,
    implementation_data JSONB DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Chat History Table
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    phase VARCHAR(50) DEFAULT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- BUSINESS PLANNING TABLES
-- =============================================

-- Business Plans Table
CREATE TABLE IF NOT EXISTS business_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan_type VARCHAR(50) NOT NULL DEFAULT 'comprehensive',
    content TEXT NOT NULL,
    summary TEXT DEFAULT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Roadmaps Table
CREATE TABLE IF NOT EXISTS roadmaps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    roadmap_type VARCHAR(50) NOT NULL DEFAULT 'comprehensive',
    content TEXT NOT NULL,
    phases JSONB DEFAULT '[]',
    tasks JSONB DEFAULT '[]',
    timeline JSONB DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'in_progress', 'completed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- IMPLEMENTATION TABLES
-- =============================================

-- Implementation Tasks Table
CREATE TABLE IF NOT EXISTS implementation_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    roadmap_id UUID REFERENCES roadmaps(id) ON DELETE CASCADE,
    task_name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT NULL,
    phase VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    due_date TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Service Providers Table
CREATE TABLE IF NOT EXISTS service_providers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    task_id UUID REFERENCES implementation_tasks(id) ON DELETE CASCADE,
    provider_name VARCHAR(255) NOT NULL,
    provider_type VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100) DEFAULT NULL,
    is_local BOOLEAN NOT NULL DEFAULT false,
    description TEXT DEFAULT NULL,
    contact_info JSONB DEFAULT '{}',
    rating DECIMAL(3,2) DEFAULT NULL CHECK (rating >= 0 AND rating <= 5),
    price_range VARCHAR(50) DEFAULT NULL,
    location VARCHAR(255) DEFAULT NULL,
    website VARCHAR(500) DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- RESEARCH & RAG TABLES
-- =============================================

-- Research Sources Table
CREATE TABLE IF NOT EXISTS research_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    query VARCHAR(500) NOT NULL,
    source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('web_search', 'rag', 'agent', 'manual')),
    source_url VARCHAR(1000) DEFAULT NULL,
    content TEXT NOT NULL,
    relevance_score DECIMAL(3,2) DEFAULT NULL CHECK (relevance_score >= 0 AND relevance_score <= 1),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- RAG Documents Table
CREATE TABLE IF NOT EXISTS rag_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_name VARCHAR(255) NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- SPECIALIZED AGENTS TABLES
-- =============================================

-- Agent Interactions Table
CREATE TABLE IF NOT EXISTS agent_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    agent_type VARCHAR(100) NOT NULL,
    question TEXT NOT NULL,
    response TEXT NOT NULL,
    business_context JSONB DEFAULT '{}',
    confidence_score DECIMAL(3,2) DEFAULT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- USER PREFERENCES & SETTINGS
-- =============================================

-- User Preferences Table
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    communication_style VARCHAR(50) DEFAULT 'professional',
    industry VARCHAR(100) DEFAULT NULL,
    location VARCHAR(255) DEFAULT NULL,
    business_type VARCHAR(100) DEFAULT NULL,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- ANALYTICS & TRACKING TABLES
-- =============================================

-- User Activity Table
CREATE TABLE IF NOT EXISTS user_activity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    activity_type VARCHAR(50) NOT NULL,
    activity_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

-- Chat Sessions Indexes
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_current_phase ON chat_sessions(current_phase);

-- Chat History Indexes
CREATE INDEX IF NOT EXISTS idx_chat_history_session_id ON chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created_at ON chat_history(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_history_phase ON chat_history(phase);

-- Business Plans Indexes
CREATE INDEX IF NOT EXISTS idx_business_plans_session_id ON business_plans(session_id);
CREATE INDEX IF NOT EXISTS idx_business_plans_status ON business_plans(status);

-- Roadmaps Indexes
CREATE INDEX IF NOT EXISTS idx_roadmaps_session_id ON roadmaps(session_id);
CREATE INDEX IF NOT EXISTS idx_roadmaps_status ON roadmaps(status);

-- Implementation Tasks Indexes
CREATE INDEX IF NOT EXISTS idx_implementation_tasks_session_id ON implementation_tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_implementation_tasks_status ON implementation_tasks(status);
CREATE INDEX IF NOT EXISTS idx_implementation_tasks_phase ON implementation_tasks(phase);
CREATE INDEX IF NOT EXISTS idx_implementation_tasks_due_date ON implementation_tasks(due_date);

-- Service Providers Indexes
CREATE INDEX IF NOT EXISTS idx_service_providers_session_id ON service_providers(session_id);
CREATE INDEX IF NOT EXISTS idx_service_providers_category ON service_providers(category);
CREATE INDEX IF NOT EXISTS idx_service_providers_is_local ON service_providers(is_local);

-- Research Sources Indexes
CREATE INDEX IF NOT EXISTS idx_research_sources_session_id ON research_sources(session_id);
CREATE INDEX IF NOT EXISTS idx_research_sources_source_type ON research_sources(source_type);

-- RAG Documents Indexes
CREATE INDEX IF NOT EXISTS idx_rag_documents_document_type ON rag_documents(document_type);

-- Agent Interactions Indexes
CREATE INDEX IF NOT EXISTS idx_agent_interactions_session_id ON agent_interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_interactions_agent_type ON agent_interactions(agent_type);

-- User Activity Indexes
CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity(user_id);
CREATE INDEX IF NOT EXISTS idx_user_activity_activity_type ON user_activity(activity_type);

-- =============================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- =============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_chat_sessions_updated_at BEFORE UPDATE ON chat_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_business_plans_updated_at BEFORE UPDATE ON business_plans FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_roadmaps_updated_at BEFORE UPDATE ON roadmaps FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_implementation_tasks_updated_at BEFORE UPDATE ON implementation_tasks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_rag_documents_updated_at BEFORE UPDATE ON rag_documents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_preferences_updated_at BEFORE UPDATE ON user_preferences FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =============================================

-- Enable RLS on all tables
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE roadmaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE implementation_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE service_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_activity ENABLE ROW LEVEL SECURITY;

-- RLS Policies for chat_sessions
CREATE POLICY "Users can view their own sessions" ON chat_sessions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own sessions" ON chat_sessions FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own sessions" ON chat_sessions FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete their own sessions" ON chat_sessions FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for chat_history
CREATE POLICY "Users can view their own chat history" ON chat_history FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own chat history" ON chat_history FOR INSERT WITH CHECK (auth.uid() = user_id);

-- RLS Policies for business_plans
CREATE POLICY "Users can view their own business plans" ON business_plans FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own business plans" ON business_plans FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own business plans" ON business_plans FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete their own business plans" ON business_plans FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for roadmaps
CREATE POLICY "Users can view their own roadmaps" ON roadmaps FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own roadmaps" ON roadmaps FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own roadmaps" ON roadmaps FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete their own roadmaps" ON roadmaps FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for implementation_tasks
CREATE POLICY "Users can view their own implementation tasks" ON implementation_tasks FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own implementation tasks" ON implementation_tasks FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own implementation tasks" ON implementation_tasks FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete their own implementation tasks" ON implementation_tasks FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for service_providers
CREATE POLICY "Users can view their own service providers" ON service_providers FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own service providers" ON service_providers FOR INSERT WITH CHECK (auth.uid() = user_id);

-- RLS Policies for research_sources
CREATE POLICY "Users can view their own research sources" ON research_sources FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own research sources" ON research_sources FOR INSERT WITH CHECK (auth.uid() = user_id);

-- RLS Policies for agent_interactions
CREATE POLICY "Users can view their own agent interactions" ON agent_interactions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own agent interactions" ON agent_interactions FOR INSERT WITH CHECK (auth.uid() = user_id);

-- RLS Policies for user_preferences
CREATE POLICY "Users can view their own preferences" ON user_preferences FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own preferences" ON user_preferences FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own preferences" ON user_preferences FOR UPDATE USING (auth.uid() = user_id);

-- RLS Policies for user_activity
CREATE POLICY "Users can view their own activity" ON user_activity FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own activity" ON user_activity FOR INSERT WITH CHECK (auth.uid() = user_id);

-- RLS Policies for rag_documents (read-only for all authenticated users)
CREATE POLICY "Authenticated users can view rag documents" ON rag_documents FOR SELECT USING (auth.role() = 'authenticated');

-- =============================================
-- SAMPLE DATA (Optional)
-- =============================================

-- Insert sample RAG documents
INSERT INTO rag_documents (document_name, document_type, content, metadata) VALUES
('Business Formation Guide', 'legal', 'Comprehensive guide to business formation including LLC, Corporation, and Partnership structures...', '{"category": "legal", "tags": ["business", "formation", "legal"]}'),
('Marketing Strategy Template', 'marketing', 'Template for developing marketing strategies including digital marketing, content marketing, and social media...', '{"category": "marketing", "tags": ["marketing", "strategy", "digital"]}'),
('Financial Planning Guide', 'finance', 'Guide to financial planning for startups including budgeting, funding, and financial projections...', '{"category": "finance", "tags": ["finance", "planning", "startup"]}')
ON CONFLICT DO NOTHING;

-- =============================================
-- VERIFICATION QUERIES
-- =============================================

-- Check if all tables were created successfully
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'chat_sessions', 'chat_history', 'business_plans', 'roadmaps', 
    'implementation_tasks', 'service_providers', 'research_sources', 
    'rag_documents', 'agent_interactions', 'user_preferences', 'user_activity'
)
ORDER BY table_name;



