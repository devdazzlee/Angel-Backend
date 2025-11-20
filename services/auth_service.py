from db.supabase import supabase
import logging
from typing import Final, Optional
from gotrue.errors import AuthApiError

logger = logging.getLogger(__name__)

_MIN_E164_LENGTH: Final[int] = 8
_MAX_E164_LENGTH: Final[int] = 15


def _normalize_contact_number(contact_number: Optional[str]) -> Optional[str]:
    if not contact_number:
        return None
    
    stripped = contact_number.strip()
    if not stripped:
        return None

    if not stripped.startswith("+"):
        raise ValueError("Contact number must start with '+' followed by country code, e.g., +15551234567")

    digits_only = ''.join(ch for ch in stripped[1:] if ch.isdigit())
    normalized = f"+{digits_only}" if digits_only else "+"

    if len(digits_only) < _MIN_E164_LENGTH or len(digits_only) > _MAX_E164_LENGTH:
        raise ValueError("Contact number must contain 8-15 digits after the '+'. Example: +15551234567")

    return normalized


async def create_user(email: str, password: str, full_name: str, contact_number: Optional[str] = None):
    user_data = {
        "full_name": full_name,
        "display_name": full_name,
    }
    
    if contact_number:
        normalized_phone = _normalize_contact_number(contact_number)
        if normalized_phone:
            user_data["contact_number"] = contact_number
            user_data["phone_e164"] = normalized_phone

    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": user_data
            }
        })
    except AuthApiError as exc:
        logger.error("Supabase signup failed: %s", exc.message)
        raise ValueError(exc.message) from exc

    if response.user is None:
        raise ValueError("User not created")

    user_id = response.user.id

    try:
        updated_user_response = supabase.auth.admin.get_user_by_id(user_id)
        return updated_user_response.user
    except AuthApiError as exc:
        logger.warning("Unable to fetch user after signup, returning created user: %s", exc.message)
        return response.user

async def authenticate_user(email: str, password: str):
    response = supabase.auth.sign_in_with_password({"email": email, "password": password})
    if response.session is None:
        raise Exception("Invalid credentials")
    return response.session

async def send_reset_password_email(email: str):
    supabase.auth.reset_password_for_email(email)
    return {"email": email}

def refresh_session(refresh_token: str):
    try:
        logger.info("Attempting to refresh session with token")
        response = supabase.auth.refresh_session(refresh_token)
        if response.session is None:
            logger.error("Token refresh failed - no session returned")
            raise Exception("Token refresh failed")
        logger.info("Session refreshed successfully")
        return response.session
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error refreshing session: {error_message}")
        
        # Handle specific Supabase auth errors
        if "Already Used" in error_message:
            logger.warning("Refresh token already used - user needs to re-authenticate")
            raise Exception("Session expired - please log in again")
        elif "Invalid Refresh Token" in error_message:
            logger.warning("Invalid refresh token - user needs to re-authenticate")
            raise Exception("Session expired - please log in again")
        else:
            raise Exception(f"Token refresh failed: {error_message}")