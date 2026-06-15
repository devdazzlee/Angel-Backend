from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from middlewares.auth import verify_auth_token
from services.upload_plan_service import (
    process_uploaded_plan,
    extract_business_info_from_plan,
    analyze_plan_completeness,
    extract_per_question_answers,
    parse_canonical_business_plan_questions,
)
from services.chat_service import save_chat_message
from services.session_service import get_session, patch_session
from db.supabase import supabase
import os
import uuid
import tempfile
import json
import re
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

router = APIRouter()

@router.post("")
async def upload_business_plan(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(verify_auth_token)
):
    """
    Upload and process a business plan document (does NOT store in database)
    Simply extracts business info and returns it to frontend for session update
    Supports: PDF, DOCX, TXT files

    Endpoint: POST /upload-plan (router prefix + "" = /upload-plan).

    Important: the route path is "" (not "/") so the canonical URL is
    /upload-plan with NO trailing slash. The frontend posts to /upload-plan;
    a trailing-slash mismatch causes FastAPI to 307-redirect, and many
    deployment proxies (Vercel functions, IIS) drop the POST body across
    that redirect, which surfaces as "Method Not Allowed" to the user.
    """
    temp_file_path = None
    
    try:
        # Validate file type
        allowed_extensions = ['.pdf', '.docx', '.txt']
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Please upload: {', '.join(allowed_extensions)}"
            )
        
        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        file_content = await file.read()
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size is 10MB."
            )
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        # Process the uploaded plan
        processed_content = await process_uploaded_plan(temp_file_path, file_extension)

        # Single canonical extraction: per-question answers aligned to Angel's actual
        # 45 BUSINESS_PLAN questions. business_info summary and completeness analysis
        # are derived from this so the upload pipeline cannot drift from the prompt.
        per_question_answers = await extract_per_question_answers(processed_content)
        business_info = await extract_business_info_from_plan(processed_content, per_question_answers)
        analysis = await analyze_plan_completeness(processed_content, business_info, per_question_answers)

        # JSON keys must be strings; convert int keys for the wire format.
        per_question_answers_str_keys = {str(k): v for k, v in per_question_answers.items()}

        return JSONResponse(content={
            "success": True,
            "message": "Business plan processed and analyzed successfully!",
            "business_info": business_info,
            "per_question_answers": per_question_answers_str_keys,
            "analysis": analysis,
            "content_preview": processed_content[:500] + "..." if len(processed_content) > 500 else processed_content,
        })
                
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error uploading business plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process business plan: {str(e)}")
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass  # Ignore cleanup errors

@router.get("/importable-sources")
async def list_importable_plans(
    request: Request,
    current_user: dict = Depends(verify_auth_token),
):
    """
    Return the user's other ventures that have a completed Angel-generated
    business plan available to import. Excludes the current session if a
    `session_id` query param is provided.

    Response shape:
        { "success": true, "sources": [ { id, title, generated_at, ... } ] }
    """
    user_id = request.state.user["id"]
    current_session_id = request.query_params.get("session_id")

    try:
        query = (
            supabase
            .from_("chat_sessions")
            .select("id,title,business_plan_artifact,business_plan_generated_at,updated_at,business_context")
            .eq("user_id", user_id)
            .not_.is_("business_plan_artifact", "null")
            .order("business_plan_generated_at", desc=True)
        )
        if current_session_id:
            query = query.neq("id", current_session_id)
        result = query.execute()
    except Exception as e:
        print(f"Error listing importable plans: {e}")
        raise HTTPException(status_code=500, detail="Failed to list importable plans")

    sources: List[Dict[str, Any]] = []
    for row in result.data or []:
        artifact = row.get("business_plan_artifact") or ""
        if not artifact.strip():
            continue
        ctx = row.get("business_context") or {}
        if not isinstance(ctx, dict):
            ctx = {}
        sources.append({
            "id": row.get("id"),
            "title": row.get("title") or "Untitled venture",
            "business_name": ctx.get("business_name") or "",
            "industry": ctx.get("industry") or "",
            "generated_at": row.get("business_plan_generated_at") or row.get("updated_at"),
            "artifact_chars": len(artifact),
        })

    return JSONResponse(content={"success": True, "sources": sources})


