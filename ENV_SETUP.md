# Environment Variables Setup Guide

## Overview

This guide explains how to create and activate environment variables for the Angel Backend project.

---

## Step 1: Create the .env File

1. **Copy the example file:**
   ```bash
   cd /Users/mac/Desktop/Ahmed\ Work/Angel2/Angel-Backend
   cp .env.example .env
   ```

2. **Open the .env file in your editor:**
   ```bash
   nano .env
   # or
   code .env
   # or
   open -a TextEdit .env
   ```

3. **Fill in your actual values:**
   - `OPENAI_API_KEY`: Get from https://platform.openai.com/api-keys
   - `SUPABASE_URL`: Get from your Supabase project settings
   - `SUPABASE_SERVICE_ROLE_KEY`: Get from your Supabase project API settings
   - `RESEARCH_CACHE_TTL`: Optional (defaults to 21600 seconds if not set)

---

## Step 2: Activate the Virtual Environment

The project already has a virtual environment in the `myenv/` directory.

### On macOS/Linux:

```bash
# Navigate to the project directory
cd /Users/mac/Desktop/Ahmed\ Work/Angel2/Angel-Backend

# Activate the virtual environment
source myenv/bin/activate
```

After activation, you should see `(myenv)` at the beginning of your terminal prompt.

### Verify activation:

```bash
# Check Python location (should point to myenv)
which python

# Should output something like:
# /Users/mac/Desktop/Ahmed Work/Angel2/Angel-Backend/myenv/bin/python
```

---

## Step 3: Verify Environment Variables are Loaded

The project uses `python-dotenv` which automatically loads `.env` when you import modules that use `load_dotenv()`.

You can verify your environment variables are loaded by running:

```bash
# Make sure virtual environment is activated first
source myenv/bin/activate

# Test loading environment variables
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('OPENAI_API_KEY:', 'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET'); print('SUPABASE_URL:', 'SET' if os.getenv('SUPABASE_URL') else 'NOT SET')"
```

---

## Step 4: Deactivate Virtual Environment (When Done)

When you're finished working, you can deactivate the virtual environment:

```bash
deactivate
```

---

## Quick Start Commands

```bash
# 1. Navigate to project
cd /Users/mac/Desktop/Ahmed\ Work/Angel2/Angel-Backend

# 2. Create .env file (if not exists)
cp .env.example .env
# Then edit .env with your actual values

# 3. Activate virtual environment
source myenv/bin/activate

# 4. Run the application
uvicorn main:app --reload
# or
python main.py
```

---

## Troubleshooting

### Issue: "Module not found" errors
**Solution:** Make sure the virtual environment is activated and dependencies are installed:
```bash
source myenv/bin/activate
pip install -r requirements.txt
```

### Issue: Environment variables not loading
**Solution:** 
1. Verify `.env` file exists in the project root
2. Check that variable names match exactly (case-sensitive)
3. Ensure no extra spaces around the `=` sign
4. Verify `python-dotenv` is installed: `pip install python-dotenv`

### Issue: Virtual environment not found
**Solution:** Create a new virtual environment:
```bash
python3 -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt
```

---

## Environment Variables Reference

| Variable | Required | Description | Where to Get |
|----------|----------|-------------|--------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for AI services | https://platform.openai.com/api-keys |
| `SUPABASE_URL` | Yes | Your Supabase project URL | Supabase Dashboard > Settings > API |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key | Supabase Dashboard > Settings > API |
| `RESEARCH_CACHE_TTL` | No | Cache duration in seconds (default: 21600) | - |

---

## Security Notes

- ⚠️ **Never commit `.env` to git** - It's already in `.gitignore`
- ⚠️ **Never share your API keys** publicly
- ⚠️ **Use different keys for development and production**
- ✅ **Use `.env.example` as a template** for team members

