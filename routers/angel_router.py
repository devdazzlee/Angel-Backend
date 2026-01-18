from fastapi import APIRouter, Request, Depends, UploadFile, File, HTTPException
from schemas.angel_schemas import ChatRequestSchema, CreateSessionSchema, SyncProgressSchema
from services.session_service import create_session, list_sessions, get_session, patch_session
from services.chat_service import fetch_chat_history, save_chat_message, fetch_phase_chat_history
from services.generate_plan_service import generate_full_business_plan, generate_full_roadmap_plan, generate_comprehensive_business_plan_summary, generate_implementation_insights, generate_service_provider_preview, generate_motivational_quote
from services.angel_service import (
    get_angel_reply,
    handle_roadmap_generation,
    handle_roadmap_to_implementation_transition,
    generate_business_plan_artifact,
    extract_business_context_from_history,
)
from utils.progress import parse_tag, TOTALS_BY_PHASE, calculate_phase_progress, calculate_combined_progress, smart_trim_history
from middlewares.auth import verify_auth_token
from fastapi.middleware.cors import CORSMiddleware
from db.supabase import supabase
from utils.constant import ANGEL_SYSTEM_PROMPT
from openai import AsyncOpenAI
import re
import os
import uuid
from datetime import datetime

router = APIRouter(
    tags=["Angel"],
    dependencies=[Depends(verify_auth_token)]
)

# Build a lookup of canonical question text keyed by tag (e.g., "KYC.10")
QUESTION_TEXT_MAP = dict(
    re.findall(r'\[\[Q:([A-Z_]+\.\d{2})]]\s*([^\n]+)', ANGEL_SYSTEM_PROMPT)
)

PHASE_SEQUENCE = [
    "KYC",
    "BUSINESS_PLAN",
    "PLAN_TO_ROADMAP_TRANSITION",
    "ROADMAP",
    "ROADMAP_GENERATED",
    "ROADMAP_TO_IMPLEMENTATION_TRANSITION",
    "IMPLEMENTATION",
]

BUSINESS_CONTEXT_KEYS = ["business_name", "industry", "location", "business_type"]
DEFAULT_BUSINESS_CONTEXT = {
    "business_name": "Your Business",
    "industry": "General Business",
    "location": "United States",
    "business_type": "Startup",
}


def _phase_index(phase: str) -> int:
    try:
        return PHASE_SEQUENCE.index(phase)
    except ValueError:
        return -1


def _question_progress(asked_q: str):
    """
    Return a tuple (phase_index, question_number) that can be compared to prevent regressions.
    """
    if not asked_q or "." not in asked_q:
        return -1, -1
    phase, _, number = asked_q.partition(".")
    try:
        question_number = int(number)
    except ValueError:
        question_number = -1
    return _phase_index(phase), question_number


def _normalize_business_context(context: dict) -> dict:
    normalized = DEFAULT_BUSINESS_CONTEXT.copy()
    if not context or not isinstance(context, dict):
        return normalized
    for key in BUSINESS_CONTEXT_KEYS:
        value = context.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value:
            normalized[key] = value
    return normalized


def _has_meaningful_context(context: dict) -> bool:
    if not context or not isinstance(context, dict):
        return False
    for key in BUSINESS_CONTEXT_KEYS:
        value = context.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value:
            return True
    return False

def enforce_question_tag(reply: str, question_tag: str) -> str:
    """
    Ensure the assistant message references the expected question tag
    and leverages the canonical question text when available.
    """
    if not reply:
        return reply

    canonical_text = QUESTION_TEXT_MAP.get(question_tag)
    tag_pattern = re.compile(r'\[\[Q:[A-Z_]+\.\d{2}\]\]')

    if tag_pattern.search(reply):
        reply = tag_pattern.sub(f'[[Q:{question_tag}]]', reply, count=1)
        if canonical_text:
            reply = re.sub(
                r'\[\[Q:[A-Z_]+\.\d{2}\]\]\s*[^\n]*',
                f'[[Q:{question_tag}]] {canonical_text}',
                reply,
                count=1
            )
    else:
        question_line = (
            f'[[Q:{question_tag}]] {canonical_text}'
            if canonical_text else f'[[Q:{question_tag}]]'
        )
        reply = reply.rstrip() + "\n\n" + question_line

    return reply

@router.post("/sessions")
async def post_session(request: Request, payload: CreateSessionSchema):
    user_id = request.state.user["id"]
    session = await create_session(user_id, payload.title)
    return {"success": True, "message": "Session created", "result": session}


@router.get("/sessions")
async def get_sessions(request: Request):
    user_id = request.state.user["id"]
    sessions = await list_sessions(user_id)
    return {"success": True, "message": "Chat sessions fetched", "result": sessions}

@router.get("/sessions/{session_id}")
async def get_single_session(request: Request, session_id: str):
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    return {"success": True, "message": "Session fetched", "result": session}

@router.get("/sessions/{session_id}/history")
async def chat_history(request: Request, session_id: str):

    history = await fetch_chat_history(session_id)
    return {"success": True, "message": "Chat history fetched", "data": history}


@router.get("/sessions/{session_id}/business-context")
async def get_business_context(session_id: str, request: Request):
    """Return authoritative business context derived from KYC + Business Plan phases."""
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    stored_context = session.get("business_context") if isinstance(session.get("business_context"), dict) else {}
    if stored_context is None:
        stored_context = {}

    needs_refresh = (
        not stored_context
        or any(
            not stored_context.get(key) or not str(stored_context.get(key)).strip()
            for key in BUSINESS_CONTEXT_KEYS
        )
    )

    source = "stored"
    updated = False

    if needs_refresh:
        history = await fetch_chat_history(session_id)
        extracted_context = extract_business_context_from_history(history) or {}
        if extracted_context:
            merged_context = stored_context.copy()
            for key, value in extracted_context.items():
                if isinstance(value, str):
                    value = value.strip()
                if value and merged_context.get(key) != value:
                    merged_context[key] = value
                    updated = True
            if updated:
                await patch_session(session_id, {"business_context": merged_context})
                session["business_context"] = merged_context
                stored_context = merged_context
                source = "extracted"
        else:
            source = "fallback"

    normalized = _normalize_business_context(stored_context)

    return {
        "success": True,
        "message": "Business context fetched",
        "result": {
            "business_context": normalized,
            "source": source,
            "updated": updated
        }
    }


@router.post("/sessions/{session_id}/sync-progress")
async def sync_progress(request: Request, session_id: str, payload: SyncProgressSchema):
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)

    current_phase = session.get("current_phase", "KYC")
    current_phase_idx = _phase_index(current_phase)
    incoming_phase = payload.phase or current_phase
    incoming_phase_idx = _phase_index(incoming_phase)

    # Prevent regressions: never allow the client to move the phase backwards
    if incoming_phase_idx < current_phase_idx:
        incoming_phase = current_phase
        incoming_phase_idx = current_phase_idx

    current_answered = session.get("answered_count", 0)
    incoming_answered = payload.answered_count if payload.answered_count is not None else current_answered

    if incoming_phase_idx < current_phase_idx:
        incoming_answered = current_answered
    elif incoming_phase_idx == current_phase_idx:
        incoming_answered = max(current_answered, incoming_answered)

    updates = {
        "current_phase": incoming_phase,
        "answered_count": incoming_answered,
    }

    if payload.asked_q:
        current_q_progress = _question_progress(session.get("asked_q"))
        incoming_q_progress = _question_progress(payload.asked_q)
        # Allow update only if it moves forward (or if no previous question)
        if current_q_progress == (-1, -1) or incoming_q_progress >= current_q_progress:
            updates["asked_q"] = payload.asked_q

    await patch_session(session_id, user_id, updates)
    session.update(updates)

    return {
        "success": True,
        "message": "Session progress synced",
        "result": {
            "session_id": session_id,
            "current_phase": session["current_phase"],
            "answered_count": session["answered_count"],
            "asked_q": session.get("asked_q"),
        }
    }

