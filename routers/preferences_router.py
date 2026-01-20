"""
Preferences Router
Handles user preferences including Angel Constructive Feedback Intensity Scale (0-10)
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from schemas.preferences_schemas import FeedbackIntensitySchema, UserPreferencesSchema
from services.preferences_service import (
    get_user_preferences,
    update_feedback_intensity
)
from middlewares.auth import verify_auth_token
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/preferences",
    tags=["Preferences"],
    dependencies=[Depends(verify_auth_token)]
)

@router.get("/")
async def get_preferences(request: Request):
    """
    Get user preferences including feedback intensity scale (0-10).
    """
    try:
        user_id = request.state.user["id"]
        preferences = await get_user_preferences(user_id)
        return {
            "success": True,
            "message": "Preferences retrieved successfully",
            "result": preferences
        }
    except Exception as e:
        logger.error(f"Error fetching user preferences: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch preferences: {str(e)}") from e

@router.put("/feedback-intensity")
async def set_feedback_intensity(
    request: Request,
    payload: FeedbackIntensitySchema
):
    """
    Update user's preferred feedback intensity (0-10).
    - 0-2: Very gentle, supportive only
    - 3-4: Gentle with occasional suggestions
    - 5-6: Moderate constructive feedback (default)
    - 7-8: Challenging with tough questions
    - 9-10: Very challenging, rigorous feedback
    """
    try:
        user_id = request.state.user["id"]
        result = await update_feedback_intensity(user_id, payload.intensity)
        return {
            "success": True,
            "message": result.get("message", "Feedback intensity updated successfully"),
            "result": {
                "feedback_intensity": result.get("feedback_intensity", payload.intensity)
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error updating feedback intensity: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update feedback intensity: {str(e)}") from e





