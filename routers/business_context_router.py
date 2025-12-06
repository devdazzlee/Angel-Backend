from fastapi import APIRouter, Request, Depends, HTTPException
from typing import Dict, Any
from services.session_service import get_session, patch_session
from services.chat_service import fetch_chat_history
from services.angel_service import extract_business_context_from_history
from middlewares.auth import verify_auth_token
from openai import AsyncOpenAI
import os
import json

router = APIRouter(
    tags=["Business Context"],
    dependencies=[Depends(verify_auth_token)]
)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def ai_extract_or_generate_business_name(history: list, industry: str = "", location: str = "") -> Dict[str, str]:
    """
    Use AI to extract business name from history OR generate appropriate one if not found.
    This handles cases where user said "Unsure" or never provided a name.
    """
    
    # Prepare conversation text for AI analysis
    conversation_text = ""
    for i, msg in enumerate(history[:150]):  # Analyze more messages
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        conversation_text += f"{role.upper()}: {content}\n\n"
    
    extraction_prompt = f"""
Analyze this conversation from a business questionnaire. The user is in {industry} industry, located in {location}.

CONVERSATION HISTORY:
{conversation_text}

TASK 1 - EXTRACT BUSINESS NAME:
Look for the business name the user provided:
1. Direct answers to "What is your business name?"
2. Domain names (e.g., "timelyservices.com")
3. Branded names mentioned anywhere
4. Company names the user refers to

TASK 2 - IF NOT FOUND, GENERATE APPROPRIATE NAME:
If user said "Unsure", "I don't know", or never provided a name:
- Based on their industry ({industry}), location ({location}), and business description
- Generate a professional, appropriate business name suggestion
- Make it relevant to what they described their business does
- Use their location if appropriate (e.g., "Karachi Timely Services")

IMPORTANT:
- If you find an EXPLICIT business name (not "Unsure"), return it with confidence "high"
- If user said "Unsure" or "I don't know", GENERATE a name based on context with confidence "generated"
- Do NOT return generic terms like "my business", "the company"
- Do NOT return just industry name like "Timely services" - add location or make it more specific

Return as JSON:
{{
  "business_name": "Extracted Name" or "Generated Name Based on Context",
  "confidence": "high" | "medium" | "generated",
  "source": "extracted_from_answer" or "generated_from_context",
  "reasoning": "Brief explanation of why this name"
}}
"""
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing conversations and extracting structured business information. Be precise and only extract explicit information."},
                {"role": "user", "content": extraction_prompt}
            ],
            temperature=0.1,  # Low temperature for consistency
            max_tokens=300,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        print(f"🤖 AI result: {result}")
        print(f"   - Business Name: {result.get('business_name')}")
        print(f"   - Confidence: {result.get('confidence')}")
        print(f"   - Source: {result.get('source')}")
        print(f"   - Reasoning: {result.get('reasoning', 'N/A')}")
        return result
        
    except Exception as e:
        print(f"❌ AI extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "business_name": "NOT_FOUND",
            "confidence": "low",
            "source": "extraction_failed",
            "reasoning": str(e)
        }

