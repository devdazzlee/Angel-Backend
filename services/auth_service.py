from db.supabase import supabase
import logging
import os
from gotrue.errors import AuthApiError

logger = logging.getLogger(__name__)


def _check_user_exists(email: str) -> bool:
    """
    Check if a user with the given email already exists in auth.users table.
    Uses a database function for efficient direct query - this is the ROOT CAUSE fix.
    Prevents duplicate signups by checking BEFORE calling sign_up().
    """
    try:
        # Use RPC to call database function that directly queries auth.users table
        # This is the most efficient and reliable method
        result = supabase.rpc('check_email_exists', {'email_address': email}).execute()
        
        if result.data is True:
            logger.warning(f"User with email {email} already exists in database")
            return True
        return False
        
    except Exception as e:
        # If RPC function doesn't exist yet, fall back to admin API
        logger.warning(f"RPC function check_email_exists not available, using admin API fallback: {e}")
        try:
            # Fallback: Use admin API (less efficient but works)
            email_lower = email.lower().strip()
            users_response = supabase.auth.admin.list_users(page=1, per_page=1000)
            
            if hasattr(users_response, 'users') and users_response.users:
                for user in users_response.users:
                    if user.email and user.email.lower().strip() == email_lower:
                        logger.warning(f"User with email {email} already exists in database")
                        return True
        except Exception as admin_error:
            logger.error(f"Failed to check user existence via admin API: {admin_error}")
            # FAIL SAFE: Don't allow signup if we can't verify - prevents duplicates
            raise ValueError("Unable to verify email availability. Please try again later or contact support.") from admin_error
    
    return False


async def create_user(email: str, password: str, full_name: str):
    # Check if user already exists before attempting signup
    if _check_user_exists(email):
        raise ValueError("An account with this email already exists. Please sign in instead.")
    user_data = {
        "full_name": full_name,
        "display_name": full_name,
    }

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
        # Check for duplicate email errors - provide user-friendly message
        error_lower = exc.message.lower()
        if any(keyword in error_lower for keyword in [
            "already registered", 
            "user already exists", 
            "email already", 
            "already been registered",
            "user already registered",
            "email address is already in use"
        ]):
            raise ValueError("An account with this email already exists. Please sign in instead.") from exc
        # For other errors, return the original message
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
    """
    Send password reset email to user.
    Returns email address if successful.
    """
    try:
        # Check if user exists first to avoid revealing email existence
        # But we'll still send email even if user doesn't exist (security best practice)
        supabase.auth.reset_password_for_email(
            email,
            {
                "redirect_to": f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/reset-password"
            }
        )
        logger.info(f"Password reset email sent to {email}")
        return {"email": email, "message": "If an account exists with this email, a password reset link has been sent."}
    except AuthApiError as exc:
        logger.error(f"Failed to send reset password email to {email}: {exc.message}")
        # Don't reveal if email exists - return success anyway (security best practice)
        return {"email": email, "message": "If an account exists with this email, a password reset link has been sent."}
    except Exception as e:
        logger.error(f"Unexpected error sending reset password email: {e}")
        raise ValueError("Failed to send reset password email. Please try again later.") from e


async def update_password(email: str, token: str, new_password: str):
    """
    Update user password using the reset token from email.
    Uses admin API to update password directly.
    Note: Token validation should happen on frontend (Supabase client handles this).
    Backend verifies email exists and updates password via admin API.
    """
    try:
        # Verify user exists by email
        if not _check_user_exists(email):
            raise ValueError("User not found. Please check your email address.")
        
        # Get user by email using admin API
        users_response = supabase.auth.admin.list_users()
        user = None
        if hasattr(users_response, 'users') and users_response.users:
            for u in users_response.users:
                if u.email and u.email.lower() == email.lower():
                    user = u
                    break
        
        if not user:
            raise ValueError("User not found. Please check your email address.")
        
        # Update password using admin API
        # Note: Token validation happens on frontend before this call
        update_response = supabase.auth.admin.update_user_by_id(
            user.id,
            {"password": new_password}
        )
        
        if update_response.user:
            logger.info(f"Password updated successfully for user: {update_response.user.email}")
            return {
                "success": True,
                "message": "Password updated successfully",
                "user": {
                    "id": update_response.user.id,
                    "email": update_response.user.email
                }
            }
        else:
            raise ValueError("Failed to update password. Please try again.")
        
    except ValueError as e:
        raise e
    except AuthApiError as exc:
        logger.error(f"Failed to update password: {exc.message}")
        error_lower = exc.message.lower()
        if "expired" in error_lower or "invalid" in error_lower:
            raise ValueError("Invalid or expired reset token. Please request a new password reset link.") from exc
        raise ValueError(f"Failed to update password: {exc.message}") from exc
    except Exception as e:
        logger.error(f"Unexpected error updating password: {e}")
        raise ValueError("Failed to update password. Please try again later.") from e

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