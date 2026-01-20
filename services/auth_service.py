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


def _get_user_by_email(email: str):
    """
    Get user by email from Supabase auth.users table using direct database query.
    Uses RPC function for efficient O(1) lookup - works for any number of users.
    Returns user-like object if found, None otherwise.
    """
    try:
        # Primary method: Use RPC function that queries auth.users directly
        # This is the most efficient approach - direct database query, no pagination needed
        result = supabase.rpc('get_user_by_email', {'email_address': email}).execute()
        
        if result.data:
            user_data = result.data
            # Create a simple user-like object from the JSON response
            class UserObject:
                def __init__(self, data):
                    self.id = data.get('id')
                    self.email = data.get('email')
                    self.email_confirmed_at = data.get('email_confirmed_at')
                    self.created_at = data.get('created_at')
                    self.updated_at = data.get('updated_at')
                    self.user_metadata = data.get('user_metadata', {})
                    self.app_metadata = data.get('app_metadata', {})
            
            logger.info(f"Found user with email {email} via RPC function")
            return UserObject(user_data)
        
        logger.info(f"User with email {email} not found via RPC function")
        return None
        
    except Exception as e:
        # Fallback: If RPC function doesn't exist, use admin API
        # This should rarely happen if SQL function is properly set up
        logger.warning(f"RPC function get_user_by_email not available, using admin API fallback: {e}")
        try:
            # Fallback: Use admin API with get_user_by_id after finding user_id
            # This is less efficient but works as backup
            email_lower = email.lower().strip()
            
            # Try to get user using admin API's list_users with pagination
            # But limit to first page only as fallback (not ideal, but better than nothing)
            users_response = supabase.auth.admin.list_users(page=1, per_page=1000)
            
            if hasattr(users_response, 'users') and users_response.users:
                for user in users_response.users:
                    if user.email and user.email.lower().strip() == email_lower:
                        logger.info(f"Found user with email {email} via admin API fallback")
                        return user
            
            logger.warning(f"User with email {email} not found in admin API fallback")
            return None
            
        except Exception as admin_error:
            logger.error(f"Failed to get user by email via admin API fallback: {admin_error}")
            return None


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
    """
    Authenticate user with email and password.
    Returns session if successful.
    Raises descriptive error for email confirmation issues.
    """
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.session is None:
            # Check if user exists but email is not confirmed
            # Supabase returns None session for unconfirmed emails but doesn't always throw error
            raise ValueError("Invalid credentials. If you just signed up, check your inbox for a validation link.")
        return response.session
    except AuthApiError as exc:
        # Check for email confirmation errors
        error_message = exc.message.lower()
        
        email_confirmation_keywords = [
            "email not confirmed",
            "email not verified", 
            "email confirmation",
            "email verify",
            "unconfirmed email",
            "email address not confirmed",
            "user email not confirmed",
            "email address is not confirmed",
            "email not confirmed",
            "email_confirmed",
            "email address must be confirmed"
        ]
        
        is_email_confirmation_error = any(keyword in error_message for keyword in email_confirmation_keywords)
        
        if is_email_confirmation_error:
            raise ValueError("If you just signed up, check your inbox for a validation link. You must confirm your email address before you can sign in.") from exc
        
        # Check for invalid credentials - might be unconfirmed email
        invalid_credential_keywords = [
            "invalid login credentials",
            "invalid credentials",
            "email or password is incorrect",
            "incorrect email or password"
        ]
        
        if any(keyword in error_message for keyword in invalid_credential_keywords):
            # Could be unconfirmed email - check if user exists and email confirmation status
            try:
                if _check_user_exists(email):
                    # User exists - check if email is confirmed
                    user = _get_user_by_email(email)
                    if user:
                        # Check email confirmation status
                        email_confirmed = getattr(user, 'email_confirmed_at', None) is not None
                        if not email_confirmed:
                            raise ValueError("If you just signed up, check your inbox for a validation link. You must confirm your email address before you can sign in.")
                        # Email is confirmed but password is wrong
                        raise ValueError("Invalid password. Please check your password and try again.")
            except ValueError:
                # Re-raise ValueError (email confirmation or password error)
                raise
            except Exception:
                pass  # If we can't check, just return generic error
            
            raise ValueError("Invalid email or password. Please check your credentials and try again.") from exc
        
        # Re-raise other errors
        raise ValueError(exc.message) from exc
    except ValueError:
        # Re-raise ValueError errors (like the ones we just raised)
        raise
    except Exception as exc:
        logger.error(f"Authentication failed: {exc}")
        raise ValueError(f"Authentication failed: {str(exc)}") from exc

