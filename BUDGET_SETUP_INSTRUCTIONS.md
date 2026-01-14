# Budget Tracking Setup Instructions

## Root Cause
The `budgets` and `budget_items` tables do not exist in your Supabase database. This is why you're getting the error:
```
Could not find the table 'public.budgets' in the schema cache
```

## Solution: Create the Database Tables

### Step 1: Open Supabase SQL Editor
1. Go to your Supabase Dashboard: https://supabase.com/dashboard
2. Select your project
3. Navigate to **SQL Editor** in the left sidebar

### Step 2: Run the Budget Schema SQL
1. Click **New Query**
2. Copy the entire contents of `budget_schema.sql`
3. Paste it into the SQL Editor
4. Click **Run** (or press Cmd/Ctrl + Enter)

### Step 3: Verify Tables Were Created
Run this query to verify:
```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('budgets', 'budget_items');
```

You should see both tables listed.

### Step 4: Verify RLS Policies
Run this query to verify RLS is enabled:
```sql
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('budgets', 'budget_items');
```

Both should show `rowsecurity = true`.

## What This Creates

1. **`budgets` table**: Stores budget information per session
   - `id`, `session_id`, `user_id`
   - `initial_investment`, `total_estimated_expenses`, `total_estimated_revenue`
   - `total_actual_expenses`, `total_actual_revenue`
   - Timestamps

2. **`budget_items` table**: Stores individual budget line items
   - `id`, `budget_id`, `name`, `category` (expense/revenue)
   - `estimated_amount`, `actual_amount`, `description`, `is_custom`
   - Timestamps

3. **Indexes**: For performance on common queries
4. **RLS Policies**: Security to ensure users can only access their own budgets
5. **Triggers**: Auto-update `updated_at` timestamps

## After Setup

Once the tables are created, restart your backend server and the budget endpoints will work:
- `GET /api/sessions/{session_id}/budget` - Get budget
- `POST /api/sessions/{session_id}/budget` - Create/update budget
- `POST /api/sessions/{session_id}/budget/items` - Add item
- `PUT /api/sessions/{session_id}/budget/items/{item_id}` - Update item
- `DELETE /api/sessions/{session_id}/budget/items/{item_id}` - Delete item
- `GET /api/sessions/{session_id}/budget/summary` - Get summary

## Troubleshooting

If you get errors:
1. **"relation already exists"**: Tables already created, you can skip
2. **"permission denied"**: Make sure you're using the service role key or have proper permissions
3. **"function does not exist"**: The `update_updated_at_column` function should be created by the main schema first. If not, it will be created by this script.