@router.post("/sessions/{session_id}/chat")
async def post_chat(session_id: str, request: Request, payload: ChatRequestSchema):
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    history = await fetch_chat_history(session_id)

    # Log the incoming message for debugging
    print(f"📨 POST /chat - Received message: '{payload.content[:200]}...' (length: {len(payload.content)})")
    
    # CRITICAL: Block normal chat processing during transition phases
    # User should interact with modals, not chat during transitions
    current_phase = session.get("current_phase", "")
    transition_phases = [
        "PLAN_TO_BUDGET_TRANSITION",
        "PLAN_TO_SUMMARY_TRANSITION",
        "PLAN_TO_ROADMAP_TRANSITION",
        "ROADMAP_TO_IMPLEMENTATION_TRANSITION"
    ]
    
    if current_phase in transition_phases:
        print(f"🚫 Blocking chat message - session is in transition phase: {current_phase}")
        print(f"   User should interact with the transition modal, not send chat messages")
        return {
            "success": False,
            "message": f"Session is in {current_phase} phase. Please complete the transition first.",
            "result": {
                "reply": f"You're currently in a transition phase. Please complete the current step before continuing.",
                "progress": {
                    "phase": current_phase,
                    "answered": 1,
                    "total": 1,
                    "percent": 100
                },
                "transition_phase": current_phase
            }
        }
    
    # Save user message
    await save_chat_message(session_id, user_id, "user", payload.content)

    # Get AI reply
    angel_response = await get_angel_reply({"role": "user", "content": payload.content}, history, session)
    
    # Handle new return format
    if isinstance(angel_response, dict):
        assistant_reply = angel_response["reply"]
        web_search_status = angel_response.get("web_search_status", {"is_searching": False, "query": None})
        immediate_response = angel_response.get("immediate_response", None)
        transition_phase = angel_response.get("transition_phase", None)
        business_plan_summary = angel_response.get("business_plan_summary", None)
        session_update = angel_response.get("patch_session", None)
        show_accept_modify = angel_response.get("show_accept_modify", False)
        business_plan_artifact = angel_response.get("business_plan_artifact", None)
    else:
        # Backward compatibility
        assistant_reply = angel_response
        web_search_status = {"is_searching": False, "query": None}
        immediate_response = None
        transition_phase = None
        business_plan_summary = None
        session_update = None
        show_accept_modify = False
        business_plan_artifact = None

    # CRITICAL: Don't save assistant reply to chat history if it's a transition
    # Transitions should show modals, not appear in chat
    if transition_phase not in ["PLAN_TO_ROADMAP", "PLAN_TO_BUDGET", "PLAN_TO_SUMMARY", "KYC_TO_BUSINESS_PLAN", "ROADMAP_GENERATED", "BUDGET_SETUP"]:
        # Also check if we're in PLAN_TO_ROADMAP_TRANSITION phase - don't save to chat
        current_phase = session.get("current_phase", "")
        if current_phase != "PLAN_TO_ROADMAP_TRANSITION":
            # Save assistant reply to chat history (normal flow)
            await save_chat_message(session_id, user_id, "assistant", assistant_reply)
        else:
            print(f"🚫 Skipping chat history save - in PLAN_TO_ROADMAP_TRANSITION phase (should show modal)")
    else:
        print(f"🚫 Skipping chat history save for transition phase: {transition_phase} (will show modal instead)")

    # Handle session updates (e.g., from Accept responses)
    if session_update:
        session.update(session_update)
        await patch_session(session_id, session_update)

    # Handle transition phases
    if transition_phase == "PLAN_TO_SUMMARY":
        # Show business plan summary first, then user can proceed to budget
        # Update session to summary transition phase
        await patch_session(session_id, {
            "current_phase": "PLAN_TO_SUMMARY_TRANSITION"
        })
        
        session["current_phase"] = "PLAN_TO_SUMMARY_TRANSITION"
        session["transition_data"] = {
            "business_plan_summary": business_plan_summary,
            "business_plan_artifact": business_plan_artifact,
            "transition_type": "PLAN_TO_SUMMARY"
        }
        
        return {
            "success": True,
            "message": "Business plan completed - showing summary",
            "result": {
                "reply": assistant_reply,
                "progress": {
                    "phase": "PLAN_TO_SUMMARY_TRANSITION",
                    "answered": 45,
                    "total": 45,
                    "percent": 100
                },
                "session_id": session_id,
                "web_search_status": web_search_status,
                "immediate_response": immediate_response,
                "transition_phase": "PLAN_TO_SUMMARY",
                "business_plan_summary": business_plan_summary,
                "business_plan_artifact": business_plan_artifact,
                "show_accept_modify": show_accept_modify,
                "transition_data": session.get("transition_data")
            }
        }
    
    if transition_phase == "KYC_TO_BUSINESS_PLAN":
        # Update session to transition phase
        session["current_phase"] = "BUSINESS_PLAN"
        await patch_session(session_id, {
            "current_phase": "BUSINESS_PLAN",
            "asked_q": "BUSINESS_PLAN.01",
            "answered_count": 0
        })
        
        # Return transition response
        return {
            "success": True,
            "message": "KYC completed - transition to business plan",
            "result": {
                "reply": assistant_reply,
                "progress": {
                    "phase": "BUSINESS_PLAN",
                    "answered": 0,
                    "total": 2,
                    "percent": 0
                },
                "web_search_status": web_search_status,
                "immediate_response": immediate_response,
                "transition_phase": transition_phase
            }
        }
    
    if transition_phase == "PLAN_TO_BUDGET":
        # Transition from Business Plan to Budget phase
        from services.angel_service import handle_budget_setup
        
        # Get business plan artifact if available
        business_plan_artifact = angel_response.get("business_plan_artifact", None)
        business_plan_summary = angel_response.get("business_plan_summary", None)
        
        # Generate budget setup message
        budget_response = await handle_budget_setup(session, history)
        
        # Prepare transition data (store in memory only, not in database)
        transition_data = {
            "business_plan_summary": business_plan_summary,
            "business_plan_artifact": business_plan_artifact,
            "transition_type": "PLAN_TO_BUDGET",
            "estimated_expenses": budget_response.get("estimated_expenses", ""),
            "business_context": budget_response.get("business_context", {})
        }
        
        # Update session to budget transition phase (don't save transition_data to DB - it's not a column)
        await patch_session(session_id, {
            "current_phase": "PLAN_TO_BUDGET_TRANSITION"
        })
        
        session["current_phase"] = "PLAN_TO_BUDGET_TRANSITION"
        session["transition_data"] = transition_data  # Store in memory only
        
        return {
            "success": True,
            "message": "Business plan completed - transition to budget",
            "result": {
                "reply": budget_response["reply"],
                "progress": {
                    "phase": "PLAN_TO_BUDGET_TRANSITION",
                    "answered": 45,
                    "total": 45,
                    "percent": 100
                },
                "session_id": session_id,
                "web_search_status": web_search_status,
                "immediate_response": immediate_response,
                "transition_phase": "PLAN_TO_BUDGET",
                "business_plan_summary": business_plan_summary,
                "business_plan_artifact": business_plan_artifact,
                "estimated_expenses": budget_response.get("estimated_expenses", ""),
                "business_context": budget_response.get("business_context", {}),
                "transition_data": session.get("transition_data")
            }
        }
    
    if transition_phase == "PLAN_TO_ROADMAP":
        # CRITICAL: Get business plan artifact from angel_response if it was generated
        business_plan_artifact = angel_response.get("business_plan_artifact", None)
        patch_session_data = angel_response.get("patch_session", {})
        
        # If artifact was generated, save it to the session immediately
        if business_plan_artifact:
            print(f"💾 Saving Business Plan Artifact to session ({len(business_plan_artifact)} characters)")
            session["business_plan_artifact"] = business_plan_artifact
            session["business_plan_generated_at"] = patch_session_data.get("business_plan_generated_at", datetime.now().isoformat())
            
            # Update session in database with artifact
            await patch_session(session_id, {
                "current_phase": "PLAN_TO_ROADMAP_TRANSITION",
                "business_plan_artifact": business_plan_artifact,
                "business_plan_generated_at": session["business_plan_generated_at"]
            })
            print("✅ Business Plan Artifact saved to database")
        else:
            # Update session to transition phase
            await patch_session(session_id, {
                "current_phase": "PLAN_TO_ROADMAP_TRANSITION"
            })
        
        session["current_phase"] = "PLAN_TO_ROADMAP_TRANSITION"
        # Store transition data in session memory (not database)
        session["transition_data"] = {
            "business_plan_summary": business_plan_summary,
            "business_plan_artifact": business_plan_artifact,  # Include artifact in transition data
            "transition_type": "PLAN_TO_ROADMAP"
        }
        
        # Return transition response without normal tag processing
        return {
            "success": True,
            "message": "Business plan completed - transition to roadmap",
            "result": {
                "reply": assistant_reply,
                "progress": {
                    "phase": "PLAN_TO_ROADMAP_TRANSITION",
                    "answered": 45,
                    "total": 45,
                    "percent": 100
                },
                "session_id": session_id,
                "web_search_status": web_search_status,
                "immediate_response": immediate_response,
                "transition_phase": transition_phase,
                "business_plan_summary": business_plan_summary,
                "business_plan_artifact": business_plan_artifact,  # Include artifact in response (may be None if generating in background)
                "transition_data": session.get("transition_data")
            }
        }

    # Check if this is a command response that should not trigger tag processing
    # Also includes verification messages
    command_indicators = [
        "Here's a draft for you",
        "Here's a draft based on what you've shared",
        "Let's work through this together",
        "Here's a refined version of your thoughts",
        "I'll create additional content for you",
        "Verification:",
        "Here's what I've captured so far",
        "Does this look accurate",
        "Does this look correct"
    ]
    
    is_command_response = any(indicator in assistant_reply for indicator in command_indicators)
    
    if is_command_response:
        print(f"🔧 Command response detected - skipping tag processing to prevent question skipping")
        # Don't process tags for command responses - stay on current question
        tag = None
    else:
        # Tag handling - Only increment when moving to a genuinely new question
        last_tag = session.get("asked_q")
        tag = parse_tag(assistant_reply)

    print(f"🏷️ Tag Analysis:")
    print(f"  - Last tag: {session.get('asked_q')}")
    print(f"  - Current tag: {tag}")
    print(f"  - Is command response: {is_command_response}")
    print(f"  - Current answered_count: {session.get('answered_count', 0)}")
    print(f"  - Assistant reply preview: {assistant_reply[:100]}...")

    # Only increment answered_count when moving to a genuinely new tagged question
    # Follow-up questions or clarifications should NOT increment the count
    # Skip increment for command responses
    if not is_command_response and last_tag and tag and last_tag != tag:
        # Check if this is a genuine progression to next question
        # (not just a clarification or follow-up)
        last_phase, last_num = last_tag.split(".")
        current_phase, current_num = tag.split(".")
        
        print(f"🔄 Tag Comparison:")
        print(f"  - Last phase: {last_phase}, Last num: {last_num}")
        print(f"  - Current phase: {current_phase}, Current num: {current_num}")
        
        # Only increment if moving to next sequential question
        if (current_phase == last_phase and int(current_num) == int(last_num) + 1) or \
           (current_phase != last_phase and current_num == "01"):
            session["answered_count"] += 1
            print(f"✅ Incremented answered_count to {session['answered_count']}")
        else:
            print(f"❌ No increment - not a sequential question progression")
    elif not is_command_response and not last_tag and tag:
        # First question with a tag - this should increment
        session["answered_count"] += 1
        print(f"✅ First question with tag - incremented answered_count to {session['answered_count']}")
    elif not is_command_response and not tag:
        print(f"⚠️ No tag found in assistant reply")
        # Fallback: If no tag but we have a conversation, increment conservatively
        if len(history) > 0:
            # Only increment by 1 if we haven't incremented recently
            current_count = session.get("answered_count", 0)
            # Only increment if we have at least 2 messages (1 Q&A pair) and haven't incremented yet
            if len(history) >= 2 and current_count == 0:
                session["answered_count"] = 1
                print(f"🔄 Fallback: Incremented answered_count to 1 (first question without tag)")
            elif len(history) >= 4 and current_count == 1:
                session["answered_count"] = 2
                print(f"🔄 Fallback: Incremented answered_count to 2 (second question without tag)")
    else:
        if is_command_response:
            print(f"🔧 Command response - skipping answered_count increment")
        else:
            print(f"⚠️ No tag change or missing tags")

    if tag and not is_command_response:
        # Validate tag format and detect backwards progression
        previous_tag = session.get("asked_q", "")
        if previous_tag:
            try:
                prev_phase, prev_num = previous_tag.split(".")
                prev_num = int(prev_num)
                
                current_phase, current_num = tag.split(".")
                current_num = int(current_num)
                
                # Check if tag matches "Question X" in the message text
                question_num_match = re.search(r'Question\s+(\d+)(?:\s+of\s+\d+)?', assistant_reply)
                if question_num_match:
                    message_question_num = int(question_num_match.group(1))
                    if message_question_num != current_num:
                        print(f"⚠️ WARNING: Tag mismatch detected!")
                        print(f"  Message says: 'Question {message_question_num}'")
                        print(f"  Tag says: {tag} (question {current_num})")
                        print(f"  Using message question number as source of truth")
                        # Use the message question number
                        corrected_tag = f"{current_phase}.{message_question_num:02d}"
                        print(f"🔧 Correcting tag from {tag} to {corrected_tag}")
                        tag = corrected_tag
                        current_num = message_question_num
                
                # CRITICAL: Check for non-sequential progression (skipping questions)
                # BUT: Allow skipping if we're in missing questions mode (uploaded plan)
                business_context = session.get("business_context", {}) or {}
                if not isinstance(business_context, dict):
                    business_context = {}
                uploaded_plan_mode = business_context.get("uploaded_plan_mode", False)
                missing_questions = business_context.get("missing_questions", [])
                is_missing_question_jump = (uploaded_plan_mode and 
                                            isinstance(missing_questions, list) and 
                                            len(missing_questions) > 0 and
                                            current_num in missing_questions)
                
                if prev_phase == current_phase and current_num != prev_num + 1:
                    if current_num < prev_num:
                        print(f"⚠️ WARNING: Backwards question progression detected!")
                        print(f"  Previous: {previous_tag} (question {prev_num})")
                        print(f"  Current: {tag} (question {current_num})")
                        print(f"  This may indicate an AI model error in tag generation")
                        
                        # Fix backwards progression by incrementing the question number
                        corrected_num = prev_num + 1
                        corrected_tag = f"{current_phase}.{corrected_num:02d}"
                        print(f"🔧 Correcting tag from {tag} to {corrected_tag}")
                        tag = corrected_tag
                    elif current_num > prev_num + 1:
                        # Check if this is a valid jump to a missing question
                        if is_missing_question_jump:
                            print(f"✅ ALLOWED: Jumping to missing question Q{current_num}")
                            print(f"  Previous: {previous_tag} (question {prev_num})")
                            print(f"  Current: {tag} (question {current_num})")
                            print(f"  Missing questions: {sorted(missing_questions)}")
                            print(f"  This is valid - user uploaded plan and we're asking missing questions")
                        else:
                            print(f"❌ ERROR: Question skipping detected!")
                            print(f"  Previous: {previous_tag} (question {prev_num})")
                            print(f"  Current: {tag} (question {current_num})")
                            print(f"  Skipped questions: {list(range(prev_num + 1, current_num))}")
                            print(f"  🔧 FORCING sequential progression - correcting to {prev_num + 1}")
                            
                            # Force sequential progression - don't allow skipping (unless missing questions mode)
                            corrected_num = prev_num + 1
                            corrected_tag = f"{current_phase}.{corrected_num:02d}"
                            print(f"🔧 Correcting tag from {tag} to {corrected_tag}")
                            tag = corrected_tag
                            current_num = corrected_num
                            
                            # Also correct the tag in the reply content
                            assistant_reply = re.sub(
                                r'\[\[Q:[A-Z_]+\.\d+\]\]',
                                f'[[Q:{corrected_tag}]]',
                                assistant_reply,
                                count=1
                            )
                            print(f"🔧 Corrected tag in reply content to {corrected_tag}")
            except (ValueError, IndexError) as e:
                print(f"⚠️ Error parsing tag format: {e}")
        
        # Only update session if tag is valid and sequential
        session["asked_q"] = tag
        session["current_phase"] = tag.split(".")[0]
        print(f"📝 Updated session: asked_q={tag}, current_phase={tag.split('.')[0]}")
        
        # Auto-transition to roadmap after business plan completion
        # Only transition when we've completed all business plan questions (45 total)
        if tag.startswith("BUSINESS_PLAN."):
            try:
                question_num = int(tag.split(".")[1])
                if question_num > 45:
                    session["asked_q"] = "ROADMAP.01"
                    session["current_phase"] = "ROADMAP"
                    print(f"🔄 Auto-transitioned to ROADMAP after completing BUSINESS_PLAN question {question_num}")
            except (ValueError, IndexError):
                print(f"⚠️ Error parsing question number from tag: {tag}")
                # Don't transition if we can't parse the question number
    else:
        # If no tag found or command response, try to maintain current phase or set default
        if not session.get("current_phase"):
            session["current_phase"] = "KYC"
            print(f"📝 Set default phase to KYC")
        
        if is_command_response:
            print(f"🔧 Command response - maintaining current session state without tag updates")

    # Calculate progress based on current phase and CURRENT TAG (not answered_count)
    # CRITICAL: Use asked_q as the source of truth for what question we're on
    current_phase = session["current_phase"]
    answered_count = session["answered_count"]
    current_tag = session.get("asked_q")
    
    print(f"📈 Progress Calculation Input:")
    print(f"  - current_phase: {current_phase}")
    print(f"  - answered_count: {answered_count}")
    print(f"  - current_tag (asked_q): {current_tag}")
    print(f"  - Parsed tag from reply: {tag}")
    print(f"  - session data: {session}")
    
    # Calculate phase-specific progress for phase indicator
    phase_progress = calculate_phase_progress(current_phase, answered_count, current_tag)
    print(f"📊 Phase Progress Output: {phase_progress}")
    
    # For KYC and Business Plan phases, also calculate combined progress (Overall Progress)
    if current_phase in ["KYC", "BUSINESS_PLAN"]:
        combined_progress = calculate_combined_progress(current_phase, answered_count, current_tag)
        print(f"📊 Combined Progress Output (for Overall Progress): {combined_progress}")
        # Add combined progress info to phase_progress for frontend
        phase_progress["overall_progress"] = {
            "answered": combined_progress["answered"],
            "total": combined_progress["total"],
            "percent": combined_progress["percent"]
        }
    
    print(f"📊 Final Progress Data Sent to Frontend: {phase_progress}")
    
    # Update session in DB (without phase_progress since it's calculated on the fly)
    await patch_session(session_id, {
        "asked_q": session["asked_q"],
        "answered_count": session["answered_count"],
        "current_phase": session["current_phase"]
    })

    # Extract question number from tag before removing it
    question_number = None
    if tag and "." in tag:
        try:
            question_number = int(tag.split(".")[1])
        except (ValueError, IndexError):
            question_number = None
    
    # Clean response
    display_reply = re.sub(r'Question \d+ of \d+ \(\d+%\):', '', assistant_reply, flags=re.IGNORECASE)
    display_reply = re.sub(r'\[\[Q:[A-Z_]+\.\d{2}]]', '', display_reply)
    
    # Clean up excessive spacing for Angel introduction text
    if 'welcome to founderport' in display_reply.lower():
        # Reduce excessive line breaks throughout the entire text
        display_reply = re.sub(r'\n{4,}', '\n\n', display_reply)  # Reduce 4+ newlines to 2
        display_reply = re.sub(r'\n{3}', '\n\n', display_reply)  # Reduce 3 newlines to 2
        # Fix spacing around journey question
        display_reply = re.sub(r'\n\s*\n\s*Are you ready to begin your journey\?\s*\n\s*\n', '\n\nAre you ready to begin your journey?\n\n', display_reply)
        # Fix spacing around questionnaire intro
        display_reply = re.sub(r'\n\s*\n\s*Let\'s start with the Getting to Know You questionnaire', '\n\nLet\'s start with the Getting to Know You questionnaire', display_reply)
        # Final cleanup - ensure no more than 2 consecutive newlines anywhere
        display_reply = re.sub(r'\n{3,}', '\n\n', display_reply)

    # Return progress information
    progress_info = phase_progress

    return {
        "success": True,
        "message": "Angel chat processed successfully",
        "result": {
            "reply": display_reply.strip(),
            "progress": progress_info,
            "session_id": session_id,
            "web_search_status": web_search_status,
            "immediate_response": immediate_response,
            "show_accept_modify": show_accept_modify,
            "question_number": question_number
        }
    }