@router.post("/sessions/{session_id}/extract-business-context")
async def extract_business_context_from_history_api(
    session_id: str,
    request: Request
):
    """
    Extract business context from chat history when stored values are invalid (Unsure, Your Business, etc.)
    This endpoint intelligently searches KYC and Business Plan chat history for actual business information.
    """
    
    user_id = request.state.user["id"]
    
    try:
        # Get session
        session = await get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get current stored context
        stored_context = session.get("business_context") or {}
        if not isinstance(stored_context, dict):
            stored_context = {}
        
        current_business_name = stored_context.get("business_name") or session.get("business_name", "")
        current_industry = stored_context.get("industry") or session.get("industry", "")
        current_location = stored_context.get("location") or session.get("location", "")
        current_business_type = stored_context.get("business_type") or session.get("business_type", "")
        
        print(f"🔍 Current stored context: business_name='{current_business_name}', industry='{current_industry}', location='{current_location}', type='{current_business_type}'")
        
        # Check if any values are invalid/need extraction
        invalid_values = ["", "unsure", "your business", "none", "n/a", "not specified"]
        needs_extraction = (
            str(current_business_name).lower().strip() in invalid_values or
            str(current_industry).lower().strip() in invalid_values or
            str(current_location).lower().strip() in invalid_values or
            str(current_business_type).lower().strip() in invalid_values
        )
        
        if not needs_extraction:
            print(f"✅ Business context is valid, no extraction needed")
            return {
                "success": True,
                "message": "Business context is already valid",
                "result": {
                    "business_context": {
                        "business_name": current_business_name,
                        "industry": current_industry,
                        "location": current_location,
                        "business_type": current_business_type
                    },
                    "source": "stored",
                    "extracted": False
                }
            }
        
        # Fetch complete chat history from database
        print(f"📊 Extracting business context from chat history for session {session_id}")
        history = await fetch_chat_history(session_id)
        print(f"📊 Found {len(history)} messages in chat history")
        
        # Get current industry and location for context
        current_industry = stored_context.get("industry") or session.get("industry", "")
        current_location = stored_context.get("location") or session.get("location", "")
        
        # Use AI to intelligently extract OR generate business name
        ai_extraction = await ai_extract_or_generate_business_name(
            history, 
            industry=current_industry,
            location=current_location
        )
        print(f"🤖 AI extraction result: {ai_extraction}")
        
        # Also use the weighted extraction function for other fields
        extracted_context = extract_business_context_from_history(history)
        print(f"📊 Pattern-based extraction: {extracted_context}")
        
        # Build final business context
        final_context = {}
        
        # Business Name - Use AI extraction/generation
        ai_business_name = ai_extraction.get("business_name", "")
        ai_confidence = ai_extraction.get("confidence", "")
        
        if ai_business_name and ai_business_name != "NOT_FOUND" and ai_business_name.lower() not in invalid_values:
            final_context["business_name"] = ai_business_name
            if ai_confidence == "generated":
                print(f"🎯 Using AI-GENERATED business name: '{ai_business_name}' (based on: {ai_extraction.get('reasoning')})")
            else:
                print(f"✅ Using AI-EXTRACTED business name: '{ai_business_name}' (confidence: {ai_confidence})")
        else:
            # Fall back to pattern-based extraction
            extracted_name = extracted_context.get("business_name", "").strip()
            if extracted_name and extracted_name.lower() not in invalid_values:
                final_context["business_name"] = extracted_name
                print(f"✅ Using pattern-extracted business name: '{extracted_name}'")
            elif current_business_name and str(current_business_name).lower().strip() not in invalid_values:
                final_context["business_name"] = current_business_name
            else:
                final_context["business_name"] = "Your Business"
                print(f"⚠️ No valid business name found in chat history")
        
        # Industry
        extracted_industry = extracted_context.get("industry", "").strip()
        if extracted_industry and extracted_industry.lower() not in invalid_values:
            final_context["industry"] = extracted_industry
            print(f"✅ Using extracted industry: '{extracted_industry}'")
        elif current_industry and str(current_industry).lower().strip() not in invalid_values:
            final_context["industry"] = current_industry
        else:
            final_context["industry"] = "General Business"
        
        # Location
        extracted_location = extracted_context.get("location", "").strip()
        if extracted_location and extracted_location.lower() not in invalid_values:
            final_context["location"] = extracted_location
            print(f"✅ Using extracted location: '{extracted_location}'")
        elif current_location and str(current_location).lower().strip() not in invalid_values:
            final_context["location"] = current_location
        else:
            final_context["location"] = "United States"
        
        # Business Type
        extracted_type = extracted_context.get("business_type", "").strip()
        if extracted_type and extracted_type.lower() not in invalid_values:
            final_context["business_type"] = extracted_type
            print(f"✅ Using extracted business type: '{extracted_type}'")
        elif current_business_type and str(current_business_type).lower().strip() not in invalid_values:
            final_context["business_type"] = current_business_type
        else:
            final_context["business_type"] = "Startup"
        
        # Update session with extracted context
        try:
            await patch_session(
                session_id,
                user_id,
                {"business_context": final_context}
            )
            print(f"✅ Updated session business_context in database")
            
            # CRITICAL: Clear the task cache so next API call fetches fresh data
            from routers.implementation_router import task_cache
            cache_key = f"{session_id}_{user_id}"
            if cache_key in task_cache:
                del task_cache[cache_key]
                print(f"🗑️ Cleared task cache for session {session_id}")
                
        except Exception as e:
            print(f"⚠️ Failed to update session: {e}")
        
        return {
            "success": True,
            "message": "Business context extracted from chat history",
            "result": {
                "business_context": final_context,
                "source": "extracted_from_history",
                "extracted": True,
                "previous_context": {
                    "business_name": current_business_name,
                    "industry": current_industry,
                    "location": current_location,
                    "business_type": current_business_type
                }
            }
        }
        
    except Exception as e:
        print(f"❌ Error extracting business context: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to extract business context: {str(e)}")