@router.post("/from-session")
async def import_business_plan_from_session(
    request: Request,
    current_user: dict = Depends(verify_auth_token),
):
    """
    Import an Angel-generated business plan from one of the user's other
    sessions and run it through the same extraction pipeline as a TXT
    upload. Returns the exact same response shape as `POST /upload-plan`
    so the frontend's success handler is shared between paths.

    Request body: { "source_session_id": "<uuid>" }
    """
    user_id = request.state.user["id"]
    body = await request.json()
    source_session_id = body.get("source_session_id")
    if not source_session_id:
        raise HTTPException(status_code=400, detail="source_session_id is required")

    # Ownership is enforced by get_session via user_id.
    source_session = await get_session(source_session_id, user_id)
    artifact = (source_session.get("business_plan_artifact") or "").strip()
    if not artifact:
        raise HTTPException(
            status_code=404,
            detail="The selected venture does not have a completed business plan to import.",
        )

    per_question_answers = await extract_per_question_answers(artifact)
    business_info = await extract_business_info_from_plan(artifact, per_question_answers)
    analysis = await analyze_plan_completeness(artifact, business_info, per_question_answers)
    per_question_answers_str_keys = {str(k): v for k, v in per_question_answers.items()}

    return JSONResponse(content={
        "success": True,
        "message": f"Imported business plan from '{source_session.get('title') or 'venture'}'",
        "business_info": business_info,
        "per_question_answers": per_question_answers_str_keys,
        "analysis": analysis,
        "content_preview": artifact[:500] + ("..." if len(artifact) > 500 else ""),
        "source": {
            "session_id": source_session_id,
            "title": source_session.get("title"),
        },
    })