def clean_reply_for_display(reply):
    """Clean reply by removing progress indicators and tags"""
    # Remove progress indicators
    reply = re.sub(r'Question \d+ of \d+ \(\d+%\):', '', reply, flags=re.IGNORECASE)
    
    # Remove machine tags
    reply = re.sub(r'\[\[Q:[A-Z_]+\.\d{2}]]\s*', '', reply)
    
    # Remove extra whitespace
    reply = re.sub(r'\n\s*\n', '\n\n', reply)
    
    return reply.strip()

def get_phase_display_name(phase):
    """Get user-friendly phase names"""
    phase_names = {
        "KYC": "Getting to Know You",
        "BUSINESS_PLAN": "Business Planning", 
        "ROADMAP": "Creating Your Roadmap",
        "IMPLEMENTATION": "Implementation & Launch"
    }
    return phase_names.get(phase, phase)

async def patch_session_context_from_response(session_id, response_content, tag, session):
    """Extract and store key information from user responses"""
    
    # Skip extraction if this is a command word (Accept, Modify, Draft, etc.)
    command_words = ["accept", "modify", "draft", "support", "scrapping", "scraping", "draft more", "ok", "okay", "yes", "no"]
    response_lower = response_content.strip().lower()
    
    if response_lower in command_words:
        print(f"🔧 Skipping session context extraction for command word: {response_content}")
        return
    
    # Skip if response is too long (likely from Support/Draft commands)
    if len(response_content) > 500:
        print(f"🔧 Skipping session context extraction for long response ({len(response_content)} chars)")
        return
    
    # Extract key information based on KYC question
    updates = {}
    
    if tag == "KYC.01":  # Name
        updates["user_name"] = response_content.strip()
    elif tag == "KYC.04":  # Work situation  
        updates["employment_status"] = response_content.strip()
    elif tag == "KYC.05":  # Business idea
        updates["has_business_idea"] = "yes" in response_content.lower()
        if updates["has_business_idea"]:
            updates["business_idea_brief"] = response_content.strip()
    elif tag == "KYC.08":  # Business type
        updates["business_type"] = response_content.strip()
    elif tag == "KYC.09":  # Motivation
        updates["motivation"] = response_content.strip()
    elif tag == "KYC.10":  # Business location
        updates["location"] = response_content.strip()
    elif tag == "KYC.11":  # Business offering location
        updates["offering_location"] = response_content.strip()
    elif tag == "KYC.12":  # Industry (renumbered from KYC.11)
        updates["industry"] = response_content.strip()
    elif tag == "KYC.07":  # Skills comfort level
        updates["skills_assessment"] = response_content.strip()
        
    # Update session with extracted information
    if updates:
        print(f"📝 Extracting session context: {list(updates.keys())}")
        await patch_session(session_id, user_id, updates)
        session.update(updates)