@router.get("/sessions/{session_id}/business-context")
async def get_business_context_with_auto_extract(
    session_id: str,
    request: Request
):
    """
    Get business context with automatic extraction from history if values are invalid
    """
    
    user_id = request.state.user["id"]
    
    try:
        # Get session
        session = await get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get stored context
        stored_context = session.get("business_context") or {}
        if not isinstance(stored_context, dict):
            stored_context = {}
        
        business_name = stored_context.get("business_name") or session.get("business_name", "")
        industry = stored_context.get("industry") or session.get("industry", "")
        location = stored_context.get("location") or session.get("location", "")
        business_type = stored_context.get("business_type") or session.get("business_type", "")
        
        # Check if extraction is needed
        invalid_values = ["", "unsure", "your business", "none", "n/a", "not specified"]
        needs_extraction = str(business_name).lower().strip() in invalid_values
        
        if needs_extraction:
            print(f"🔍 Business name is invalid ('{business_name}'), extracting/generating from chat history...")
            
            # Fetch and extract from history using AI
            history = await fetch_chat_history(session_id)
            
            # Use AI for intelligent extraction or generation
            ai_extraction = await ai_extract_or_generate_business_name(
                history,
                industry=industry,
                location=location
            )
            ai_business_name = ai_extraction.get("business_name", "")
            ai_confidence = ai_extraction.get("confidence", "")
            
            if ai_business_name and ai_business_name != "NOT_FOUND" and ai_business_name.lower() not in invalid_values:
                business_name = ai_business_name
                if ai_confidence == "generated":
                    print(f"🎯 AI-GENERATED business name: '{business_name}' (reasoning: {ai_extraction.get('reasoning')})")
                else:
                    print(f"✅ AI-EXTRACTED business name: '{business_name}' (confidence: {ai_confidence})")
            else:
                # Fallback to pattern-based extraction
                extracted_context = extract_business_context_from_history(history)
                if extracted_context.get("business_name") and extracted_context["business_name"].lower() not in invalid_values:
                    business_name = extracted_context["business_name"]
                    print(f"✅ Pattern-extracted business name: '{business_name}'")
            
            if extracted_context.get("industry") and extracted_context["industry"].lower() not in invalid_values:
                industry = extracted_context["industry"]
            
            if extracted_context.get("location") and extracted_context["location"].lower() not in invalid_values:
                location = extracted_context["location"]
            
            if extracted_context.get("business_type") and extracted_context["business_type"].lower() not in invalid_values:
                business_type = extracted_context["business_type"]
            
            # Update session with extracted values
            final_context = {
                "business_name": business_name,
                "industry": industry,
                "location": location,
                "business_type": business_type
            }
            
            try:
                await patch_session(session_id, user_id, {"business_context": final_context})
                print(f"✅ Updated session with extracted context")
                
                # CRITICAL: Clear the task cache so next API call fetches fresh data
                from routers.implementation_router import task_cache
                cache_key = f"{session_id}_{user_id}"
                if cache_key in task_cache:
                    del task_cache[cache_key]
                    print(f"🗑️ Cleared task cache for session {session_id}")
                    
            except Exception as e:
                print(f"⚠️ Failed to update session: {e}")
            
            return {
                "success": True,
                "message": "Business context fetched and extracted from history",
                "result": {
                    "business_context": final_context,
                    "source": "extracted_from_history",
                    "updated": True
                }
            }
        
        # Return stored context (valid)
        return {
            "success": True,
            "message": "Business context fetched",
            "result": {
                "business_context": {
                    "business_name": business_name,
                    "industry": industry,
                    "location": location,
                    "business_type": business_type
                },
                "source": "stored",
                "updated": False
            }
        }
        
    except Exception as e:
        print(f"❌ Error getting business context: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get business context: {str(e)}")

