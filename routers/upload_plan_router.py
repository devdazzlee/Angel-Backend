from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from middlewares.auth import verify_auth_token
from services.upload_plan_service import process_uploaded_plan, extract_business_info_from_plan, analyze_plan_completeness
from services.chat_service import save_chat_message
from services.session_service import get_session, patch_session
from db.supabase import supabase
import os
import uuid
import tempfile
import json
import re

router = APIRouter()

@router.post("/")
async def upload_business_plan(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(verify_auth_token)
):
    """
    Upload and process a business plan document (does NOT store in database)
    Simply extracts business info and returns it to frontend for session update
    Supports: PDF, DOCX, TXT files
    
    Endpoint: POST /upload-plan (router prefix + "/" = /upload-plan)
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
        
        # Extract business information
        business_info = await extract_business_info_from_plan(processed_content)
        
        # Analyze plan completeness and identify missing information
        analysis = await analyze_plan_completeness(processed_content, business_info)
        
        # Return the extracted business info and analysis to frontend
        # Frontend will update the session with this data and show missing questions
        return JSONResponse(content={
            "success": True,
            "message": "Business plan processed and analyzed successfully!",
            "business_info": business_info,
            "analysis": analysis,
            "content_preview": processed_content[:500] + "..." if len(processed_content) > 500 else processed_content
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

@router.post("/save-found-info")
async def save_found_info_to_history(
    request: Request,
    current_user: dict = Depends(verify_auth_token)
):
    """
    Save found information from uploaded plan to chat history as Q&A pairs
    This creates proper chat history entries for information that was found in the plan
    """
    # Get user_id from request.state (set by verify_auth_token)
    user_id = request.state.user["id"] if hasattr(request.state, 'user') and request.state.user else None
    if not user_id:
        # Fallback: try to get from current_user if it's a dict
        if isinstance(current_user, dict) and "id" in current_user:
            user_id = current_user["id"]
        else:
            raise HTTPException(status_code=401, detail="Authentication required")
    body = await request.json()
    session_id = body.get("session_id")
    business_info = body.get("business_info", {})
    found_questions = body.get("found_questions", [])  # List of question numbers that were found
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Get session to verify ownership
    session = await get_session(session_id, user_id)
    
    # Map business_info fields to question numbers (approximate mapping)
    # This creates Q&A pairs for information found in the plan
    question_mapping = {
        "business_name": (1, "What is your business name?"),
        "tagline": (2, "What is your business tagline or mission statement?"),
        "mission": (2, "What is your business tagline or mission statement?"),
        "problem": (3, "What problem does your business solve?"),
        "solution": (3, "What problem does your business solve?"),
        "unique_value": (4, "What makes your business unique?"),
        "product_description": (5, "Describe your core product or service in detail"),
        "target_market": (8, "Who is your target market?"),
        "market_size": (9, "What is the size of your target market?"),
        "competitors": (10, "Who are your main competitors?"),
        "location": (12, "Where will your business be located?"),
        "pricing": (17, "How will you price your product/service?"),
        "startup_costs": (19, "What are your estimated startup costs?"),
        "monthly_expenses": (20, "What are your estimated monthly operating expenses?"),
        "funding_needs": (22, "How much funding do you need to get started?"),
        "marketing_strategy": (25, "How will you reach your target customers?"),
        "legal_structure": (31, "What business structure will you use (LLC, Corporation, etc.)?"),
    }
    
    saved_count = 0
    
    try:
        # First, get existing chat history to check for duplicates
        from services.chat_service import fetch_chat_history
        existing_history = await fetch_chat_history(session_id)
        
        # Extract existing question numbers from history
        existing_question_numbers = set()
        for record in existing_history:
            if record.get("role") == "assistant":
                content = record.get("content", "")
                # Extract question number from tag like [[Q:BUSINESS_PLAN.01]]
                import re
                tag_match = re.search(r'\[\[Q:BUSINESS_PLAN\.(\d+)\]\]', content)
                if tag_match:
                    existing_question_numbers.add(int(tag_match.group(1)))
        
        print(f"📋 Existing questions in history: {sorted(existing_question_numbers)}")
        
        # Collect all Q&A pairs to save, sorted by question number
        qa_pairs_to_save = []
        
        for field, value in business_info.items():
            if not value or value == "" or value == "N/A":
                continue
                
            # Find matching question
            if field in question_mapping:
                question_num, question_text = question_mapping[field]
                
                # Only save if this question was marked as "found" in the analysis
                # AND it doesn't already exist in history
                if question_num in found_questions and question_num not in existing_question_numbers:
                    # Format answer based on field type
                    if isinstance(value, dict):
                        answer_text = json.dumps(value, indent=2)
                    elif isinstance(value, list):
                        answer_text = ", ".join(str(v) for v in value)
                    else:
                        answer_text = str(value)
                    
                    qa_pairs_to_save.append({
                        "question_num": question_num,
                        "question_text": question_text,
                        "answer": answer_text
                    })
        
        # Sort by question number to maintain order
        qa_pairs_to_save.sort(key=lambda x: x["question_num"])
        
        # Save all Q&A pairs in order
        for qa_pair in qa_pairs_to_save:
            question_num = qa_pair["question_num"]
            question_text = qa_pair["question_text"]
            answer_text = qa_pair["answer"]
            
            # Create assistant message with question
            assistant_content = f"[[Q:BUSINESS_PLAN.{question_num:02d}]] {question_text}"
            
            # Save assistant question
            await save_chat_message(session_id, user_id, "assistant", assistant_content)
            
            # Save user answer
            await save_chat_message(session_id, user_id, "user", answer_text)
            
            saved_count += 1
            print(f"✅ Saved found info: Q{question_num} - {question_text[:50]}...")
        
        # Get missing questions list from request
        missing_questions = body.get("missing_questions", [])  # List of question numbers that are missing
        
        # Get current business_context or create new one
        session = await get_session(session_id, user_id)
        business_context = session.get("business_context", {}) or {}
        if not isinstance(business_context, dict):
            business_context = {}
        
        # Store missing questions and uploaded plan mode in business_context JSON
        business_context["uploaded_plan_mode"] = True
        business_context["missing_questions"] = missing_questions
        business_context["found_questions_count"] = saved_count
        
        # Update session to track that we're in "missing questions mode"
        # Store in business_context JSON since missing_questions column doesn't exist
        await patch_session(session_id, {
            "business_context": business_context
        })
        
        print(f"✅ Session updated with missing questions in business_context: {missing_questions}")
        
        return JSONResponse(content={
            "success": True,
            "message": f"Saved {saved_count} found information entries to chat history",
            "saved_count": saved_count
        })
        
    except Exception as e:
        print(f"Error saving found info to history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save found information: {str(e)}")