@router.post("/sessions/{session_id}/command")
async def handle_command(session_id: str, request: Request, payload: dict):
    """Handle Accept/Modify commands for Draft and Scrapping responses"""
    
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    command = payload.get("command")  # "accept" or "modify"
    draft_content = payload.get("draft_content")
    modification_feedback = payload.get("feedback", "")

    if command == "accept":
        # Save the draft as the user's answer
        await save_chat_message(session_id, user_id, "user", draft_content)
        
        # Move to next question
        current_tag = session.get("asked_q")
        if current_tag:
            # Increment question number
            phase, num = current_tag.split(".")
            next_num = str(int(num) + 1).zfill(2)
            next_tag = f"{phase}.{next_num}"
            
            session["asked_q"] = next_tag
            session["answered_count"] += 1
            
            await patch_session(session_id, {
                "asked_q": session["asked_q"],
                "answered_count": session["answered_count"]
            })
        
        return {
            "success": True,
            "message": "Answer accepted, moving to next question",
            "action": "next_question"
        }
    
    elif command == "modify":
        # Process modification request
        history = await fetch_chat_history(session_id)
        
        modify_prompt = f"The user wants to modify this response based on their feedback:\n\nOriginal: {draft_content}\n\nFeedback: {modification_feedback}\n\nPlease provide an improved version."
        
        session_context = {
            "current_phase": session.get("current_phase", "KYC"),
            "industry": session.get("industry"),
            "location": session.get("location")
        }
        
        improved_response = await get_angel_reply(
            {"role": "user", "content": modify_prompt},
            history,
            session_context
        )
        
        # Extract the reply content from the response object
        improved_reply = improved_response.get("reply", improved_response) if isinstance(improved_response, dict) else improved_response
        
        return {
            "success": True,
            "message": "Here's your modified response",
            "result": {
                "improved_response": improved_reply,
                "show_accept_modify": True
            }
        }

@router.post("/sessions/{session_id}/go-back")
async def go_back_to_previous_question(session_id: str, request: Request):
    """Handle going back to the previous question"""
    
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    history = await fetch_chat_history(session_id)
    
    if not history or len(history) < 2:
        return {
            "success": False,
            "message": "Cannot go back - no previous question available"
        }
    
    # Get current phase and question
    current_tag = session.get("asked_q", "")
    current_phase = session.get("current_phase", "KYC")
    answered_count = session.get("answered_count", 0)
    
    # Parse current question number
    if current_tag:
        try:
            parts = current_tag.split(".")
            if len(parts) == 2:
                phase_prefix = parts[0]
                current_q_num = int(parts[1])
                
                # Calculate previous question number/phase
                previous_q_num = current_q_num - 1
                previous_phase = phase_prefix

                if previous_q_num < 1 and phase_prefix in PHASE_SEQUENCE:
                    current_index = PHASE_SEQUENCE.index(phase_prefix)
                    for idx in range(current_index - 1, -1, -1):
                        candidate_phase = PHASE_SEQUENCE[idx]
                        total_questions = TOTALS_BY_PHASE.get(candidate_phase)
                        if total_questions and total_questions > 0:
                            previous_phase = candidate_phase
                            previous_q_num = total_questions
                            break

                if previous_q_num < 1:
                    return {
                        "success": False,
                        "message": "Already at the first question"
                    }
                
                # Create previous question tag
                previous_tag = f"{previous_phase}.{previous_q_num:02d}"

                # Remove the current question and any responses after the previous question
                history_response = (
                    supabase
                    .from_("chat_history")
                    .select("id, role, content")
                    .eq("session_id", session_id)
                    .order("created_at")
                    .execute()
                )
                history_records = history_response.data or []

                # Find the LAST occurrence of the previous question BEFORE the current question
                # This is important because going back to Q1 means we want the intro Q1, not a later Q1
                target_index = None
                previous_tag_marker = f"[[Q:{previous_tag}]]"
                current_tag_marker = f"[[Q:{current_tag}]]" if current_tag else None
                
                print(f"🔍 Looking for previous question tag: {previous_tag_marker}")
                print(f"🔍 Current question tag: {current_tag_marker}")
                print(f"🔍 History has {len(history_records)} records")
                
                # Find the position of the current question first (if it exists)
                current_question_index = None
                if current_tag_marker:
                    for idx in range(len(history_records) - 1, -1, -1):
                        record = history_records[idx]
                        if record.get("role") == "assistant" and current_tag_marker in (record.get("content") or ""):
                            current_question_index = idx
                            print(f"🔍 Found current question at index {idx}")
                            break
                
                # Now find the last occurrence of previous question BEFORE the current question
                search_end = current_question_index if current_question_index is not None else len(history_records)
                
                for idx in range(search_end - 1, -1, -1):
                    record = history_records[idx]
                    content = record.get("content") or ""
                    if record.get("role") == "assistant" and previous_tag_marker in content:
                        target_index = idx
                        print(f"✅ Found previous question at index {idx} (before current at {current_question_index})")
                        break
                
                if target_index is None:
                    print(f"⚠️ Could not find previous question tag {previous_tag_marker} in history before index {search_end}")
                    # Debug: Print all assistant messages with question tags
                    for idx, record in enumerate(history_records[:search_end]):
                        if record.get("role") == "assistant":
                            content = record.get("content", "")
                            if "[[Q:" in content:
                                tag_match = content.find("[[Q:")
                                tag_snippet = content[tag_match:tag_match+15] if tag_match >= 0 else "N/A"
                                print(f"  Record {idx}: {tag_snippet}")

                ids_to_remove = []

                if target_index is not None:
                    # Remove the user's answer to the previous question AND everything after
                    # This allows the user to re-answer the previous question
                    # target_index = assistant message with previous question
                    # target_index + 1 = user's answer to previous question (if exists)
                    # target_index + 2 onwards = everything after
                    
                    # Start from target_index + 1 to include the user's answer to the previous question
                    ids_to_remove = [
                        rec["id"]
                        for rec in history_records[target_index + 1:]
                    ]
                    print(f"🔍 Found previous question at index {target_index}, will delete {len(ids_to_remove)} records after it")
                else:
                    # Fallback: remove the latest assistant question and the following user response
                    print(f"⚠️ Could not find previous question tag {previous_tag_marker} in history, using fallback")
                    latest_assistant_index = None
                    for idx in range(len(history_records) - 1, -1, -1):
                        record = history_records[idx]
                        if record.get("role") == "assistant" and "[[Q:" in (record.get("content") or ""):
                            latest_assistant_index = idx
                            break

                    if latest_assistant_index is not None:
                        # Delete the latest question and its answer
                        ids_to_remove.append(history_records[latest_assistant_index]["id"])
                        # Remove the immediate next user message (their answer to that question) if it exists
                        if latest_assistant_index + 1 < len(history_records):
                            next_record = history_records[latest_assistant_index + 1]
                            if next_record.get("role") == "user":
                                ids_to_remove.append(next_record["id"])
                        print(f"🔍 Fallback: Found latest question at index {latest_assistant_index}, will delete {len(ids_to_remove)} records")

                if ids_to_remove:
                    try:
                        print(f"🗑️ Attempting to delete {len(ids_to_remove)} records")
                        print(f"🗑️ Record IDs to delete: {ids_to_remove}")
                        
                        # Try batch deletion first
                        try:
                            delete_response = supabase.from_("chat_history").delete().in_("id", ids_to_remove).execute()
                            deleted_data = delete_response.data or []
                            print(f"✅ Batch delete response: {len(deleted_data)} records returned")
                        except Exception as batch_error:
                            print(f"⚠️ Batch delete failed, trying individual deletes: {batch_error}")
                            deleted_data = []
                        
                        # If batch didn't work or didn't return data, delete individually
                        if not deleted_data:
                            print(f"🔄 Deleting {len(ids_to_remove)} records individually...")
                            for record_id in ids_to_remove:
                                try:
                                    individual_response = supabase.from_("chat_history").delete().eq("id", record_id).execute()
                                    if individual_response.data:
                                        deleted_data.extend(individual_response.data)
                                    print(f"  ✅ Deleted record {record_id}")
                                except Exception as individual_error:
                                    print(f"  ❌ Failed to delete record {record_id}: {individual_error}")
                        
                        deleted_count = len(deleted_data) if deleted_data else 0
                        print(f"✅ Deleted {deleted_count} out of {len(ids_to_remove)} records")
                        
                        # Wait a moment for database to commit
                        import asyncio
                        await asyncio.sleep(0.2)
                        
                        # Verify deletion by re-fetching history
                        try:
                            verify_response = (
                                supabase
                                .from_("chat_history")
                                .select("id")
                                .eq("session_id", session_id)
                                .in_("id", ids_to_remove)
                                .execute()
                            )
                            remaining_records = verify_response.data or []
                            remaining_ids = [rec["id"] for rec in remaining_records]
                            
                            if remaining_ids:
                                print(f"⚠️ WARNING: {len(remaining_ids)} records still exist after deletion!")
                                print(f"⚠️ Remaining IDs: {remaining_ids}")
                                # Final attempt: delete remaining records one by one
                                for record_id in remaining_ids:
                                    try:
                                        final_response = supabase.from_("chat_history").delete().eq("id", record_id).execute()
                                        print(f"  🔄 Final attempt deleted {record_id}: {final_response.data is not None}")
                                    except Exception as final_error:
                                        print(f"  ❌ Final attempt failed for {record_id}: {final_error}")
                            else:
                                print(f"✅ VERIFICATION PASSED: All {len(ids_to_remove)} records successfully deleted")
                        except Exception as verify_error:
                            print(f"⚠️ Could not verify deletion: {verify_error}")
                            
                    except Exception as delete_error:
                        print(f"❌ CRITICAL ERROR deleting chat history records: {delete_error}")
                        import traceback
                        traceback.print_exc()
                        # Continue anyway - the session update will still happen
                else:
                    print(f"⚠️ No records to delete - target_index: {target_index}, history length: {len(history_records)}")

                # Update session to previous question
                if previous_phase == phase_prefix:
                    new_answered_count = max(0, answered_count - 1)
                else:
                    new_answered_count = max(
                        0, TOTALS_BY_PHASE.get(previous_phase, 1) - 1
                    )

                updates = {
                    "asked_q": previous_tag,
                    "answered_count": new_answered_count,
                    "current_phase": previous_phase
                }
                
                await patch_session(session_id, user_id, updates)
                session.update(updates)
                
                # Re-fetch updated session
                updated_session = await get_session(session_id, user_id)
                
                # Generate the previous question
                client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                
                question_prompt = f"""
                The user wants to go back to the previous question.
                Please display question {previous_tag} again.
                Use the proper format with the [[Q:{previous_tag}]] tag.
                """
                
                # Try to reuse the previously stored assistant question after trimming history
                refreshed_history = await fetch_chat_history(session_id)
                reply = None
                reply_from_history = False
                if refreshed_history:
                    for item in reversed(refreshed_history):
                        if item.get("role") == "assistant":
                            content = item.get("content") or ""
                            if "[[Q:" in content:
                                reply = content
                                reply_from_history = True
                                break

                # If we could not find the previous question (edge case), regenerate it
                if not reply:
                    response = await client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": ANGEL_SYSTEM_PROMPT},
                            {"role": "user", "content": question_prompt}
                        ],
                        temperature=0.7,
                        max_tokens=500
                    )
                    reply = response.choices[0].message.content
                    reply_from_history = False
                
                reply = enforce_question_tag(reply, previous_tag)

                if not reply_from_history:
                    try:
                        await save_chat_message(session_id, user_id, "assistant", reply)
                    except Exception as save_error:
                        print(f"Warning: failed to save regenerated go-back reply: {save_error}")
                
                # Calculate progress
                current_phase = updated_session.get("current_phase", "KYC")
                answered_count = updated_session.get("answered_count", 0)
                current_tag = updated_session.get("asked_q", "")
                
                phase_progress = calculate_phase_progress(current_phase, answered_count, current_tag)
                combined_progress = calculate_combined_progress(current_phase, answered_count, current_tag)
                
                return {
                    "success": True,
                    "message": "Returned to previous question",
                    "result": {
                        "reply": reply,
                        "progress": {
                            **phase_progress,
                            "overall_progress": combined_progress
                        }
                    }
                }
                
        except (ValueError, IndexError) as e:
            print(f"Error parsing question tag: {e}")
    
    return {
        "success": False,
        "message": "Unable to go back - invalid session state"
    }