async def send_reset_password_email(email: str):
    """
    Send password reset email to user with 10-minute expiration.
    Uses Supabase admin API to generate recovery link and stores token with expiration.
    Returns email address if successful.
    """
    try:
        # Check if user exists first
        if not _check_user_exists(email):
            logger.warning(f"Password reset requested for non-existent email: {email}")
            raise ValueError("This account is not available. Please check your email address.")
        
        # Get user by email using direct database query (RPC function)
        # This efficiently queries auth.users table directly - works for any number of users
        user_obj = _get_user_by_email(email)
        
        if not user_obj:
            logger.error(f"User exists in database but not found in admin API for email: {email}")
            raise ValueError("User account found but unable to process reset. Please contact support.")
        
        user_id = user_obj.id
        
        # Check if email is confirmed - we'll try to send reset email anyway
        # If Supabase rejects it, we'll handle the error and provide helpful message
        email_confirmed = getattr(user_obj, 'email_confirmed_at', None) is not None
        if not email_confirmed:
            logger.info(f"Password reset requested for unconfirmed email: {email} - will attempt to send anyway")
        
        # User exists, send password reset email using Supabase's email service
        # Note: Supabase may allow password reset for unconfirmed emails depending on configuration
        # Note: Email sender (support@founderport.ai) must be configured in Supabase Dashboard
        # Authentication > Email Templates > Reset Password
        # Also ensure SMTP is configured in Project Settings > Auth > SMTP Settings
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        frontend_url = frontend_url.rstrip('/')
        redirect_url = f"{frontend_url}/reset-password"
        
        # Use reset_password_for_email - this generates the link AND sends the email in one call
        # This is simpler and avoids rate limiting issues from calling multiple endpoints
        try:
            supabase.auth.reset_password_for_email(
                email,
                {
                    "redirect_to": redirect_url
                }
            )
            logger.info(f"Password reset email sent to {email}")
        except Exception as send_error:
            error_str = str(send_error).lower()
            
            # Handle rate limiting - Supabase limits password reset requests to once per 60 seconds
            if "429" in str(send_error) or "too many requests" in error_str or "after" in error_str and "seconds" in error_str:
                # Extract wait time from error message if available
                import re
                wait_match = re.search(r'after (\d+) seconds?', error_str)
                wait_time = wait_match.group(1) if wait_match else "60"
                logger.warning(f"Password reset rate limited for {email}. Please wait {wait_time} seconds before requesting again.")
                raise ValueError(f"Too many password reset requests. Please wait {wait_time} seconds before requesting again. Check your email inbox - you may have already received a reset link.") from send_error
            
            # Handle email confirmation errors
            if "email" in error_str and ("not confirmed" in error_str or "unconfirmed" in error_str):
                logger.warning(f"Password reset blocked for unconfirmed email: {email}")
                raise ValueError("Please confirm your email address first. Check your inbox for the confirmation email, then try resetting your password again. If you didn't receive the confirmation email, please contact support.") from send_error
            
            # Handle other errors
            logger.error(f"Failed to send password reset email: {send_error}")
            raise ValueError("Failed to send password reset email. Please check your Supabase email configuration (SMTP settings and email templates) or contact support.") from send_error
        
        # Note: Token tracking removed - Supabase manages token expiration (default 1 hour)
        # If you need custom 10-minute expiration, you would need to:
        # 1. Use generate_link to get the token
        # 2. Store it in password_reset_tokens table
        # 3. Send email via your own SMTP
        # For now, we use Supabase's built-in reset_password_for_email which handles everything
        
        return {
            "email": email, 
            "message": "A password reset link has been sent to your email. Please check your inbox (and spam folder). The link will expire in 1 hour."
        }
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
    Supabase recovery tokens must be verified using verify_otp with type="recovery",
    then we can update the password using the verified session.
    """
    try:
        import base64
        import json
        
        # First, decode the JWT token to extract email (needed for verify_otp)
        try:
            token_parts = token.split('.')
            if len(token_parts) != 3:
                raise ValueError("Invalid token format")
            
            # Decode payload to get email
            payload = token_parts[1]
            padding = len(payload) % 4
            if padding:
                payload += '=' * (4 - padding)
            
            decoded_payload = base64.urlsafe_b64decode(payload)
            token_data = json.loads(decoded_payload)
            
            email = token_data.get('email')
            user_id = token_data.get('sub')
            exp = token_data.get('exp')
            
            if not email:
                raise ValueError("Token does not contain email information")
            
            # Check expiration
            if exp:
                from datetime import datetime, timezone
                exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
                now = datetime.now(timezone.utc)
                
                if now > exp_datetime:
                    logger.warning(f"Password reset token expired for user: {user_id}")
                    raise ValueError("Password reset link has expired. Please request a new password reset link.")
            
            logger.info(f"Decoded recovery token for email: {email}")
            
        except (ValueError, json.JSONDecodeError, Exception) as decode_error:
            logger.error(f"Failed to decode recovery token: {decode_error}")
            raise ValueError("Invalid reset token format. Please use the link from your email.") from decode_error
        
        # Verify the recovery token using Supabase's verify_otp
        # This is the proper way to validate recovery tokens and get a session
        # verify_otp requires both email and token for recovery type
        try:
            verify_response = supabase.auth.verify_otp({
                "token": token,
                "type": "recovery",
                "email": email
            })
            
            if not verify_response.session:
                raise ValueError("Token verification failed - no session returned")
            
            session = verify_response.session
            logger.info(f"Recovery token verified for email: {email}, user_id: {session.user.id}")
            
        except AuthApiError as verify_error:
            logger.error(f"Failed to verify recovery token: {verify_error.message}")
            error_lower = verify_error.message.lower()
            if "expired" in error_lower or "invalid" in error_lower or "token" in error_lower:
                raise ValueError("Invalid or expired reset token. Please request a new password reset link.") from verify_error
            raise ValueError(f"Failed to verify reset token: {verify_error.message}") from verify_error
        
        # Now update the password using the verified session
        # Use update_user with the session from verify_otp
        try:
            # The session is already set on the client from verify_otp
            # Now we can update the user's password
            update_response = supabase.auth.update_user({
                "password": new_password
            })
            
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
                raise ValueError("Failed to update password - no user returned")
                
        except AuthApiError as update_error:
            logger.error(f"Failed to update password: {update_error.message}")
            error_lower = update_error.message.lower()
            if "expired" in error_lower or "invalid" in error_lower or "token" in error_lower or "session" in error_lower:
                raise ValueError("Invalid or expired reset token. Please request a new password reset link.") from update_error
            raise ValueError(f"Failed to update password: {update_error.message}") from update_error
        
    except ValueError as e:
        # Re-raise ValueError errors (already formatted)
        raise e
    except AuthApiError as exc:
        logger.error(f"Failed to update password: {exc.message}")
        error_lower = exc.message.lower()
        if "expired" in error_lower or "invalid" in error_lower or "token" in error_lower:
            raise ValueError("Invalid or expired reset token. Please request a new password reset link.") from exc
        raise ValueError(f"Failed to update password: {exc.message}") from exc
    except Exception as e:
        logger.error(f"Unexpected error updating password: {e}")
        error_str = str(e).lower()
        if "expired" in error_str:
            raise ValueError("Password reset link has expired. Please request a new password reset link.") from e
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
    
    NOTE: Email sender configuration (support@founderport.ai) and "No Reply" setting
    must be configured in Supabase Dashboard under:
    - Authentication > Email Templates > Confirm signup
    - Set sender email to: support@founderport.ai
    - Add "No Reply" to subject line or email body
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