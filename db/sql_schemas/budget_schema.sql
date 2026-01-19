-- =============================================
-- BUDGET TRACKING TABLES FOR ANGEL AI
-- Run this in your Supabase SQL Editor
-- =============================================

-- Budgets Table
CREATE TABLE IF NOT EXISTS budgets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    initial_investment DECIMAL(15, 2) DEFAULT 0,
    total_estimated_expenses DECIMAL(15, 2) DEFAULT 0,
    total_estimated_revenue DECIMAL(15, 2) DEFAULT 0,
    total_actual_expenses DECIMAL(15, 2) DEFAULT 0,
    total_actual_revenue DECIMAL(15, 2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(session_id)
);

-- Budget Items Table
CREATE TABLE IF NOT EXISTS budget_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    budget_id UUID NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('expense', 'revenue')),
    estimated_amount DECIMAL(15, 2) NOT NULL DEFAULT 0,
    actual_amount DECIMAL(15, 2) DEFAULT NULL,
    description TEXT,
    is_custom BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_budgets_session_id ON budgets(session_id);
CREATE INDEX IF NOT EXISTS idx_budgets_user_id ON budgets(user_id);
CREATE INDEX IF NOT EXISTS idx_budget_items_budget_id ON budget_items(budget_id);
CREATE INDEX IF NOT EXISTS idx_budget_items_category ON budget_items(category);

-- Enable RLS
ALTER TABLE budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_items ENABLE ROW LEVEL SECURITY;

-- RLS Policies for budgets
CREATE POLICY "Users can view their own budgets" 
    ON budgets FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own budgets" 
    ON budgets FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own budgets" 
    ON budgets FOR UPDATE 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own budgets" 
    ON budgets FOR DELETE 
    USING (auth.uid() = user_id);

-- RLS Policies for budget_items
CREATE POLICY "Users can view their own budget items" 
    ON budget_items FOR SELECT 
    USING (
        EXISTS (
            SELECT 1 FROM budgets 
            WHERE budgets.id = budget_items.budget_id 
            AND budgets.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert their own budget items" 
    ON budget_items FOR INSERT 
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM budgets 
            WHERE budgets.id = budget_items.budget_id 
            AND budgets.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update their own budget items" 
    ON budget_items FOR UPDATE 
    USING (
        EXISTS (
            SELECT 1 FROM budgets 
            WHERE budgets.id = budget_items.budget_id 
            AND budgets.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete their own budget items" 
    ON budget_items FOR DELETE 
    USING (
        EXISTS (
            SELECT 1 FROM budgets 
            WHERE budgets.id = budget_items.budget_id 
            AND budgets.user_id = auth.uid()
        )
    );

-- Trigger for updated_at (function may already exist from main schema)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_budgets_updated_at 
    BEFORE UPDATE ON budgets 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_budget_items_updated_at 
    BEFORE UPDATE ON budget_items 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

