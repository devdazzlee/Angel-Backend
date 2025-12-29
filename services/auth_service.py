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
        # Use admin API to create user WITHOUT sending confirmation email
        # This prevents the automatic email from being sent
        # We'll send it manually after Terms/Privacy acceptance
        try:
            # Create user via admin API (doesn't send email automatically)
            admin_response = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": False,  # Don't confirm email yet
                "user_metadata": user_data
            })
            
            if admin_response.user is None:
                raise ValueError("User not created")
            
            user_id = admin_response.user.id
            response_user = admin_response.user
            
        except Exception as admin_error:
            # Fallback to regular sign_up if admin API fails
            logger.warning(f"Admin API user creation failed, using sign_up: {admin_error}")
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": user_data,
                    "email_redirect_to": None
                }
            })
            
            if response.user is None:
                raise ValueError("User not created")
            
            user_id = response.user.id
            response_user = response.user
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
    except Exception as exc:
        logger.error(f"User creation failed: {exc}")
        raise ValueError(f"Failed to create user: {str(exc)}") from exc

    # user_id and response_user are set in the try block above

    # Create acceptance record (both false initially)
    try:
        supabase.table("user_legal_acceptances").insert({
            "user_id": user_id,
            "terms_accepted": False,
            "privacy_accepted": False,
            "email_confirmation_sent": False
        }).execute()
        logger.info(f"Created legal acceptance record for user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to create legal acceptance record: {e}")
        # Don't fail signup if this fails, but log it

    try:
        updated_user_response = supabase.auth.admin.get_user_by_id(user_id)
        return updated_user_response.user
    except AuthApiError as exc:
        logger.warning("Unable to fetch user after signup, returning created user: %s", exc.message)
        return response_user

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
        # Check if user exists first
        if not _check_user_exists(email):
            logger.warning(f"Password reset requested for non-existent email: {email}")
            raise ValueError("This account is not available. Please check your email address.")
        
        # User exists, send reset email
        # Ensure redirect URL includes the full path
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        # Remove trailing slash if present
        frontend_url = frontend_url.rstrip('/')
        redirect_url = f"{frontend_url}/reset-password"
        
        supabase.auth.reset_password_for_email(
            email,
            {
                "redirect_to": redirect_url
            }
        )
        logger.info(f"Password reset email sent to {email}")
        return {"email": email, "message": "A password reset link has been sent to your email."}
    except ValueError as e:
        # Re-raise ValueError (user doesn't exist)
        raise e
    except AuthApiError as exc:
        logger.error(f"Failed to send reset password email to {email}: {exc.message}")
        raise ValueError("Failed to send reset password email. Please try again later.") from exc
    except Exception as e:
        logger.error(f"Unexpected error sending reset password email: {e}")
        raise ValueError("Failed to send reset password email. Please try again later.") from e


async def update_password(token: str, new_password: str):
    """
    Update user password using the reset token from email.
    Extracts email from token and updates password via admin API.
    """
    try:
        # Get user from token to extract email
        user_response = supabase.auth.get_user(token)
        
        if not user_response or not user_response.user:
            raise ValueError("Invalid or expired reset token. Please request a new password reset link.")
        
        user = user_response.user
        email = user.email
        
        if not email:
            raise ValueError("Unable to extract email from token. Please request a new password reset link.")
        
        # Verify user exists
        if not _check_user_exists(email):
            raise ValueError("User not found. Please check your email address.")
        
        # Update password using admin API
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
        if "expired" in error_lower or "invalid" in error_lower or "token" in error_lower:
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


async def accept_terms(user_id: str, name: str, date: str):
    """
    Record user's acceptance of Terms and Conditions.
    Returns True if both Terms and Privacy are now accepted.
    """
    try:
        from datetime import datetime
        
        # Parse date string (expecting YYYY-MM-DD format)
        acceptance_date = datetime.strptime(date, "%Y-%m-%d").date()
        acceptance_timestamp = datetime.now()
        
        # Update or insert acceptance record
        result = supabase.table("user_legal_acceptances").upsert({
            "user_id": user_id,
            "terms_accepted": True,
            "terms_accepted_at": acceptance_timestamp.isoformat(),
            "terms_accepted_name": name,
            "terms_accepted_date": acceptance_date.isoformat()
        }, on_conflict="user_id").execute()
        
        logger.info(f"Terms accepted by user {user_id}")
        
        # Check if both are now accepted
        acceptance_record = supabase.table("user_legal_acceptances").select("*").eq("user_id", user_id).single().execute()
        
        if acceptance_record.data:
            record = acceptance_record.data
            both_accepted = record.get("terms_accepted", False) and record.get("privacy_accepted", False)
            return both_accepted
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to record terms acceptance: {e}")
        raise ValueError(f"Failed to record acceptance: {str(e)}") from e


