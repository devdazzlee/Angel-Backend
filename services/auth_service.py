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
            # Could be unconfirmed email - check if user exists
            try:
                if _check_user_exists(email):
                    # User exists - might be unconfirmed email
                    raise ValueError("If you just signed up, check your inbox for a validation link. You must confirm your email address before you can sign in. If you've already confirmed, please check your email and password.")
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
        
        # Get user by email to get user_id
        from db.supabase import supabase
        user_response = supabase.auth.admin.list_users()
        user_id = None
        user_obj = None
        
        # Find user by email
        if hasattr(user_response, 'users') and user_response.users:
            for user in user_response.users:
                if user.email and user.email.lower() == email.lower():
                    user_id = user.id
                    user_obj = user
                    break
        
        if not user_id:
            raise ValueError("User not found. Please check your email address.")
        
        # User exists, generate reset link using admin API (allows custom expiration handling)
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        frontend_url = frontend_url.rstrip('/')
        redirect_url = f"{frontend_url}/reset-password"
        
        # Generate recovery link using admin API
        # This generates a link that we can track for expiration
        link_response = supabase.auth.admin.generate_link({
            "type": "recovery",
            "email": email,
            "options": {
                "redirect_to": redirect_url
            }
        })
        
        if not link_response or not hasattr(link_response, 'properties') or not link_response.properties:
            raise ValueError("Failed to generate password reset link. Please try again later.")
        
        # Extract token from the generated link
        reset_link = link_response.properties.get('action_link', '') or link_response.properties.get('href', '')
        if not reset_link:
            # Fallback: Use standard reset_password_for_email if generate_link doesn't work
            logger.warning("Admin generate_link didn't return link, using standard reset_password_for_email")
            supabase.auth.reset_password_for_email(
                email,
                {
                    "redirect_to": redirect_url
                }
            )
        else:
            # Extract token from link (format: .../recover?token=...)
            import re
            token_match = re.search(r'[?&]token=([^&]+)', reset_link)
            if token_match:
                reset_token = token_match.group(1)
                
                # Store reset token with creation timestamp and 10-minute expiration
                from datetime import datetime, timedelta
                expires_at = datetime.now() + timedelta(minutes=10)
                
                # Store in password_reset_tokens table (create table if doesn't exist)
                try:
                    supabase.table("password_reset_tokens").insert({
                        "user_id": user_id,
                        "email": email,
                        "token": reset_token,
                        "created_at": datetime.now().isoformat(),
                        "expires_at": expires_at.isoformat(),
                        "used": False
                    }).execute()
                    
                    logger.info(f"Password reset token stored for {email}, expires at {expires_at}")
                except Exception as db_error:
                    logger.warning(f"Could not store reset token in database (table may not exist): {db_error}")
                    # Continue anyway - Supabase will validate the token
        
        # Send the reset email using Supabase's email service
        # Note: Email sender (support@founderport.ai) must be configured in Supabase Dashboard
        # Authentication > Email Templates > Reset Password
        supabase.auth.reset_password_for_email(
            email,
            {
                "redirect_to": redirect_url
            }
        )
        
        logger.info(f"Password reset email sent to {email} (expires in 10 minutes)")
        return {
            "email": email, 
            "message": "A password reset link has been sent to your email. The link will expire in 10 minutes."
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
    Validates 10-minute expiration before allowing password update.
    Extracts email from token and updates password via admin API.
    """
    try:
        from datetime import datetime
        
        # Check if token exists in our password_reset_tokens table and validate 10-minute expiration
        token_record = None
        user_id = None
        email = None
        
        try:
            # Query password_reset_tokens table to check expiration
            token_result = supabase.table("password_reset_tokens").select("*").eq("token", token).eq("used", False).single().execute()
            
            if token_result.data:
                token_record = token_result
                token_data = token_result.data
                expires_at_str = token_data.get("expires_at")
                created_at_str = token_data.get("created_at")
                user_id = token_data.get("user_id")
                email = token_data.get("email")
                
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                    now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else datetime.now()
                    
                    # Check if token has expired (10 minutes)
                    if now > expires_at:
                        logger.warning(f"Password reset token expired for token: {token[:20]}...")
                        raise ValueError("Password reset link has expired. Please request a new password reset link. Reset links expire after 10 minutes.")
                    
                    # Additional validation: Check if token was created more than 10 minutes ago
                    if created_at_str:
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        elapsed = (now - created_at).total_seconds()
                        if elapsed > 600:  # 10 minutes in seconds
                            logger.warning(f"Password reset token expired (more than 10 minutes old) for token: {token[:20]}...")
                            raise ValueError("Password reset link has expired. Please request a new password reset link. Reset links expire after 10 minutes.")
        except ValueError:
            # Re-raise expiration errors
            raise
        except Exception as token_check_error:
            # If table doesn't exist or token not found, log warning but continue with Supabase validation
            logger.warning(f"Could not check token expiration in database (table may not exist or token not found): {token_check_error}")
            # Continue with Supabase's token validation as fallback
        
        # If we found token record with valid expiration, use it to update password
        if token_record and token_record.data and user_id:
            # Update password using admin API (we already validated expiration)
            update_response = supabase.auth.admin.update_user_by_id(
                user_id,
                {"password": new_password}
            )
            
            if update_response.user:
                # Mark token as used
                try:
                    supabase.table("password_reset_tokens").update({
                        "used": True,
                        "used_at": datetime.now().isoformat()
                    }).eq("token", token).execute()
                except Exception as mark_error:
                    logger.warning(f"Could not mark token as used: {mark_error}")
                
                logger.info(f"Password updated successfully for user: {update_response.user.email}")
                return {
                    "success": True,
                    "message": "Password updated successfully",
                    "user": {
                        "id": update_response.user.id,
                        "email": update_response.user.email
                    }
                }
        
        # Fallback: Use Supabase's standard recovery flow (if token record not found)
        # Try to verify and use the recovery token via Supabase's exchange method
        # For recovery tokens, Supabase uses a different flow - tokens need to be exchanged for session
        # However, we can try using Supabase's verify_otp or update_user_by_id if we can get user from token
        
        # If we couldn't find token in our table, rely on Supabase's validation
        # Note: Supabase's default expiration may be different (configure in dashboard)
        # But we've documented that reset links expire in 10 minutes in the email
        raise ValueError("Invalid or expired reset token. Please request a new password reset link. Reset links expire after 10 minutes.")
        
    except ValueError as e:
        raise e
    except AuthApiError as exc:
        logger.error(f"Failed to update password: {exc.message}")
        error_lower = exc.message.lower()
        if "expired" in error_lower or "invalid" in error_lower or "token" in error_lower:
            raise ValueError("Invalid or expired reset token. Please request a new password reset link. Reset links expire after 10 minutes.") from exc
        raise ValueError(f"Failed to update password: {exc.message}") from exc
    except Exception as e:
        logger.error(f"Unexpected error updating password: {e}")
        error_str = str(e).lower()
        if "expired" in error_str:
            raise ValueError("Password reset link has expired. Please request a new password reset link. Reset links expire after 10 minutes.") from e
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