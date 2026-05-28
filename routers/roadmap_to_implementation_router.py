from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from services.roadmap_to_implementation_service import (
    prepare_implementation_transition,
    get_motivational_quote,
    get_service_provider_preview,
    generate_implementation_insights
)
from middlewares.auth import verify_auth_token
from utils.business_context import (
    fetch_authoritative_business_context,
    merge_request_context_overrides,
    prompt_labels,
)
import json

router = APIRouter()

@router.post("/sessions/{session_id}/roadmap-to-implementation-transition")
async def create_roadmap_to_implementation_transition(
    session_id: str,
    request: Request,
    current_user: dict = Depends(verify_auth_token)
):
    """Create comprehensive roadmap to implementation transition"""
    try:
        user_id = request.state.user["id"]
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}

        db_context = await fetch_authoritative_business_context(session_id, user_id)
        session_data = merge_request_context_overrides(db_context, body)
        labels = prompt_labels(session_data)

        roadmap_content = body.get("roadmap_content", "Roadmap content not available")

        transition_data = await prepare_implementation_transition(session_data, roadmap_content)

        if not transition_data["success"]:
            raise HTTPException(status_code=500, detail=transition_data.get("error", "Failed to prepare transition"))

        return JSONResponse(content={
            "success": True,
            "message": "Implementation transition prepared successfully",
            "result": {
                "transition_phase": "ROADMAP_TO_IMPLEMENTATION_TRANSITION",
                "motivational_quote": transition_data["motivational_quote"],
                "service_providers": transition_data["service_providers"],
                "implementation_insights": transition_data["implementation_insights"],
                "business_context": transition_data["business_context"],
                "reply": (
                    f"🚀 **Roadmap to Implementation Transition** 🚀\n\n"
                    f"Congratulations! You've successfully completed your comprehensive business plan "
                    f"and detailed launch roadmap for \"{labels['business_name']}\". "
                    f"Now it's time to transition from planning into execution mode.\n\n"
                    f"**\"{transition_data['motivational_quote']['quote']}\"** – "
                    f"{transition_data['motivational_quote']['author']}\n\n"
                    f"---\n\n"
                    f"## 🎯 **Time to Transition from Planning to Action**\n\n"
                    f"You've built a solid foundation with your business plan and roadmap. "
                    f"The time has come to transition from planning into execution mode.\n\n"
                    f"*This implementation process is tailored specifically to your "
                    f"\"{labels['business_name']}\" business in the {labels['industry']} industry, "
                    f"located in {labels['location']}.*"
                ),
            }
        })

    except Exception as e:
        print(f"Error in roadmap to implementation transition: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/service-provider-preview")
async def get_service_provider_preview_endpoint(
    session_id: str,
    request: Request,
    current_user: dict = Depends(verify_auth_token)
):
    """Get service provider preview for implementation transition"""
    try:
        user_id = request.state.user["id"]
        business_context = await fetch_authoritative_business_context(session_id, user_id)
        providers = await get_service_provider_preview(business_context)

        return JSONResponse(content={
            "success": True,
            "providers": providers
        })

    except Exception as e:
        print(f"Error getting service provider preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/implementation-insights")
async def get_implementation_insights_endpoint(
    session_id: str,
    request: Request,
    current_user: dict = Depends(verify_auth_token)
):
    """Get implementation insights for transition"""
    try:
        user_id = request.state.user["id"]
        business_context = await fetch_authoritative_business_context(session_id, user_id)
        insights = await generate_implementation_insights(business_context, "Roadmap content placeholder")

        return JSONResponse(content={
            "success": True,
            "insights": insights
        })

    except Exception as e:
        print(f"Error getting implementation insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/motivational-quote")
async def get_motivational_quote_endpoint(
    session_id: str,
    request: Request,
    current_user: dict = Depends(verify_auth_token)
):
    """Get motivational quote for transition"""
    try:
        user_id = request.state.user["id"]
        business_context = await fetch_authoritative_business_context(session_id, user_id)
        quote = await get_motivational_quote(business_context)

        return JSONResponse(content={
            "success": True,
            "quote": quote
        })

    except Exception as e:
        print(f"Error getting motivational quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))
