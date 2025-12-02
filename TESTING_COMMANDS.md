# Testing Commands for Angel Backend

This document describes special testing commands available during development.

⚠️ **IMPORTANT**: All changes are marked with 🧪 emoji for easy identification and removal.

---

## Skip to Question 44 (Business Plan Phase)

### Purpose
Allows testers to skip directly to question 44 in the Business Plan phase without answering all 46 questions. This is useful for:
- Testing the end of the Business Plan phase
- Testing the transition to Roadmap phase
- Quick iteration during development

### Usage

1. Start a new session and complete KYC phase
2. Answer 1-2 questions in the Business Plan phase
3. Type any of these commands in the chat:
   - `skip to 44`
   - `jump to 44`
   - `goto 44`
   - `skip 44`

### What Happens

- Session is updated to question 44
- Answered count is set to 43 (questions 1-43 marked as answered)
- Progress shows 93% complete (43/46)
- You can then answer questions 44, 45, and 46 to complete the phase

### Example Flow

```
User: [Answers Q1 and Q2]
User: skip to 44
Angel: 🧪 Testing Mode: Skipped to Question 44
       You're now at question 44 of 46 in the Business Plan phase.
       Please provide your answer to continue.
User: [Answers Q44]
User: [Answers Q45]
User: [Answers Q46]
Angel: [Triggers Business Plan Summary and Roadmap Transition]
```

### Limitations

- Only works during the Business Plan phase
- Cannot be used in KYC, Roadmap, or Implementation phases
- The skip command itself is not saved to chat history

## Removing Testing Commands

### Backend (API)

**Location**: `/routers/angel_router.py`
**Function**: `post_chat()`
**Search for**: `# 🧪 TESTING COMMAND`

**To Remove**:
1. Open `/routers/angel_router.py`
2. Find the section marked with `# 🧪 TESTING COMMAND: Skip to question 44`
3. Delete the entire if-block (approximately 40 lines)
4. The code starts with:
   ```python
   # 🧪 TESTING COMMAND: Skip to question 44 in Business Plan phase
   if payload.content.strip().lower() in ["skip to 44", "jump to 44", "goto 44", "skip 44"]:
   ```
5. Delete until the closing of the else block and the empty line before `# Save user message`

### Frontend (UI Button)

**Location**: `/Azure-Angel-Frontend/src/pages/Venture/venture.tsx`
**Search for**: `# 🧪 TESTING: Skip to Q44 Button`

**To Remove**:
1. Open `/src/pages/Venture/venture.tsx`
2. Find the section marked with `{/* 🧪 TESTING: Skip to Q44 Button - Only show in Business Plan phase */}`
3. Delete the entire button block (approximately 20 lines)
4. The code starts with:
   ```tsx
   {/* 🧪 TESTING: Skip to Q44 Button - Only show in Business Plan phase */}
   {progress.phase === ("BUSINESS_PLAN" as ProgressState['phase']) && (
   ```
5. Delete until the closing `)}` of the conditional rendering

### Code to Remove (Backend)

Search for `# 🧪 TESTING COMMAND` and delete the entire if-block:

```python
# 🧪 TESTING COMMAND: Skip to question 44 in Business Plan phase
if payload.content.strip().lower() in ["skip to 44", "jump to 44", "goto 44", "skip 44"]:
    current_phase = session.get("current_phase", "")
    if current_phase == "BUSINESS_PLAN":
        # Update session to question 44
        update_data = {
            "asked_q": "BUSINESS_PLAN.44",
            "answered_count": 43  # 43 questions answered (1-43)
        }
        await patch_session(session_id, update_data)
        
        # CRITICAL: Update the local session object so subsequent operations use the new state
        session.update(update_data)
        
        # Reload session from database to ensure we have the latest state
        session = await get_session(session_id, user_id)
        
        # Don't save the skip command to history
        # Get the actual question 44 from the backend
        # Note: get_angel_reply is already imported at the top of the file
        
        # Create a dummy message to trigger question 44
        dummy_msg = {"role": "user", "content": "Please show me question 44"}
        angel_response = await get_angel_reply(dummy_msg, history, session)
        
        if isinstance(angel_response, dict):
            assistant_reply = angel_response["reply"]
        else:
            assistant_reply = angel_response
        
        # Return the actual question 44
        return {
            "success": True,
            "message": "Skipped to question 44",
            "result": {
                "reply": assistant_reply,
                "progress": {
                    "phase": "BUSINESS_PLAN",
                    "answered": 43,
                    "total": 46,
                    "percent": 93
                },
                "session_id": session_id,
                "web_search_status": {"is_searching": False, "query": None},
                "immediate_response": None,
                "show_accept_modify": False,
                "question_number": 44
            }
        }
    else:
        return {
            "success": False,
            "message": "Skip command only works in BUSINESS_PLAN phase",
            "result": {
                "reply": "⚠️ Skip command only works during the Business Plan phase. You're currently in: " + current_phase,
                "progress": session.get("progress", {}),
                "session_id": session_id
            }
        }
```

## Complete List of Changes Made