@router.get("/sessions/{session_id}/artifacts/{artifact_type}")
async def get_artifact(session_id: str, artifact_type: str, request: Request):
    """Retrieve generated artifacts like business plans and roadmaps"""
    
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    
    try:
        artifact = await fetch_artifact(session_id, artifact_type)
        if not artifact:
            return {"success": False, "message": "Artifact not found"}
            
        return {
            "success": True,
            "result": {
                "content": artifact["content"],
                "created_at": artifact["created_at"],
                "type": artifact_type
            }
        }
    except Exception as e:
        return {"success": False, "message": f"Error retrieving artifact: {str(e)}"}

@router.post("/sessions/{session_id}/navigate")
async def navigate_to_question(session_id: str, request: Request, payload: dict):
    """Allow navigation back to previous questions for modifications"""
    
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    target_tag = payload.get("target_tag")  # e.g., "KYC.05"
    
    if not target_tag:
        return {"success": False, "message": "Target question tag required"}
    
    # Validate target tag format
    if not re.match(r'^(KYC|BUSINESS_PLAN|ROADMAP|IMPLEMENTATION)\.\d{2}$', target_tag):
        return {"success": False, "message": "Invalid question tag format"}
    
    # Update session to target question
    session["asked_q"] = target_tag
    session["current_phase"] = target_tag.split(".")[0]
    
    await patch_session(session_id, {
        "asked_q": session["asked_q"],
        "current_phase": session["current_phase"]
    })
    
    # Get the question text for the target tag
    history = await fetch_chat_history(session_id)
    
    # Generate response for the target question
    navigation_prompt = f"The user wants to revisit and potentially modify their answer to question {target_tag}. Please re-present this question and their previous answer if available."
    
    session_context = {
        "current_phase": session["current_phase"],
        "industry": session.get("industry"),
        "location": session.get("location")
    }
    
    question_response = await get_angel_reply(
        {"role": "user", "content": navigation_prompt},
        history,
        session_context
    )
    
    # Extract the reply content from the response object
    question_reply = question_response.get("reply", question_response) if isinstance(question_response, dict) else question_response
    
    return {
        "success": True,
        "message": "Navigated to previous question",
        "result": {
            "question": clean_reply_for_display(question_reply),
            "current_tag": target_tag,
            "phase": session["current_phase"]
        }
    }

# Database helper functions for artifacts and enhanced session management

async def save_artifact(session_id: str, artifact_type: str, content: str):
    """Save generated artifacts to database"""
    # Implementation depends on your database structure
    # This is a placeholder for the database operation
    pass

async def fetch_artifact(session_id: str, artifact_type: str):
    """Fetch artifact from database"""
    # Implementation depends on your database structure
    # This is a placeholder for the database operation
    pass

# TOTALS_BY_PHASE is now defined in utils/progress.py

@router.post("/sessions/{session_id}/generate-plan")
async def generate_business_plan(request: Request, session_id: str):
    history = await fetch_chat_history(session_id)
    history_trimmed = smart_trim_history(history)  
    result = await generate_full_business_plan(history_trimmed) 
    return {
        "success": True,
        "message": "Business plan generated successfully",
        "result": result,
    }

@router.post("/sessions/{session_id}/generate-business-plan-artifact")
async def generate_business_plan_artifact_endpoint(request: Request, session_id: str):
    """
    Generate business plan artifact ON-DEMAND when user clicks 'View Full Business Plan'
    This is the proper architecture - generate only when needed, not in background
    """
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    
    # Check if artifact already exists
    existing_artifact = session.get("business_plan_artifact")
    if existing_artifact:
        # Validate it's in the correct format
        has_new_format = "## Scene 1" in existing_artifact and "## Scene 8" in existing_artifact
        if has_new_format:
            print(f"✅ Using existing artifact (already generated)")
            return {
                "success": True,
                "result": {
                    "business_plan_artifact": existing_artifact,
                    "generated_at": session.get("business_plan_generated_at"),
                    "cached": True
                }
            }
    
    try:
        print(f"📄 Generating business plan artifact on-demand for session {session_id}")
        
        # Fetch conversation history
        history = await fetch_chat_history(session_id)
        
        # Generate artifact synchronously (user waits, but gets reliable result)
        artifact = await generate_business_plan_artifact(session, history)
        
        # Save to database
        await patch_session(session_id, {
            "business_plan_artifact": artifact,
            "business_plan_generated_at": datetime.now().isoformat()
        })
        
        print(f"✅ Business plan artifact generated: {len(artifact)} characters")
        
        return {
            "success": True,
            "result": {
                "business_plan_artifact": artifact,
                "generated_at": datetime.now().isoformat(),
                "cached": False
            }
        }
    except Exception as e:
        print(f"❌ Error generating artifact: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to generate business plan: {str(e)}"
        }

