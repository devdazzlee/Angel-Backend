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
import asyncio
from datetime import datetime

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
    found_questions = body.get("found_questions", [])  # List of question numbers that were found (1-45)
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    # Get session to verify ownership
    session = await get_session(session_id, user_id)
    
    # Map business_info fields to question numbers using actual question text from constant.py
    # This creates Q&A pairs for information found in the plan
    # IMPORTANT: Question numbers match the actual BUSINESS_PLAN question sequence
    # NOTE: Multiple field names can map to same question (e.g., "mission", "tagline", "vision" all answer Q2)
    # The code uses the first non-empty value found, so no duplicates are created
    question_mapping = {
        # Question 1: Business Name
        "business_name": (1, "What is your business name? If you haven't decided yet, what are your top 3-5 name options?"),
        
        # Question 2: Mission/Tagline (multiple field names for same question)
        "mission": (2, "What is your business tagline or mission statement?"),
        "tagline": (2, "What is your business tagline or mission statement?"),
        "vision": (2, "What is your business tagline or mission statement?"),
        
        # Question 3: Problem Solved (multiple field names for same question)
        "problem": (3, "What problem does your business solve? Who has this problem and how significant is it for them?"),
        "problem_solved": (3, "What problem does your business solve? Who has this problem and how significant is it for them?"),
        
        # Question 4: Unique Value (multiple field names for same question)
        "value_proposition": (4, "What makes your business unique? What's your competitive advantage or unique value proposition?"),
        "unique_value": (4, "What makes your business unique? What's your competitive advantage or unique value proposition?"),
        "competitive_advantage": (4, "What makes your business unique? What's your competitive advantage or unique value proposition?"),
        
        # Question 5: Product/Service Description (multiple field names for same question)
        "product_description": (5, "Describe your core product or service in detail. What exactly will you be offering to customers?"),
        "solution": (5, "Describe your core product or service in detail. What exactly will you be offering to customers?"),
        
        # Question 8: Target Market
        "target_market": (8, "Who is your target market? Be specific about demographics, psychographics, and behaviors."),
        
        # Question 9: Market Size
        "market_size": (9, "What is the size of your target market? How many potential customers exist?"),
        
        # Question 11: Competitors
        "competitors": (11, "Who are your main competitors? What are their strengths and weaknesses?"),
        
        # Question 12: Location
        "location": (12, "Where will your business be located? Why did you choose this location?"),
        
        # Question 18: Pricing (multiple field names for same question)
        "pricing": (18, "How will you price your product/service? What pricing strategy will you use?"),
        "revenue_model": (18, "How will you price your product/service? What pricing strategy will you use?"),
        
        # Question 20: Startup Costs
        "startup_costs": (20, "What are your estimated startup costs? What one-time expenses will you have?"),
        
        # Question 21: Monthly Expenses
        "monthly_expenses": (21, "What are your estimated monthly operating expenses? Include all recurring costs."),
        
        # Question 22: Funding Needs
        "funding_needs": (22, "How much funding do you need to get started? How will you use this money?"),
        
        # Question 26: Marketing Strategy
        "marketing_strategy": (26, "How will you reach your target customers? What marketing channels will you use?"),
        
        # Question 32: Legal Structure (multiple field names for same question)
        "legal_structure": (32, "What licenses and permits do you need? Have you researched local requirements?"),
        "business_structure": (32, "What licenses and permits do you need? Have you researched local requirements?"),
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
        
        # Import question text extractor
        from utils.constant import ANGEL_SYSTEM_PROMPT
        
        # Extract question text from constant.py using regex
        def get_question_text(question_num: int) -> str:
            """Extract actual question text from ANGEL_SYSTEM_PROMPT"""
            # Pattern to match [[Q:BUSINESS_PLAN.NN]] followed by question text
            # This captures the question text until the next tag or section marker
            tag_pattern = rf'\[\[Q:BUSINESS_PLAN\.{question_num:02d}\]\]\s*'
            match = re.search(tag_pattern, ANGEL_SYSTEM_PROMPT, re.MULTILINE)
            if match:
                start_pos = match.end()
                # Find the end of the question (next tag, next section, or end of line with guidance)
                # Look for next [[Q: tag or next section marker (---)
                next_tag_pattern = r'\[\[Q:BUSINESS_PLAN\.\d{2}\]\]'
                next_section_pattern = r'^---'
                
                # Extract text until next tag or section
                remaining_text = ANGEL_SYSTEM_PROMPT[start_pos:]
                next_tag_match = re.search(next_tag_pattern, remaining_text)
                next_section_match = re.search(next_section_pattern, remaining_text, re.MULTILINE)
                
                end_pos = len(remaining_text)
                if next_tag_match:
                    end_pos = min(end_pos, next_tag_match.start())
                if next_section_match:
                    end_pos = min(end_pos, next_section_match.start())
                
                question_text = remaining_text[:end_pos].strip()
                
                # Clean up: remove guidance lines (lines that are just questions without context)
                lines = [line.strip() for line in question_text.split('\n') if line.strip()]
                # Keep the main question (first line) and any context lines
                # Remove lines that are just standalone questions (guidance)
                main_question = lines[0] if lines else ""
                
                # If main question ends with ?, return it; otherwise include first few context lines
                if main_question.endswith('?'):
                    return main_question
                elif len(lines) > 0:
                    # Return first line as main question
                    return lines[0]
                else:
                    return question_text.split('\n')[0].strip() if question_text else ""
            
            # Fallback: use question_mapping if available
            for field, (q_num, q_text) in question_mapping.items():
                if q_num == question_num:
                    # Extract just the main question (first sentence)
                    main_q = q_text.split('?')[0] + '?' if '?' in q_text else q_text.split('.')[0] + '.'
                    return main_q.strip()
            
            # Final fallback: construct from question number
            return f"Business Plan Question {question_num}"
        
        # Map business_info fields to question numbers for answer extraction
        field_to_question_map = {}
        for field, (q_num, _) in question_mapping.items():
            if q_num not in field_to_question_map:
                field_to_question_map[q_num] = []
            field_to_question_map[q_num].append(field)
        
        # Collect all Q&A pairs to save, sorted by question number
        qa_pairs_to_save = []
        
        # Process each found question number
        # IMPORTANT: For ALL 45 questions, we extract answers from business_info OR use AI to extract from document
        print(f"🔍 Processing {len(found_questions)} found questions (out of 45 total) to extract answers...")
        print(f"📋 Available business_info fields: {list(business_info.keys())}")
        
        # We'll use AI to extract answers from business_info JSON for any question
        
        async def extract_answer_for_question(question_num: int, question_text: str) -> str:
            """Extract answer for a specific question using business_info first, then AI if needed"""
            # First, try to find answer from business_info using mapped fields
            answer_text = None
            if question_num in field_to_question_map:
                # Check all mapped fields for this question
                for field in field_to_question_map[question_num]:
                    value = business_info.get(field)
                    if value and value != "" and value != "N/A" and value is not None:
                        # Format answer based on field type
                        if isinstance(value, dict):
                            answer_text = json.dumps(value, indent=2)
                        elif isinstance(value, list):
                            answer_text = ", ".join(str(v) for v in value if v)
                        else:
                            answer_text = str(value).strip()
                        if answer_text and answer_text.strip():
                            return answer_text  # Found answer, return it
            
            # If no answer from mapping, try common field names
            common_fields = {
                1: ["business_name"],
                2: ["mission", "tagline", "vision"],
                3: ["problem", "problem_solved"],
                4: ["unique_value", "value_proposition", "competitive_advantage"],
                5: ["product_description", "solution"],
                8: ["target_market"],
                9: ["market_size"],
                11: ["competitors"],
                12: ["location"],
                18: ["pricing", "revenue_model"],
                20: ["startup_costs"],
                21: ["monthly_expenses"],
                22: ["funding_needs"],
                26: ["marketing_strategy"],
                32: ["legal_structure", "business_structure"],
            }
            
            if question_num in common_fields:
                for field in common_fields[question_num]:
                    value = business_info.get(field)
                    if value and value != "" and value != "N/A":
                        answer_text = str(value).strip()
                        if answer_text:
                            return answer_text
            
            # If still no answer, use AI to extract from business_info JSON
            # This works for ALL 45 questions by analyzing the structured data
            try:
                from openai import AsyncOpenAI
                ai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                
                # Convert business_info to JSON string for AI analysis
                business_info_json = json.dumps(business_info, indent=2)
                
                extraction_prompt = f"""
                Based on the extracted business information below, provide an answer to this business plan question.
                
                Question {question_num}: {question_text}
                
                Extracted Business Information:
                {business_info_json[:6000]}  # Limit to avoid token limits
                
                Instructions:
                - If the information directly answers the question, provide a clear, concise answer (2-5 sentences)
                - If the information partially answers it, provide what's available
                - If the information doesn't answer it at all, return "NOT_FOUND"
                - Use the actual values from the business_info, don't make up information
                - Format the answer naturally, as if the user wrote it
                
                Return ONLY the answer text, or "NOT_FOUND" if no relevant information exists.
                """
                
                response = await ai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are an expert at extracting and formatting business plan information. Always use actual data from the provided information, never invent details."},
                        {"role": "user", "content": extraction_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                
                extracted = response.choices[0].message.content.strip()
                if extracted and extracted != "NOT_FOUND" and len(extracted) > 10:
                    print(f"  🤖 AI extracted answer for Q{question_num} from business_info")
                    return extracted
            except Exception as e:
                print(f"⚠️ AI extraction failed for Q{question_num}: {e}")
            
            return None
        
        # CRITICAL FIX: Process ALL 45 questions to determine which are truly found vs missing
        # The frontend's "found_questions" is just an estimate - we need to verify by extracting answers
        all_questions = list(range(1, 46))  # Questions 1-45
        questions_that_failed_extraction = []
        
        # Process all questions (not just the frontend's "found_questions" estimate)
        for question_num in sorted(all_questions):
            # Skip if already exists in history
            if question_num in existing_question_numbers:
                print(f"⏭️ Skipping Q{question_num} - already exists in history")
                continue
            
            # Get question text from constant.py
            question_text = get_question_text(question_num)
            
            # Extract answer using the helper function
            answer_text = await extract_answer_for_question(question_num, question_text)
            
            # Only save if we have a valid answer
            if answer_text and answer_text.strip() and len(answer_text.strip()) > 3:
                qa_pairs_to_save.append({
                    "question_num": question_num,
                    "question_text": question_text,
                    "answer": answer_text
                })
                print(f"✅ Prepared Q{question_num}: {question_text[:50]}... → {answer_text[:50]}...")
            else:
                # Question failed extraction - add to failed list
                questions_that_failed_extraction.append(question_num)
                print(f"⚠️ Q{question_num} - no valid answer found (tried business_info and AI extraction)")
        
        # Sort by question number to maintain order (1, 2, 3, etc.)
        qa_pairs_to_save.sort(key=lambda x: x["question_num"])
        
        # ACTUAL found questions = questions we successfully extracted answers for
        actual_found_question_numbers = [q["question_num"] for q in qa_pairs_to_save]
        print(f"📋 Successfully extracted answers for {len(qa_pairs_to_save)} questions: {actual_found_question_numbers}")
        print(f"⚠️ Failed to extract answers for {len(questions_that_failed_extraction)} questions: {questions_that_failed_extraction}")
        
        # Add a summary message at the start showing what was found from uploaded plan
        if qa_pairs_to_save:
            questions_list = ", ".join([f"Q{q['question_num']}" for q in qa_pairs_to_save])
            summary_message = f"📄 **Business Plan Uploaded and Analyzed**\n\nI've extracted the following information from your uploaded business plan:\n\n**Questions Found in Your Plan:** {questions_list}\n\n**Total Questions Found:** {len(qa_pairs_to_save)}\n\nYour answers to these questions have been automatically saved to the chat history below. I'll now ask you only the missing questions to complete your business plan."
            
            # Save summary message as assistant message FIRST (before Q&A pairs)
            await save_chat_message(session_id, user_id, "assistant", summary_message)
            await asyncio.sleep(0.1)  # Slightly longer delay to ensure summary appears first
        
        # Save all Q&A pairs in order with sequential delays to ensure proper timestamp ordering
        print(f"💾 Starting to save {len(qa_pairs_to_save)} Q&A pairs to chat history...")
        for idx, qa_pair in enumerate(qa_pairs_to_save):
            question_num = qa_pair["question_num"]
            question_text = qa_pair["question_text"]
            answer_text = qa_pair["answer"]
            
            try:
                # Create assistant message with question
                # Format: [[Q:BUSINESS_PLAN.NN]] Question text
                assistant_content = f"[[Q:BUSINESS_PLAN.{question_num:02d}]] {question_text}"
                
                # Save assistant question
                await save_chat_message(session_id, user_id, "assistant", assistant_content)
                print(f"  ✅ Saved assistant message for Q{question_num}")
                
                # Small delay to ensure sequential timestamps (100ms between each save for better ordering)
                await asyncio.sleep(0.1)
                
                # Save user answer
                await save_chat_message(session_id, user_id, "user", answer_text)
                print(f"  ✅ Saved user answer for Q{question_num}: {answer_text[:50]}...")
                
                saved_count += 1
                
                # Small delay to ensure sequential timestamps (except after last one)
                if idx < len(qa_pairs_to_save) - 1:
                    await asyncio.sleep(0.1)
            except Exception as e:
                print(f"  ❌ Error saving Q{question_num}: {e}")
                # Continue with next Q&A pair even if one fails
                continue
        
        print(f"✅ Successfully saved {saved_count} Q&A pairs from uploaded plan in order")
        
        # Get missing questions list and business_info from request
        original_missing_questions = body.get("missing_questions", [])  # Original missing questions from analysis
        uploaded_business_info = body.get("business_info", {}) or {}
        
        # CRITICAL FIX: Update missing_questions to include questions that failed extraction
        # Combine original missing questions with questions that failed extraction
        # Remove duplicates and ensure we have a complete list
        missing_questions = list(set(original_missing_questions + questions_that_failed_extraction))
        missing_questions = sorted([q for q in missing_questions if q not in actual_found_question_numbers])
        
        print(f"📊 Missing Questions Update:")
        print(f"  - Original missing from analysis: {sorted(original_missing_questions)}")
        print(f"  - Questions that failed extraction: {sorted(questions_that_failed_extraction)}")
        print(f"  - Final missing questions list: {missing_questions}")
        print(f"  - Actual found questions: {sorted(actual_found_question_numbers)}")
        
        # Get current session to update answered_count and asked_q
        session = await get_session(session_id, user_id)
        business_context = session.get("business_context", {}) or {}
        if not isinstance(business_context, dict):
            business_context = {}
        
        # CRITICAL: Update answered_count based on saved Q&A pairs
        # IMPORTANT: The progress calculation in progress.py uses asked_q (current_tag) to determine progress,
        # NOT answered_count. However, answered_count should still reflect how many questions have been answered.
        # 
        # For uploaded plans: answered_count = count of saved questions
        # Example: If we saved Q2, Q3, Q8, Q9, Q12, Q22, answered_count should be 6
        current_answered_count = session.get("answered_count", 0)
        
        # Count how many BUSINESS_PLAN questions were already answered before this upload
        existing_bp_questions = len([q for q in existing_question_numbers if 1 <= q <= 45])
        
        # New answered_count = existing BP questions + newly saved questions
        # This ensures we don't double-count if questions were already in history
        new_answered_count = existing_bp_questions + saved_count
        
        # Also track the highest question number saved for reference (used for asked_q calculation)
        max_saved_question = max([q["question_num"] for q in qa_pairs_to_save]) if qa_pairs_to_save else 0
        
        print(f"📊 Progress Update:")
        print(f"  - Existing BP questions in history: {existing_bp_questions}")
        print(f"  - Saved {saved_count} new Q&A pairs")
        print(f"  - Previous answered_count: {current_answered_count}")
        print(f"  - New answered_count: {new_answered_count} (existing: {existing_bp_questions} + new: {saved_count})")
        print(f"  - Highest question saved: Q{max_saved_question}")
        print(f"  - Saved question numbers: {sorted([q['question_num'] for q in qa_pairs_to_save])}")
        
        # CRITICAL: Merge uploaded business_info into business_context
        # This ensures the uploaded plan's business data overrides old GKY data
        if uploaded_business_info and isinstance(uploaded_business_info, dict):
            # Merge uploaded business info, giving precedence to uploaded data
            for key, value in uploaded_business_info.items():
                if value and value != "" and value != "N/A":
                    # Normalize keys - handle both formats
                    normalized_key = key.lower().replace(" ", "_").replace("-", "_")
                    business_context[normalized_key] = value
                    # Also keep original key for compatibility
                    if normalized_key != key:
                        business_context[key] = value
            
            # Ensure critical fields are set from uploaded plan
            if uploaded_business_info.get("business_name"):
                business_context["business_name"] = uploaded_business_info["business_name"]
            if uploaded_business_info.get("industry"):
                business_context["industry"] = uploaded_business_info["industry"]
            if uploaded_business_info.get("location"):
                business_context["location"] = uploaded_business_info["location"]
            if uploaded_business_info.get("tagline") or uploaded_business_info.get("mission"):
                business_context["mission"] = uploaded_business_info.get("tagline") or uploaded_business_info.get("mission")
            if uploaded_business_info.get("legal_structure"):
                business_context["legal_structure"] = uploaded_business_info["legal_structure"]
        
        # Store missing questions and uploaded plan mode in business_context JSON
        business_context["uploaded_plan_mode"] = True
        business_context["missing_questions"] = missing_questions
        business_context["found_questions_count"] = saved_count
        business_context["business_info_uploaded_at"] = datetime.now().isoformat()
        
        # Determine the asked_q tag - CRITICAL for progress calculation
        # The progress calculation uses asked_q to determine which question we're currently on
        # This should be set to the first missing question so the system knows what to ask next
        if missing_questions and len(missing_questions) > 0:
            first_missing = min(missing_questions)
            asked_q_tag = f"BUSINESS_PLAN.{first_missing:02d}"
            print(f"🎯 Setting asked_q to first missing question: {asked_q_tag}")
        elif qa_pairs_to_save:
            # If no missing questions, all 45 questions were found in the uploaded plan
            # Set to next question after the highest saved, or Q45 if all done
            next_question = max_saved_question + 1
            if next_question <= 45:
                asked_q_tag = f"BUSINESS_PLAN.{next_question:02d}"
                print(f"🎯 No missing questions - setting asked_q to next question: {asked_q_tag}")
            else:
                # All 45 questions answered - stay on Q45
                asked_q_tag = f"BUSINESS_PLAN.45"
                print(f"🎯 All questions answered - setting asked_q to: {asked_q_tag}")
        else:
            # No questions were saved (edge case - shouldn't happen)
            asked_q_tag = "BUSINESS_PLAN.01"
            print(f"⚠️ No questions saved - defaulting asked_q to: {asked_q_tag}")
        
        # Update session with all the changes - CRITICAL for proper progress tracking
        session_updates = {
            "current_phase": "BUSINESS_PLAN",  # Ensure we're in BUSINESS_PLAN phase
            "answered_count": new_answered_count,  # Count of answered questions (not question number)
            "asked_q": asked_q_tag,  # Current question tag (used by progress calculation)
            "business_context": business_context
        }
        
        await patch_session(session_id, session_updates)
        
        print(f"✅ Session updated successfully:")
        print(f"  - current_phase: BUSINESS_PLAN")
        print(f"  - answered_count: {new_answered_count} (total questions answered)")
        print(f"  - asked_q: {asked_q_tag} (current question - used for progress)")
        print(f"  - missing_questions: {missing_questions}")
        print(f"  - Business context keys: {list(uploaded_business_info.keys()) if uploaded_business_info else 'None'}")
        
        # Verify the updates will work correctly with progress calculation
        # Progress calculation uses asked_q to determine current question number
        # Example: If asked_q = "BUSINESS_PLAN.07", progress will show "Question 7 of 45"
        if asked_q_tag.startswith("BUSINESS_PLAN."):
            current_q_num = int(asked_q_tag.split(".")[1])
            expected_progress = round((current_q_num / 46) * 100)
            print(f"📊 Expected progress calculation:")
            print(f"  - Current question: Q{current_q_num}")
            print(f"  - Progress: {current_q_num}/46 = {expected_progress}%")
            print(f"  - Total answered: {new_answered_count} questions")
        
        return JSONResponse(content={
            "success": True,
            "message": f"Saved {saved_count} found information entries to chat history",
            "saved_count": saved_count,
            "found_questions": actual_found_question_numbers,  # Return actual found questions
            "missing_questions": missing_questions,  # Return updated missing questions
            "failed_extraction": questions_that_failed_extraction  # Questions that failed extraction
        })
        
    except Exception as e:
        print(f"Error saving found info to history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save found information: {str(e)}")