### 1. Backend API Endpoint (`/routers/angel_router.py`)
**Location**: Inside `post_chat()` function, after line ~258
**Search for**: `# 🧪 TESTING COMMAND: Skip to question 44`
**Lines**: Approximately 50 lines
**What it does**: Intercepts "skip to 44" command and updates session

### 2. Backend Sequence Validation (`/services/angel_service.py`)
**Location**: Inside `validate_business_plan_sequence()` function, line ~817
**Search for**: `# 🧪 TESTING: Check if we're in testing mode`
**Lines**: Approximately 10 lines
**What it does**: Detects testing mode and skips sequence validation

**Code to remove**:
```python
# 🧪 TESTING: Check if we're in testing mode (answered_count doesn't match asked_q)
# This happens when using "skip to 44" command
asked_q = session_data.get("asked_q", "BUSINESS_PLAN.01")
answered_count = session_data.get("answered_count", 0)

if "BUSINESS_PLAN." in asked_q:
    asked_q_num = int(asked_q.split(".")[1])
    
    # If asked_q is 44 but answered_count is 43, we're in testing mode - skip validation
    if asked_q_num >= 44 and answered_count == 43:
        print(f"🧪 TESTING MODE DETECTED: asked_q={asked_q}, answered_count={answered_count}")
        print(f"🧪 Skipping sequence validation to allow testing of questions 44-46")
        return reply
```

### 3. Frontend UI Button (`/Azure-Angel-Frontend/src/pages/Venture/venture.tsx`)
**Location**: Inside Quick Actions section, after Scrapping button, line ~3870
**Search for**: `{/* 🧪 TESTING: Skip to Q44 Button`
**Lines**: Approximately 20 lines
**What it does**: Renders purple "Skip to 44" button in UI

**Code to remove**:
```tsx
{/* 🧪 TESTING: Skip to Q44 Button - Only show in Business Plan phase */}
{progress.phase === ("BUSINESS_PLAN" as ProgressState['phase']) && (
  <button
    onClick={() => handleNext("skip to 44")}
    disabled={loading}
    className="group relative bg-gradient-to-br from-purple-50 to-pink-50 hover:from-purple-100 hover:to-pink-100 border border-purple-200 hover:border-purple-300 rounded-xl p-4 transition-all duration-300 transform hover:scale-105 hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
  >
    <div className="flex flex-col items-center space-y-2">
      <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-600 rounded-full flex items-center justify-center text-white text-lg group-hover:scale-110 transition-transform duration-300">
        ⏭️
      </div>
      <div className="text-center">
        <div className="text-sm font-semibold text-purple-800 group-hover:text-purple-900">Skip to 44</div>
        <div className="text-xs text-purple-600 group-hover:text-purple-700">Testing only</div>
      </div>
    </div>
    <div className="absolute inset-0 bg-gradient-to-br from-purple-500/10 to-pink-500/10 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
  </button>
)}
```

### 4. Documentation File (`/Angel-Backend/TESTING_COMMANDS.md`)
**Location**: Root of Angel-Backend folder
**What it is**: This entire file
**What to do**: Delete the entire file when removing testing features

---

## Quick Revert Instructions

### Step 1: Remove Backend API Command
1. Open `/Angel-Backend/routers/angel_router.py`
2. Search for `# 🧪 TESTING COMMAND`
3. Delete the entire if-block (~50 lines)

### Step 2: Remove Backend Sequence Validation Bypass
1. Open `/Angel-Backend/services/angel_service.py`
2. Search for `# 🧪 TESTING: Check if we're in testing mode`
3. Delete the testing mode detection block (~10 lines)
4. Keep the rest of the `validate_business_plan_sequence()` function

### Step 3: Remove Frontend Button
1. Open `/Azure-Angel-Frontend/src/pages/Venture/venture.tsx`
2. Search for `{/* 🧪 TESTING: Skip to Q44 Button`
3. Delete the entire conditional button block (~20 lines)

### Step 4: Remove Documentation
1. Delete `/Angel-Backend/TESTING_COMMANDS.md`

---

## Security Note

⚠️ **IMPORTANT**: Remove all testing commands before deploying to production!

These commands bypass the normal flow and should only be used during development and testing.

**All testing code is marked with 🧪 emoji** for easy identification.

## UI Button

A "Skip to 44" button is also available in the frontend during the Business Plan phase:

### Location
- Appears in the "Quick Actions" section
- Only visible during Business Plan phase
- Located after Support, Draft, and Scrapping buttons

### Appearance
- Purple/pink gradient design
- ⏭️ Icon
- Label: "Skip to 44"
- Subtitle: "Testing only"

### How It Works
- Clicking the button sends "skip to 44" command to the backend
- Backend processes it the same as typing the command
- Session updates to question 44
- Progress bar updates to 93%

## Future Testing Commands

You can add more testing commands following the same pattern:

**Backend**:
- Check for specific keywords in `payload.content`
- Perform the testing action
- Return appropriate response
- Mark clearly with `# 🧪 TESTING COMMAND` comment

**Frontend**:
- Add conditional button rendering based on phase
- Use `handleNext("command text")` to send command
- Style with distinct colors to indicate testing feature
- Mark clearly with `{/* 🧪 TESTING: ... */}` comment