@router.get("/sessions/{session_id}/business-plan-summary")
async def get_business_plan_summary(request: Request, session_id: str):
    """Generate comprehensive business plan summary for Plan to Roadmap Transition"""
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    
    history = await fetch_chat_history(session_id)
    
    # Check if existing artifact is in old format and regenerate if needed
    existing_artifact = session.get("business_plan_artifact", "")
    if existing_artifact:
        # Check if it's in the old format (has traditional sections but no Scene 1-8)
        has_old_format = (
            ("## Executive Summary" in existing_artifact or 
             "Executive Summary" in existing_artifact) and 
            "## Scene 1" not in existing_artifact
        )
        has_new_format = "## Scene 1" in existing_artifact and "## Scene 8" in existing_artifact
        
        if has_old_format and not has_new_format:
            print(f"🔄 Existing artifact is in old format - regenerating in 8-scene table format...")
            # Regenerate artifact in new format
            from services.angel_service import generate_business_plan_artifact
            new_artifact = await generate_business_plan_artifact(session, history)
            
            # Validate the new artifact is actually in the correct format
            new_has_scene_1 = "## Scene 1" in new_artifact
            new_has_scene_8 = "## Scene 8" in new_artifact
            new_scene_count = new_artifact.count("## Scene ")
            new_has_old_format = ("## Executive Summary" in new_artifact or 
                                 ("Executive Summary" in new_artifact and "## Scene 1" not in new_artifact))
            
            print(f"🔍 Validation after regeneration: scene_count={new_scene_count}, has_scene_1={new_has_scene_1}, has_scene_8={new_has_scene_8}, has_old_format={new_has_old_format}")
            print(f"🔍 First 500 chars: {new_artifact[:500]}")
            
            # If still in old format, try one more time with maximum strictness
            if new_has_old_format or not new_has_scene_1 or not new_has_scene_8 or new_scene_count != 8:
                print(f"⚠️ Regenerated artifact still in old format - forcing one more regeneration with maximum strictness...")
                print(f"   Current artifact starts with: {new_artifact[:200]}")
                # Force regeneration by clearing the artifact first
                try:
                    new_artifact = await generate_business_plan_artifact(session, history)
                except Exception as e:
                    print(f"❌ Error during regeneration: {e}")
                    # If regeneration fails, return error instead of old format
                    raise Exception(f"Failed to generate business plan in new format. Old format is no longer supported. Error: {str(e)}")
                
                # Final validation
                final_has_scene_1 = "## Scene 1" in new_artifact
                final_has_scene_8 = "## Scene 8" in new_artifact
                final_scene_count = new_artifact.count("## Scene ")
                final_has_old_format = ("## Executive Summary" in new_artifact or 
                                       ("Executive Summary" in new_artifact and "## Scene 1" not in new_artifact))
                
                if final_has_old_format or not final_has_scene_1 or not final_has_scene_8 or final_scene_count != 8:
                    print(f"❌ ERROR: After multiple attempts, artifact still not in correct format!")
                    print(f"   This is a critical issue - the AI is not following the format instructions.")
                else:
                    print(f"✅ Second regeneration successful - artifact now in correct format")
            
            session["business_plan_artifact"] = new_artifact
            await patch_session(session_id, {"business_plan_artifact": new_artifact})
            print(f"✅ Regenerated artifact saved to database")
    
    # Don't trim history - we need the full list of dicts for Q&A extraction
    # The extraction function will handle trimming internally if needed
    
    try:
        # Pass session data and full untrimmed history to extract actual business information
        result = await generate_comprehensive_business_plan_summary(history, session)
        return {
            "success": True,
            "message": "Business plan summary generated successfully",
            "result": result
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error generating business plan summary: {str(e)}"
        }

@router.get("/sessions/{session_id}/roadmap-plan")
async def generate_roadmap_plan(session_id: str, request: Request):
    """Get roadmap plan - returns Founderport-style roadmap with 8 stages in table format"""
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    history = await fetch_chat_history(session_id)
    history_trimmed = smart_trim_history(history)
    
    # Check if roadmap exists in session and is in new format (has "Stage" and tables)
    roadmap_data = session.get("roadmap_data", {})
    existing_content = ""
    
    if roadmap_data:
        if isinstance(roadmap_data, dict):
            existing_content = roadmap_data.get("content", "") or roadmap_data.get("roadmap_content", "")
        elif isinstance(roadmap_data, str):
            existing_content = roadmap_data
    
    # Check if existing roadmap is in new format (has "Stage" and table format)
    is_new_format = False
    if existing_content:
        # Check for new format: Must have "Stage" keyword and the table header
        has_stage_keyword = "Stage" in existing_content and ("Stage 1" in existing_content or "Stage 2" in existing_content)
        has_table_format = "| Task | Description | Dependencies | Angel's Role | Status |" in existing_content
        has_stage_format = has_stage_keyword and has_table_format
        
        # Check for old format: Has "Phase" but not the table format
        is_old_format = "Phase" in existing_content and not has_table_format
        
        if has_stage_format:
            is_new_format = True
            print(f"✅ Found roadmap in new 8-stage format - returning existing roadmap")
        elif is_old_format:
            print(f"🔄 Found roadmap in old Phase format - regenerating with Founderport-style 8-stage format")
            is_new_format = False
        else:
            # Unclear format or missing tables, regenerate to be safe
            print(f"⚠️ Roadmap format unclear or missing tables - regenerating with Founderport-style 8-stage format")
            is_new_format = False
    
    # If we have new format roadmap, return it
    if is_new_format and existing_content:
        return {
            "success": True,
            "result": {
                "plan": existing_content,
                "generated_at": roadmap_data.get("metadata", {}).get("generated_at") if isinstance(roadmap_data, dict) else datetime.now().isoformat(),
                "research_conducted": True,
                "industry": session.get("business_context", {}).get("industry", "General Business") if isinstance(session.get("business_context"), dict) else "General Business",
                "location": session.get("business_context", {}).get("location", "United States") if isinstance(session.get("business_context"), dict) else "United States",
            }
        }
    
    # Otherwise, generate new Founderport-style roadmap with 8 stages
    from services.founderport_roadmap_service import generate_founderport_style_roadmap
    
    print(f"🗺️ Generating new Founderport-style roadmap with 8 stages for session {session_id}")
    # Pass the original history (list of dicts), not the trimmed string
    roadmap_content = await generate_founderport_style_roadmap(session, history)
    
    # Update session with new roadmap
    roadmap_payload = {
        "content": roadmap_content,
        "structured_steps": [],
        "tasks": [],
        "metadata": {
            "total_tasks": 0,
            "generated_at": datetime.now().isoformat()
        }
    }
    session["roadmap_data"] = roadmap_payload
    await patch_session(session_id, {
        "roadmap_data": roadmap_payload
    })
    
    return {
        "success": True,
        "result": {
            "plan": roadmap_content,
            "generated_at": datetime.now().isoformat(),
            "research_conducted": True,
            "industry": session.get("business_context", {}).get("industry", "General Business") if isinstance(session.get("business_context"), dict) else "General Business",
            "location": session.get("business_context", {}).get("location", "United States") if isinstance(session.get("business_context"), dict) else "United States",
        }
    }

@router.get("/sessions/{session_id}/enhanced-roadmap")
async def generate_enhanced_roadmap(session_id: str, request: Request):
    """Generate enhanced roadmap with comprehensive summary, execution advice, and motivational elements"""
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    
    history = await fetch_chat_history(session_id)
    history_trimmed = smart_trim_history(history)
    
    try:
        # Generate the enhanced roadmap with all new features
        roadmap_result = await generate_full_roadmap_plan(history_trimmed)
        
        # Add additional metadata for the enhanced UI
        enhanced_result = {
            **roadmap_result,
            "enhanced_features": {
                "research_foundation": True,
                "planning_champion_award": True,
                "execution_advice": True,
                "motivational_elements": True,
                "comprehensive_summary": True,
                "success_statistics": True
            },
            "ui_metadata": {
                "show_research_banner": True,
                "show_achievement_section": True,
                "show_execution_excellence": True,
                "show_success_stats": True,
                "enhanced_action_button": True
            }
        }
        
        return {
            "success": True,
            "message": "Enhanced roadmap generated successfully with comprehensive features",
            "result": enhanced_result
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error generating enhanced roadmap: {str(e)}"
        }

@router.post("/sessions/{session_id}/modify-roadmap")
async def modify_roadmap(session_id: str, request: Request):
    """Modify the roadmap content with user edits"""
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    
    try:
        payload = await request.json()
        modified_content = payload.get("modified_content", "")
        
        if not modified_content:
            return {
                "success": False,
                "message": "No modified content provided"
            }
        
        # Store the modified roadmap in the session
        session["modified_roadmap"] = modified_content
        session["roadmap_modified_at"] = datetime.now().isoformat()
        await patch_session(session_id, session)
        
        return {
            "success": True,
            "message": "Roadmap modified successfully",
            "modified_at": session["roadmap_modified_at"]
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error modifying roadmap: {str(e)}"
        }

@router.get("/sessions/{session_id}/implementation-insights")
async def get_implementation_insights(session_id: str, request: Request):
    """Generate RAG-powered implementation insights for the transition phase"""
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    
    try:
        # Extract business context from session
        business_context = session.get("business_context", {})
        industry = business_context.get("industry", "")
        location = business_context.get("location", "")
        business_type = business_context.get("business_type", "")
        
        # Generate implementation insights using RAG
        insights = await generate_implementation_insights(industry, location, business_type)
        
        return {
            "success": True,
            "insights": insights
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error generating implementation insights: {str(e)}"
        }