@router.post("/save-found-info")
async def save_found_info_to_history(
    request: Request,
    current_user: dict = Depends(verify_auth_token)
):
    """
    Persist canonical per-question answers extracted from an uploaded plan as
    chat history Q&A pairs, then put the session into uploaded-plan mode so Angel
    asks only the missing questions next.

    Request body:
        session_id (str, required)
        per_question_answers (dict[str -> str|null], required for v3 flow):
            keys "1".."45", values are the extracted answer or null. This is the
            single source of truth — every other field below is supplemental.
        business_info (dict, optional): legacy summary used to seed business_context
            so prompts that read business_name/industry/mission/etc. work right away.
    """
    user_id = request.state.user["id"] if hasattr(request.state, 'user') and request.state.user else None
    if not user_id:
        if isinstance(current_user, dict) and "id" in current_user:
            user_id = current_user["id"]
        else:
            raise HTTPException(status_code=401, detail="Authentication required")
    body = await request.json()
    session_id = body.get("session_id")
    business_info = body.get("business_info", {}) or {}
    raw_per_question = body.get("per_question_answers") or {}

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Verify session ownership; we re-fetch later after computing updates.
    await get_session(session_id, user_id)

    canonical_questions = parse_canonical_business_plan_questions()
    canonical_text_by_num = {n: t for n, t in canonical_questions}
    if not canonical_questions:
        raise HTTPException(
            status_code=500,
            detail="Internal error: failed to load canonical BUSINESS_PLAN questions",
        )

    # Normalize per-question answers (wire format uses string keys; coerce to int).
    per_question: Dict[int, Optional[str]] = {}
    for k, v in raw_per_question.items():
        try:
            num = int(k)
        except (TypeError, ValueError):
            continue
        if not (1 <= num <= 45):
            continue
        if v is None:
            per_question[num] = None
        elif isinstance(v, str):
            cleaned = v.strip()
            per_question[num] = cleaned if cleaned and cleaned.upper() not in {"NULL", "N/A", "NOT_FOUND"} else None
        else:
            try:
                per_question[num] = json.dumps(v, ensure_ascii=False)
            except Exception:
                per_question[num] = None

    # Default any unmapped canonical questions to None.
    for q_num, _ in canonical_questions:
        per_question.setdefault(q_num, None)

    # Build the dedup set as "questions that have a USER ANSWER in history",
    # not just "questions whose tag was asked". When Angel asks BP.01 and the
    # user uploads BEFORE typing an answer, the assistant message for BP.01
    # exists but no user reply follows it. The previous dedup treated that as
    # "already answered" and skipped Q1 from the upload — so the upload's
    # extracted Q2..Q45 got appended with newer timestamps and Q1 stayed
    # unanswered, producing the "Q2…Q45 then Q1 at the bottom" ordering.
    #
    # The correct rule: a question is "already answered" only if the next
    # non-empty user message after its assistant tag is a real user reply
    # (not the EMPTY sentinel, not a command word).
    from services.chat_service import fetch_chat_history
    existing_history = await fetch_chat_history(session_id)
    _COMMAND_WORDS = {"draft", "support", "scrapping", "scraping", "accept", "modify"}
    answered_question_numbers: set[int] = set()
    asked_but_unanswered: set[int] = set()
    pending_q_num: Optional[int] = None
    for record in existing_history:
        role = record.get("role")
        content = record.get("content", "") or ""
        if role == "assistant":
            tag_match = re.search(r"\[\[Q:BUSINESS_PLAN\.(\d+)\]\]", content)
            if tag_match:
                # A new question was asked. If there was a previous one without
                # an answer, it stays in asked_but_unanswered.
                if pending_q_num is not None:
                    asked_but_unanswered.add(pending_q_num)
                pending_q_num = int(tag_match.group(1))
        elif role == "user":
            if pending_q_num is None:
                continue
            answer = content.strip()
            if not answer or answer.upper() == "EMPTY" or answer.lower() in _COMMAND_WORDS:
                # Not a real answer to the pending question; keep waiting.
                continue
            answered_question_numbers.add(pending_q_num)
            pending_q_num = None
    if pending_q_num is not None:
        asked_but_unanswered.add(pending_q_num)
    print(f"📋 Already answered in history: {sorted(answered_question_numbers)}")
    print(f"📋 Asked but unanswered: {sorted(asked_but_unanswered)}")

    saved_count = 0
    qa_pairs_to_save: List[Dict[str, Any]] = []
    qa_answers_only_to_save: List[Dict[str, Any]] = []
    questions_that_failed_extraction: List[int] = []

    try:
        # Build the save plan from the canonical question list.
        # - Skip if a real user answer already exists for this Q.
        # - If the Q was asked but never answered, save just the user answer
        #   (no duplicate assistant question) so the existing assistant message
        #   gets paired with the upload's extracted answer.
        # - Otherwise, append a fresh [Q + A] pair.
        for q_num, q_text in canonical_questions:
            if q_num in answered_question_numbers:
                continue
            answer = per_question.get(q_num)
            if not (answer and len(answer.strip()) > 3):
                questions_that_failed_extraction.append(q_num)
                continue
            entry = {
                "question_num": q_num,
                "question_text": q_text,
                "answer": answer.strip(),
            }
            if q_num in asked_but_unanswered:
                qa_answers_only_to_save.append(entry)
            else:
                qa_pairs_to_save.append(entry)

        all_saved_qnums = sorted(
            {q["question_num"] for q in qa_answers_only_to_save}
            | {q["question_num"] for q in qa_pairs_to_save}
        )
        actual_found_question_numbers = all_saved_qnums
        print(
            f"📋 Will save {len(qa_answers_only_to_save)} answer-only entries (for already-asked Qs) "
            f"and {len(qa_pairs_to_save)} fresh Q&A pairs: {all_saved_qnums}"
        )
        print(f"📋 {len(questions_that_failed_extraction)} questions need to be asked: {questions_that_failed_extraction}")

        # First, complete any already-asked-but-unanswered questions by writing
        # just the user answer. Doing this BEFORE appending fresh pairs keeps
        # the chronological ordering as: [old Q1 question, NEW Q1 answer,
        # NEW Q2 Q&A, NEW Q3 Q&A, ...] so the chat reads top-to-bottom in
        # canonical order instead of "Q2…Q45 then Q1 at the bottom."
        for entry in sorted(qa_answers_only_to_save, key=lambda e: e["question_num"]):
            q_num = entry["question_num"]
            answer_text = entry["answer"]
            try:
                await save_chat_message(session_id, user_id, "user", answer_text)
                await asyncio.sleep(0.1)
                saved_count += 1
            except Exception as save_err:
                print(f"  ❌ Error saving answer for Q{q_num}: {save_err}")
                continue

        # Summary message ahead of the fresh Q&A pairs in chat history.
        if qa_pairs_to_save:
            questions_list = ", ".join([f"Q{q['question_num']}" for q in qa_pairs_to_save])
            summary_message = (
                "📄 **Business Plan Uploaded and Analyzed**\n\n"
                "I've extracted the following information from your uploaded business plan:\n\n"
                f"**Questions Found in Your Plan:** {questions_list}\n\n"
                f"**Total Questions Found:** {len(all_saved_qnums)}\n\n"
                "Your answers to these questions have been saved to the chat history below. "
                "I'll now ask you only the missing questions to complete your business plan."
            )
            await save_chat_message(session_id, user_id, "assistant", summary_message)
            await asyncio.sleep(0.1)

        # Persist fresh Q&A pairs in canonical order so timestamps stay sequential.
        for idx, qa_pair in enumerate(qa_pairs_to_save):
            q_num = qa_pair["question_num"]
            q_text = qa_pair["question_text"]
            answer_text = qa_pair["answer"]
            try:
                assistant_content = f"[[Q:BUSINESS_PLAN.{q_num:02d}]] {q_text}"
                await save_chat_message(session_id, user_id, "assistant", assistant_content)
                await asyncio.sleep(0.1)
                await save_chat_message(session_id, user_id, "user", answer_text)
                saved_count += 1
                if idx < len(qa_pairs_to_save) - 1:
                    await asyncio.sleep(0.1)
            except Exception as save_err:
                print(f"  ❌ Error saving Q{q_num}: {save_err}")
                continue

        # Compute new session state.
        session = await get_session(session_id, user_id)
        business_context = session.get("business_context", {}) or {}
        if not isinstance(business_context, dict):
            business_context = {}

        # Already-answered + answer-only completions + fresh pairs.
        # We use the union of canonical Qs that now have a user answer.
        completed_question_numbers = (
            answered_question_numbers
            | {q["question_num"] for q in qa_answers_only_to_save}
            | {q["question_num"] for q in qa_pairs_to_save}
        )
        new_answered_count = len([q for q in completed_question_numbers if 1 <= q <= 45])
        max_saved_question = max(all_saved_qnums) if all_saved_qnums else 0

        # Merge legacy summary into business_context so existing prompts read the
        # right values immediately (business_name, industry, mission, etc.).
        if isinstance(business_info, dict):
            from services.business_identity_extractor import (
                extract_business_name_from_user_answer,
                extract_industry_from_user_answer,
                extract_location_from_user_answer,
                is_valid_business_name,
                is_valid_industry_label,
                is_valid_location_label,
            )

            for key, value in business_info.items():
                if value in (None, "", "N/A"):
                    continue
                normalized_key = key.lower().replace(" ", "_").replace("-", "_")
                stored_value = value
                if normalized_key == "business_name" and isinstance(value, str):
                    stored_value = await extract_business_name_from_user_answer(value)
                    if not stored_value or not is_valid_business_name(stored_value):
                        continue
                elif normalized_key == "industry" and isinstance(value, str):
                    stored_value = await extract_industry_from_user_answer(value)
                    if not stored_value or not is_valid_industry_label(stored_value):
                        continue
                elif normalized_key == "location" and isinstance(value, str):
                    stored_value = await extract_location_from_user_answer(value)
                    if not stored_value or not is_valid_location_label(stored_value):
                        continue
                business_context[normalized_key] = stored_value
                if normalized_key != key:
                    business_context[key] = stored_value

        missing_questions = sorted(
            q for q in questions_that_failed_extraction if q not in actual_found_question_numbers
        )

        business_context["uploaded_plan_mode"] = True
        business_context["missing_questions"] = missing_questions
        business_context["found_questions_count"] = saved_count
        business_context["business_info_uploaded_at"] = datetime.now().isoformat()

        # asked_q drives Angel's "what to ask next" logic and the progress UI.
        # It must consider EVERY canonical Q we now have an answer for, including
        # answer-only completions (where Angel had already asked the question
        # before the upload) and Qs that were already answered in chat history.
        any_saved = bool(qa_pairs_to_save) or bool(qa_answers_only_to_save)
        if missing_questions:
            asked_q_tag = f"BUSINESS_PLAN.{min(missing_questions):02d}"
        elif any_saved and max_saved_question < 45:
            asked_q_tag = f"BUSINESS_PLAN.{max_saved_question + 1:02d}"
        elif any_saved or answered_question_numbers:
            asked_q_tag = "BUSINESS_PLAN.45"
        else:
            asked_q_tag = "BUSINESS_PLAN.01"

        await patch_session(session_id, user_id, {
            "current_phase": "BUSINESS_PLAN",
            "answered_count": new_answered_count,
            "asked_q": asked_q_tag,
            "business_context": business_context,
        })

        print(
            f"✅ save-found-info complete | saved={saved_count} | missing={missing_questions} | asked_q={asked_q_tag}"
        )

        return JSONResponse(content={
            "success": True,
            "message": f"Saved {saved_count} found information entries to chat history",
            "saved_count": saved_count,
            "found_questions": actual_found_question_numbers,
            "missing_questions": missing_questions,
            "failed_extraction": questions_that_failed_extraction,
            "asked_q": asked_q_tag,
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving found info to history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save found information: {str(e)}")
