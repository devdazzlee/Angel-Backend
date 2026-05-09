"""
User Preferences Service
Handles user preferences including Angel Constructive Feedback Intensity Scale (0-10)
"""
from db.supabase import supabase
from typing import Optional, Dict, Any
import logging
from utils.constant import CONSTRUCTIVE_FEEDBACK_SCALE

logger = logging.getLogger(__name__)

async def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """
    Get user preferences including feedback intensity scale.
    Returns default preferences if not set.
    """
    # `.maybe_single()` returns None on 0 rows instead of raising PGRST116, which
    # happens routinely for users who haven't customized their preferences yet —
    # logging that as a WARNING every chat turn was just noise.
    try:
        result = (
            supabase.table("user_preferences")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        row = result.data if result else None

        if row:
            preferences = row.get("preferences", {}) or {}
            # Splat first, then overlay explicit defaults so any None values stored in
            # the JSON column don't bypass the safe defaults below.
            merged: Dict[str, Any] = {**preferences}
            if merged.get("feedback_intensity") is None:
                merged["feedback_intensity"] = 5  # 0-10, moderate
            if merged.get("communication_style") is None:
                merged["communication_style"] = row.get("communication_style") or "professional"
            return merged

        # No preferences row exists yet — return documented defaults silently.
        return {
            "feedback_intensity": 5,
            "communication_style": "professional",
        }
    except Exception as e:
        # Genuine errors (network, schema, etc.) still warn so they're visible.
        logger.warning(f"Error fetching user preferences: {e}, returning defaults")
        return {
            "feedback_intensity": 5,
            "communication_style": "professional",
        }

async def update_feedback_intensity(user_id: str, intensity: int) -> Dict[str, Any]:
    """
    Update user's preferred feedback intensity (0-10).
    0 = Very gentle, supportive only
    5 = Moderate constructive feedback
    10 = Very challenging, pushes hard for depth
    """
    if not (0 <= intensity <= 10):
        raise ValueError("Feedback intensity must be between 0 and 10")
    
    try:
        # Get existing preferences or create new
        existing = supabase.table("user_preferences").select("*").eq("user_id", user_id).execute()
        
        preferences_json = {}
        if existing.data and len(existing.data) > 0:
            # Update existing preferences
            existing_prefs = existing.data[0].get("preferences", {})
            if isinstance(existing_prefs, dict):
                preferences_json = existing_prefs
            preferences_json["feedback_intensity"] = intensity
            
            result = supabase.table("user_preferences").update({
                "preferences": preferences_json,
                "updated_at": "now()"
            }).eq("user_id", user_id).execute()
        else:
            # Create new preferences record
            preferences_json["feedback_intensity"] = intensity
            result = supabase.table("user_preferences").insert({
                "user_id": user_id,
                "preferences": preferences_json,
                "communication_style": "professional"
            }).execute()
        
        logger.info(f"Updated feedback intensity to {intensity} for user {user_id}")
        return {
            "success": True,
            "feedback_intensity": intensity,
            "message": f"Feedback intensity set to {intensity}/10"
        }
    except Exception as e:
        logger.error(f"Error updating feedback intensity: {e}")
        raise ValueError(f"Failed to update feedback intensity: {str(e)}") from e

def get_feedback_intensity_guidance(intensity: int) -> str:
    """
    Instructions for Angel's constructive coaching at this intensity level.
    Wording is sourced from utils.constant.CONSTRUCTIVE_FEEDBACK_SCALE (single source of truth).
    """
    level = max(0, min(10, int(intensity)))
    desc = CONSTRUCTIVE_FEEDBACK_SCALE.get(level, CONSTRUCTIVE_FEEDBACK_SCALE[5])
    return f"""
FEEDBACK INTENSITY LEVEL {level} — CONSTRUCTIVE COACHING (0–10)

{desc}

OPERATIONAL RULES:
• Critique assumptions, not the founder.
• Pair every risk or weakness with specific improvement guidance.
• Frame feedback as optimization, not correction.
• Every critique must end with a way forward.
"""