@router.get("/sessions/{session_id}/service-provider-preview")
async def get_service_provider_preview(session_id: str, request: Request):
    """Generate RAG-powered service provider preview for the transition phase"""
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    
    try:
        # Extract business context from session
        business_context = session.get("business_context", {})
        industry = business_context.get("industry", "")
        location = business_context.get("location", "")
        business_type = business_context.get("business_type", "")
        
        # Generate service provider preview using RAG
        providers = await generate_service_provider_preview(industry, location, business_type)
        
        return {
            "success": True,
            "providers": providers
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error generating service provider preview: {str(e)}"
        }

@router.get("/sessions/{session_id}/motivational-quote")
async def get_motivational_quote(session_id: str, request: Request):
    """Get a motivational quote for the transition phase"""
    try:
        # Generate or retrieve a motivational quote
        quote = await generate_motivational_quote()
        
        return {
            "success": True,
            "quote": quote
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error generating motivational quote: {str(e)}"
    }

@router.get("/sessions/{session_id}/chat/history")
async def get_phase_chat_history(
    session_id: str,
    request: Request,
    phase: str,
    limit: int = 15,
    offset: int = 0
):
    user_id = request.state.user["id"]

    messages = await fetch_phase_chat_history(session_id, phase, offset, limit)

    return {
        "success": True,
        "result": messages,
        "has_more": len(messages) == limit
    }

@router.post("/sessions/{session_id}/transition-decision")
async def handle_transition_decision(session_id: str, request: Request, payload: dict):
    """Handle Approve/Revisit decisions for Plan to Budget/Roadmap transitions"""
    from services.stripe_service import check_user_subscription_status
    
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    decision = payload.get("decision")  # "approve" or "revisit"
    transition_type = payload.get("transition_type", "plan_to_roadmap")  # "summary_to_budget" or "plan_to_budget" or "budget_to_roadmap" or "plan_to_roadmap"
    
    if decision == "approve":
        # Check if we're transitioning from summary to budget
        if transition_type == "summary_to_budget":
            # Summary is accepted, now transition to budget
            from services.angel_service import handle_budget_setup
            history = await fetch_chat_history(session_id)
            
            # Get business plan data from session
            business_plan_summary = session.get("business_plan_summary", "")
            business_plan_artifact = session.get("business_plan_artifact", None)
            
            # Generate budget setup message
            budget_response = await handle_budget_setup(session, history)
            
            # Prepare transition data
            transition_data = {
                "business_plan_summary": business_plan_summary,
                "business_plan_artifact": business_plan_artifact,
                "transition_type": "PLAN_TO_BUDGET",
                "estimated_expenses": budget_response.get("estimated_expenses", ""),
                "business_context": budget_response.get("business_context", {})
            }
            
            # Update session to budget transition phase
            await patch_session(session_id, {
                "current_phase": "PLAN_TO_BUDGET_TRANSITION"
            })
            
            session["current_phase"] = "PLAN_TO_BUDGET_TRANSITION"
            session["transition_data"] = transition_data
            
            return {
                "success": True,
                "message": "Summary accepted - transitioning to budget",
                "result": {
                    "action": "transition_to_budget",
                    "reply": budget_response["reply"],
                    "progress": {
                        "phase": "PLAN_TO_BUDGET_TRANSITION",
                        "answered": 45,
                        "total": 45,
                        "percent": 100
                    },
                    "transition_phase": "PLAN_TO_BUDGET",
                    "business_plan_summary": business_plan_summary,
                    "business_plan_artifact": business_plan_artifact,
                    "estimated_expenses": budget_response.get("estimated_expenses", ""),
                    "business_context": budget_response.get("business_context", {}),
                    "transition_data": transition_data
                }
            }
        
        # Check if we're transitioning from budget to roadmap
        elif transition_type == "budget_to_roadmap":
            # Budget is complete, now transition to roadmap
            # Check subscription status before allowing roadmap transition
            has_active_subscription = await check_user_subscription_status(user_id)
            if not has_active_subscription:
                return {
                    "success": False,
                    "message": "Subscription required to proceed to Roadmap phase. Please subscribe to continue.",
                    "requires_subscription": True
                }
            
            history = await fetch_chat_history(session_id)
            # Check if existing artifact is in old format (doesn't have Scene 1-8 structure)
            existing_artifact = session.get("business_plan_artifact", "")
            needs_regeneration = False
            
            if existing_artifact:
                # Check if it's in the old format (has traditional sections but no Scene 1-8)
                has_old_format = (
                    "## Executive Summary" in existing_artifact or 
                    "Executive Summary" in existing_artifact and "## Scene 1" not in existing_artifact
                )
                has_new_format = "## Scene 1" in existing_artifact and "## Scene 8" in existing_artifact
                
                if has_old_format and not has_new_format:
                    print(f"🔄 Existing artifact is in old format - regenerating in 8-scene table format...")
                    needs_regeneration = True
            
            if needs_regeneration or not existing_artifact:
                from services.angel_service import generate_business_plan_artifact
                business_plan_artifact = await generate_business_plan_artifact(session, history)
                session["business_plan_artifact"] = business_plan_artifact
            else:
                business_plan_artifact = existing_artifact
                print(f"✅ Using existing artifact (already in correct format)")
            session["business_plan_generated_at"] = datetime.now().isoformat()
            
            # Transition to Roadmap phase
            session["current_phase"] = "ROADMAP"
            session["asked_q"] = "ROADMAP.01"
            session["answered_count"] = 0
            
            await patch_session(session_id, {
                "current_phase": session["current_phase"],
                "asked_q": session["asked_q"],
                "answered_count": session["answered_count"],
                "business_plan_artifact": session["business_plan_artifact"],
                "business_plan_generated_at": session["business_plan_generated_at"]
            })
            
            # Generate roadmap
            from services.angel_service import handle_roadmap_generation
            roadmap_response = await handle_roadmap_generation(session, history)
            roadmap_payload = {
                "content": roadmap_response["roadmap_content"],
                "structured_steps": roadmap_response.get("structured_steps", []),
                "tasks": roadmap_response.get("implementation_tasks", []),
                "metadata": roadmap_response.get("roadmap_metadata", {})
            }
            session["roadmap_data"] = roadmap_payload
            
            await patch_session(session_id, {
                "roadmap_data": roadmap_payload
            })
            
            return {
                "success": True,
                "message": "Budget approved - transitioning to roadmap",
                "result": {
                    "action": "transition_to_roadmap",
                    "roadmap": roadmap_response["roadmap_content"],
                    "business_plan": business_plan_artifact,
                    "quote": roadmap_response.get("quote"),
                    "structured_steps": roadmap_response.get("structured_steps", []),
                    "implementation_tasks": roadmap_response.get("implementation_tasks", []),
                    "progress": {
                        "phase": "ROADMAP",
                        "answered": 0,
                        "total": 1,
                        "percent": 0
                    },
                    "transition_phase": roadmap_response["transition_phase"]
                }
            }
        
        # Original plan_to_roadmap transition (for backward compatibility)
        elif transition_type == "plan_to_roadmap":
            # Check subscription status before allowing roadmap transition
            has_active_subscription = await check_user_subscription_status(user_id)
            if not has_active_subscription:
                return {
                    "success": False,
                    "message": "Subscription required to proceed to Roadmap phase. Please subscribe to continue.",
                    "requires_subscription": True
                }
            history = await fetch_chat_history(session_id)
            # Check if existing artifact is in old format (doesn't have Scene 1-8 structure)
            existing_artifact = session.get("business_plan_artifact", "")
            needs_regeneration = False
            
            if existing_artifact:
                # Check if it's in the old format (has traditional sections but no Scene 1-8)
                has_old_format = (
                    "## Executive Summary" in existing_artifact or 
                    "Executive Summary" in existing_artifact and "## Scene 1" not in existing_artifact
                )
                has_new_format = "## Scene 1" in existing_artifact and "## Scene 8" in existing_artifact
                
                if has_old_format and not has_new_format:
                    print(f"🔄 Existing artifact is in old format - regenerating in 8-scene table format...")
                    needs_regeneration = True
            
            if needs_regeneration or not existing_artifact:
                from services.angel_service import generate_business_plan_artifact
                business_plan_artifact = await generate_business_plan_artifact(session, history)
                session["business_plan_artifact"] = business_plan_artifact
            else:
                business_plan_artifact = existing_artifact
                print(f"✅ Using existing artifact (already in correct format)")
            session["business_plan_generated_at"] = datetime.now().isoformat()
            
            # Transition to Roadmap phase
            session["current_phase"] = "ROADMAP"
            session["asked_q"] = "ROADMAP.01"
            session["answered_count"] = 0
            
            await patch_session(session_id, {
                "current_phase": session["current_phase"],
                "asked_q": session["asked_q"],
                "answered_count": session["answered_count"],
                "business_plan_artifact": session["business_plan_artifact"],
                "business_plan_generated_at": session["business_plan_generated_at"]
            })
            
            # Generate roadmap
            from services.angel_service import handle_roadmap_generation
            roadmap_response = await handle_roadmap_generation(session, history)
            roadmap_payload = {
                "content": roadmap_response["roadmap_content"],
                "structured_steps": roadmap_response.get("structured_steps", []),
                "tasks": roadmap_response.get("implementation_tasks", []),
                "metadata": roadmap_response.get("roadmap_metadata", {})
            }
            session["roadmap_data"] = roadmap_payload
            
            await patch_session(session_id, {
                "roadmap_data": roadmap_payload
            })
            
            return {
                "success": True,
                "message": "Plan approved - transitioning to roadmap",
                "result": {
                    "action": "transition_to_roadmap",
                    "roadmap": roadmap_response["roadmap_content"],
                    "business_plan": business_plan_artifact,
                    "quote": roadmap_response.get("quote"),
                    "structured_steps": roadmap_response.get("structured_steps", []),
                    "implementation_tasks": roadmap_response.get("implementation_tasks", []),
                    "progress": {
                        "phase": "ROADMAP",
                        "answered": 0,
                        "total": 1,
                        "percent": 0
                    },
                    "transition_phase": roadmap_response["transition_phase"]
                }
            }
        
        # Handle plan_to_budget transition (when user approves business plan)
        elif transition_type == "plan_to_budget":
            # Transition to Budget phase
            await patch_session(session_id, {
                "current_phase": "BUDGET"
            })
            session["current_phase"] = "BUDGET"
            
            return {
                "success": True,
                "message": "Plan approved - transitioning to budget",
                "result": {
                    "action": "transition_to_budget",
                    "progress": {
                        "phase": "BUDGET",
                        "answered": 0,
                        "total": 1,
                        "percent": 0
                    }
                }
            }
    
    elif decision == "revisit":
        # Return to Business Plan phase for modifications
        session["current_phase"] = "BUSINESS_PLAN"
        # Keep the current progress instead of resetting to 01
        # This allows user to continue from where they left off
        current_asked_q = session.get("asked_q", "BUSINESS_PLAN.45")
        if not current_asked_q.startswith("BUSINESS_PLAN."):
            current_asked_q = "BUSINESS_PLAN.45"
        
        # Calculate correct answered count from the tag
        answered_from_tag = 46  # Default to 46 if at end
        if current_asked_q and "." in current_asked_q:
            try:
                answered_from_tag = int(current_asked_q.split(".")[1])
            except (ValueError, IndexError):
                answered_from_tag = 46
        
        # Sync answered_count with the tag to fix any discrepancies
        session["answered_count"] = answered_from_tag
        
        await patch_session(session_id, {
            "current_phase": session["current_phase"],
            "asked_q": current_asked_q,
            "answered_count": answered_from_tag  # Sync this!
        })
        
        return {
            "success": True,
            "message": "Plan review mode activated",
            "result": {
                "action": "revisit_plan",
                "progress": {
                    "phase": "BUSINESS_PLAN",
                    "answered": answered_from_tag,  # Use tag-based calculation
                    "total": 45,
                    "percent": 100
                }
            }
        }
    
    else:
        return {
            "success": False,
            "message": "Invalid decision. Please choose 'approve' or 'revisit'"
        }

