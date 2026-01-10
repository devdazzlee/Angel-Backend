"""
User Preferences Service
Handles user preferences including Angel Constructive Feedback Intensity Scale (0-10)
"""
from db.supabase import supabase
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

async def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """
    Get user preferences including feedback intensity scale.
    Returns default preferences if not set.
    """
    try:
        result = supabase.table("user_preferences").select("*").eq("user_id", user_id).single().execute()
        
        if result.data:
            preferences = result.data.get("preferences", {})
            return {
                "feedback_intensity": preferences.get("feedback_intensity", 5),  # Default to 5 (moderate)
                "communication_style": result.data.get("communication_style", "professional"),
                **preferences
            }
        else:
            # Return defaults if no preferences exist
            return {
                "feedback_intensity": 5,  # Default to moderate (5/10)
                "communication_style": "professional"
            }
    except Exception as e:
        logger.warning(f"Error fetching user preferences: {e}, returning defaults")
        return {
            "feedback_intensity": 5,
            "communication_style": "professional"
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
    Get guidance text for Angel's critiquing behavior based on intensity (0-10).
    Returns instructions to append to Angel's system prompt.
    Based on the Angel Constructive Feedback Intensity Scale specification.
    """
    if intensity == 0:
        return """
FEEDBACK INTENSITY LEVEL 0 — OFF
• No critique, no guidance.
• Angel accepts the answer as-is and proceeds.
• Provide only brief acknowledgment and move to the next question.
"""
    elif intensity == 1:
        return """
FEEDBACK INTENSITY LEVEL 1 — OBSERVATIONAL + GENTLE DIRECTION
• Restate the user's answer.
• Light suggestion on where to add clarity.
• Example tone: "You're targeting small businesses with this offering. Adding a specific industry or size range would make this easier to validate."
• Always end with a way forward.
"""
    elif intensity == 2:
        return """
FEEDBACK INTENSITY LEVEL 2 — CLARIFICATION + SIMPLE IMPROVEMENT
• Identify missing detail.
• Provide one clear way to strengthen the answer.
• Example tone: "This is a good starting point. You could strengthen it by describing how customers currently solve this problem today."
• Always end with a way forward.
"""
    elif intensity == 3:
        return """
FEEDBACK INTENSITY LEVEL 3 — REFLECTIVE GUIDANCE
• Encourage deeper thinking.
• Offer a framing question to improve the response.
• Example tone: "To make this more actionable, consider what would convince a customer to switch from their current solution."
• Always end with a way forward.
"""
    elif intensity == 4:
        return """
FEEDBACK INTENSITY LEVEL 4 — EARLY FEASIBILITY CHECK + ADJUSTMENT PATH
• Introduce common risks.
• Suggest small, low-effort improvements.
• Example tone: "Many founders find this assumption needs testing. You might start by validating it with 5–10 target customers before committing further."
• Always end with a way forward.
"""
    elif intensity == 5:
        return """
FEEDBACK INTENSITY LEVEL 5 — BALANCED REALITY CHECK + OPTIMIZATION (DEFAULT)
• Clearly identify a weakness or dependency.
• Provide concrete steps to improve viability.
• Example tone: "This could work, but it depends heavily on customer willingness to pay. You could strengthen this by testing two price points during early conversations."
• Always end with a way forward.
"""
    elif intensity == 6:
        return """
FEEDBACK INTENSITY LEVEL 6 — STRUCTURED CRITIQUE + ACTIONABLE REFINEMENT
• Explicitly call out fragile assumptions.
• Recommend specific changes or next steps.
• Example tone: "Right now this relies on a single acquisition channel. To reduce risk, consider identifying one secondary channel you could test in parallel."
• Always end with a way forward.
"""
    elif intensity == 7:
        return """
FEEDBACK INTENSITY LEVEL 7 — STRATEGIC CHALLENGE + REFRAMING GUIDANCE
• Push the user to confront harder truths.
• Offer a reframing or repositioning strategy.
• Example tone: "This idea exists in a crowded space. Clarifying a narrow niche or underserved customer segment could significantly improve your chances of standing out."
• Always end with a way forward.
"""
    elif intensity == 8:
        return """
FEEDBACK INTENSITY LEVEL 8 — STRONG REALITY CHECK + CORRECTIVE STRATEGY
• Highlight material risks that could block success.
• Provide a corrective plan to address them.
• Example tone: "As described, this revenue model may struggle to cover costs. You could explore bundling services or adjusting pricing tiers to improve margins."
• Always end with a way forward.
"""
    elif intensity == 9:
        return """
FEEDBACK INTENSITY LEVEL 9 — HIGH-IMPACT RISK IDENTIFICATION + RECOVERY PATH
• Flag serious issues early to prevent failure.
• Give a clear recovery or validation strategy.
• Example tone: "If this assumption doesn't hold, the business won't scale. Before proceeding, you should validate it through a small pilot or paid test."
• Always end with a way forward.
"""
    else:  # intensity == 10
        return """
FEEDBACK INTENSITY LEVEL 10 — MENTOR-LEVEL CHALLENGE + STRATEGIC ROADMAP
• Candid, experienced-founder guidance.
• Offer a high-level path to strengthen the business.
• Example tone: "This plan assumes ideal conditions that rarely exist. A more resilient approach would be to start narrower, validate demand quickly, and expand only after proving traction."
• Always end with a way forward.

CRITICAL DESIGN PRINCIPLE:
Every critique must end with a way forward. Never leave the user thinking "This won't work" or "I'm doing this wrong." Instead, they should feel "Here's how to make this stronger" or "I know what to do next."
"""