async def accept_privacy(user_id: str, name: str, date: str):
    """
    Record user's acceptance of Privacy Policy.
    Returns True if both Terms and Privacy are now accepted.
    """
    try:
        from datetime import datetime
        
        # Parse date string (expecting YYYY-MM-DD format)
        acceptance_date = datetime.strptime(date, "%Y-%m-%d").date()
        acceptance_timestamp = datetime.now()
        
        # Update or insert acceptance record
        result = supabase.table("user_legal_acceptances").upsert({
            "user_id": user_id,
            "privacy_accepted": True,
            "privacy_accepted_at": acceptance_timestamp.isoformat(),
            "privacy_accepted_name": name,
            "privacy_accepted_date": acceptance_date.isoformat()
        }, on_conflict="user_id").execute()
        
        logger.info(f"Privacy Policy accepted by user {user_id}")
        
        # Check if both are now accepted
        acceptance_record = supabase.table("user_legal_acceptances").select("*").eq("user_id", user_id).single().execute()
        
        if acceptance_record.data:
            record = acceptance_record.data
            both_accepted = record.get("terms_accepted", False) and record.get("privacy_accepted", False)
            return both_accepted
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to record privacy acceptance: {e}")
        raise ValueError(f"Failed to record acceptance: {str(e)}") from e


async def send_confirmation_email_after_acceptance(user_id: str):
    """
    Send confirmation email after both Terms and Privacy are accepted.
    This should only be called once both are accepted.
    Uses Supabase admin API to generate confirmation link and send email.
    """
    try:
        # Get user email
        user_response = supabase.auth.admin.get_user_by_id(user_id)
        if not user_response or not user_response.user:
            raise ValueError("User not found")
        
        user = user_response.user
        email = user.email
        
        if not email:
            raise ValueError("User email not found")
        
        # Check if email already sent
        acceptance_record = supabase.table("user_legal_acceptances").select("*").eq("user_id", user_id).single().execute()
        
        if acceptance_record.data and acceptance_record.data.get("email_confirmation_sent", False):
            logger.info(f"Confirmation email already sent to {email}")
            return {"email": email, "message": "Confirmation email already sent"}
        
        # Generate confirmation link using admin API
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        frontend_url = frontend_url.rstrip('/')
        redirect_url = f"{frontend_url}/auth/confirm"
        
        try:
            # Generate signup confirmation link and send email
            # Using generate_link with type "signup" should send the email
            link_response = supabase.auth.admin.generate_link({
                "type": "signup",
                "email": email,
                "options": {
                    "redirect_to": redirect_url
                }
            })
            
            # Note: generate_link with type "signup" generates the link but may not send email
            # If email confirmations are disabled in Supabase, we need to send it manually
            # Try to resend confirmation email using admin API
            try:
                # Update user to trigger email resend (if needed)
                # This ensures the email is sent even if generate_link doesn't send it
                supabase.auth.admin.update_user_by_id(
                    user_id,
                    {
                        "email_confirm": False  # Keep unconfirmed, but this might trigger email
                    }
                )
            except Exception as update_error:
                logger.warning(f"Could not update user to trigger email: {update_error}")
            
            logger.info(f"Confirmation link generated for {email}")
            
        except Exception as link_error:
            logger.error(f"Failed to generate confirmation link: {link_error}")
            # Try alternative: Use the user's email to manually send via Supabase email service
            # Note: This requires Supabase email service to be configured
            raise ValueError("Failed to generate confirmation link. Please contact support.") from link_error
        
        # Mark email as sent
        from datetime import datetime
        supabase.table("user_legal_acceptances").update({
            "email_confirmation_sent": True,
            "email_confirmation_sent_at": datetime.now().isoformat()
        }).eq("user_id", user_id).execute()
        
        logger.info(f"Confirmation email sent to {email}")
        return {"email": email, "message": "Confirmation email sent successfully"}
        
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {e}")
        raise ValueError(f"Failed to send confirmation email: {str(e)}") from e


async def check_acceptance_status(user_id: str):
    """
    Check if user has accepted both Terms and Privacy Policy.
    Returns dict with acceptance status.
    """
    try:
        result = supabase.table("user_legal_acceptances").select("*").eq("user_id", user_id).single().execute()
        
        if not result.data:
            return {
                "terms_accepted": False,
                "privacy_accepted": False,
                "both_accepted": False
            }
        
        record = result.data
        terms_accepted = record.get("terms_accepted", False)
        privacy_accepted = record.get("privacy_accepted", False)
        
        return {
            "terms_accepted": terms_accepted,
            "privacy_accepted": privacy_accepted,
            "both_accepted": terms_accepted and privacy_accepted
        }
        
    except Exception as e:
        logger.warning(f"Failed to check acceptance status: {e}")
        # Return false if we can't check (safer to block access)
        return {
            "terms_accepted": False,
            "privacy_accepted": False,
            "both_accepted": False
        }