@router.post("/sessions/{session_id}/revisit-plan-with-areas")
async def revisit_plan_with_areas(session_id: str, request: Request, payload: dict):
    """Handle revisit with specific modification areas"""
    
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    modification_areas = payload.get("modification_areas", [])
    
    if not modification_areas:
        return {
            "success": False,
            "message": "No modification areas specified"
        }
    
    # Store modification areas in session for guidance
    session["modification_areas"] = modification_areas
    session["current_phase"] = "BUSINESS_PLAN"
    
    # Map modification areas to specific business plan sections
    area_to_section_mapping = {
        "business-overview": "BUSINESS_PLAN.01-05",
        "market-research": "BUSINESS_PLAN.06-12", 
        "financial-projections": "BUSINESS_PLAN.13-20",
        "operations": "BUSINESS_PLAN.21-28",
        "marketing-strategy": "BUSINESS_PLAN.29-35",
        "legal-compliance": "BUSINESS_PLAN.36-42"
    }
    
    # Determine starting point based on modification areas
    starting_sections = [area_to_section_mapping.get(area) for area in modification_areas if area in area_to_section_mapping]
    
    # Start from the earliest section that needs modification
    if starting_sections:
        earliest_section = min(starting_sections, key=lambda x: int(x.split('.')[1].split('-')[0]))
        session["asked_q"] = f"BUSINESS_PLAN.{earliest_section.split('.')[1].split('-')[0].zfill(2)}"
    else:
        session["asked_q"] = "BUSINESS_PLAN.01"
    
    await patch_session(session_id, {
        "current_phase": session["current_phase"],
        "asked_q": session["asked_q"],
        "modification_areas": modification_areas
    })
    
    # Generate guidance message for modifications
    modification_guidance = f"""Based on your selection, I'll guide you through modifying the following areas of your business plan:

{', '.join([area.replace('-', ' ').replace('_', ' ').title() for area in modification_areas])}

Let's start with the first area that needs attention. I'll provide specific guidance and questions to help you refine each section."""
    
    # Save guidance message to chat
    await save_chat_message(session_id, user_id, "assistant", modification_guidance)
    
    return {
        "success": True,
        "message": "Plan modification mode activated",
        "result": {
            "action": "revisit_plan_with_areas",
            "modification_areas": modification_areas,
            "guidance": modification_guidance,
            "progress": {
                "phase": "BUSINESS_PLAN",
                "answered": session.get("answered_count", 0),
                "total": 45,
                "percent": 0
            }
        }
        }

@router.post("/sessions/{session_id}/start-implementation")
async def start_implementation(session_id: str, request: Request):
    """Start Implementation phase - requires active subscription"""
    from services.stripe_service import check_user_subscription_status
    
    user_id = request.state.user["id"]
    
    # Check subscription status before allowing implementation start
    has_active_subscription = await check_user_subscription_status(user_id)
    if not has_active_subscription:
        return {
            "success": False,
            "message": "Subscription required to start Implementation phase. Please subscribe to continue.",
            "requires_subscription": True
        }
    """Handle transition from Roadmap to Implementation phase"""
    
    user_id = request.state.user["id"]
    session = await get_session(session_id, user_id)
    
    # Transition to Implementation phase
    session["current_phase"] = "IMPLEMENTATION"
    session["asked_q"] = "IMPLEMENTATION.01"
    session["answered_count"] = 0
    
    await patch_session(session_id, {
        "current_phase": session["current_phase"],
        "asked_q": session["asked_q"],
        "answered_count": session["answered_count"]
    })
    
    # Get the first implementation task
    from services.implementation_service import get_next_implementation_task
    first_task = await get_next_implementation_task(session, [])
    
    # Generate implementation transition message and first question
    implementation_prompt = "The user has approved their roadmap and wants to start the implementation phase. Please provide a motivational transition message and present the first implementation task/question."
    
    session_context = {
        "current_phase": "IMPLEMENTATION",
        "industry": session.get("industry"),
        "location": session.get("location")
    }
    
    implementation_response = await get_angel_reply(
        {"role": "user", "content": implementation_prompt},
        [],  # Empty history for implementation start
        session_context
    )
    
    # Extract the reply content from the response object
    reply_content = implementation_response.get("reply", implementation_response) if isinstance(implementation_response, dict) else implementation_response
    
    # Save the implementation transition message
    await save_chat_message(session_id, user_id, "assistant", reply_content)
    
    return {
        "success": True,
        "message": "Implementation phase started successfully",
        "result": {
            "action": "start_implementation",
            "reply": reply_content,
            "progress": {
                "phase": "IMPLEMENTATION",
                "answered": 0,
                "total": 10,
                "percent": 0
            },
            "first_task": first_task
        }
    }

@router.post("/sessions/{session_id}/roadmap-to-implementation-transition")
async def roadmap_to_implementation_transition(session_id: str, request: Request):
    """Handle transition from Roadmap to Implementation phase"""
    from services.stripe_service import check_user_subscription_status
    
    user_id = request.state.user["id"]
    
    # Check subscription status before allowing implementation transition
    has_active_subscription = await check_user_subscription_status(user_id)
    if not has_active_subscription:
        return {
            "success": False,
            "message": "Subscription required to proceed to Implementation phase. Please subscribe to continue.",
            "requires_subscription": True
        }
    
    session = await get_session(session_id, user_id)
    
    # CRITICAL: Update session phase to ROADMAP_TO_IMPLEMENTATION_TRANSITION in database
    session["current_phase"] = "ROADMAP_TO_IMPLEMENTATION_TRANSITION"
    await patch_session(session_id, {
        "current_phase": "ROADMAP_TO_IMPLEMENTATION_TRANSITION"
    })
    print(f"✅ Updated session {session_id} phase to ROADMAP_TO_IMPLEMENTATION_TRANSITION")
    
    # Generate transition message
    history = await fetch_chat_history(session_id)
    transition_response = await handle_roadmap_to_implementation_transition(session, history)
    
    return {
        "success": True,
        "message": "Roadmap to Implementation transition prepared",
        "result": {
            "action": "roadmap_to_implementation_transition",
            "reply": transition_response["reply"],
            "progress": {
                "phase": "ROADMAP_TO_IMPLEMENTATION_TRANSITION",
                "answered": 1,
                "total": 1,
                "percent": 100
            },
            "transition_phase": transition_response["transition_phase"]
        }
    }

@router.post("/sessions/{session_id}/upload-business-plan")
async def upload_business_plan(
    session_id: str,
    request: Request,
    file: UploadFile = File(...)
):
    """Upload and process a business plan document"""
    user_id = request.state.user["id"]
    
    # Validate file type
    allowed_types = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
    if file.content_type not in allowed_types:
        return {
            "success": False,
            "error": "Please upload a PDF, DOC, or DOCX file."
        }
    
    # Validate file size (max 10MB)
    if file.size > 10 * 1024 * 1024:
        return {
            "success": False,
            "error": "File size must be less than 10MB."
        }
    
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'pdf'
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Create a chat message about the uploaded document
        upload_message = f"📄 **Business Plan Document Uploaded**\n\n**File:** {file.filename}\n**Size:** {file.size} bytes\n**Type:** {file.content_type}\n**Uploaded:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nI've received your business plan document. I can help you:\n\n• **Analyze** the content and provide feedback\n• **Extract** key information for our business planning process\n• **Compare** it with our questionnaire responses\n• **Suggest** improvements or missing sections\n\nWould you like me to analyze this document and integrate it into our business planning process?"
        
        # Save the upload message to chat history
        await save_chat_message(session_id, "assistant", upload_message)
        
        return {
            "success": True,
            "message": "Business plan uploaded successfully",
            "filename": file.filename,
            "file_id": unique_filename,
            "chat_message": upload_message
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to upload file: {str(e)}"
        }
