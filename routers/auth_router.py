from fastapi import APIRouter
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)
from schemas.auth_schemas import (
    SignUpSchema, 
    SignInSchema, 
    ResetPasswordSchema, 
    UpdatePasswordSchema,
    RefreshTokenSchema,
    AcceptTermsSchema,
    AcceptPrivacySchema
)
from services.auth_service import (
    create_user,
    authenticate_user,
    send_reset_password_email,
    update_password,
    refresh_session,
    accept_terms,
    accept_privacy,
    send_confirmation_email_after_acceptance,
    check_acceptance_status
)
from middlewares.auth import verify_auth_token
from fastapi import Depends, Request

auth_router = APIRouter()

@auth_router.post("/signup")
async def signup(user: SignUpSchema):
    try:
        created_user = await create_user(user.email, user.password, user.full_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "message": "User created successfully", "result": {"user": created_user}}

@auth_router.post("/signin")
async def signin(user: SignInSchema):
    try:
        session = await authenticate_user(user.email, user.password)
        return {"success": True, "message": "User authenticated successfully", "result": {"session": session}}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

@auth_router.post("/reset-password")
async def reset_password(user: ResetPasswordSchema):
    """Send password reset email to user"""
    try:
        response = await send_reset_password_email(user.email)
        return {"success": True, "message": response.get("message", "A password reset link has been sent to your email."), "result": response}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@auth_router.post("/update-password")
async def update_password_endpoint(user: UpdatePasswordSchema):
    """Update user password using reset token from email"""
    try:
        result = await update_password(user.token, user.password)
        return {"success": True, "message": "Password updated successfully", "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@auth_router.post("/refresh-token")
def refresh_token(token: RefreshTokenSchema):
    try:
        session = refresh_session(token.refresh_token)
        return {
            "success": True,
            "message": "Session refreshed successfully",
            "result": {"session": session}
        }
    except Exception as e:
        error_message = str(e)
        if "Session expired" in error_message:
            raise HTTPException(
                status_code=401, 
                detail={
                    "success": False,
                    "error": "Session expired",
                    "message": "Please log in again",
                    "requires_reauth": True
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": "Token refresh failed",
                    "message": error_message
                }
            )

@auth_router.post("/accept-terms")
async def accept_terms_endpoint(
    request: Request,
    data: AcceptTermsSchema,
    _: None = Depends(verify_auth_token)
):
    """Accept Terms and Conditions. Returns True if both Terms and Privacy are now accepted."""
    try:
        user_id = request.state.user["id"]
        both_accepted = await accept_terms(user_id, data.name, data.date)
        
        # If both are now accepted, send confirmation email
        if both_accepted:
            try:
                await send_confirmation_email_after_acceptance(user_id)
            except Exception as email_error:
                logger.warning(f"Failed to send confirmation email after acceptance: {email_error}")
                # Don't fail the request if email fails
        
        return {
            "success": True,
            "message": "Terms and Conditions accepted",
            "result": {
                "terms_accepted": True,
                "both_accepted": both_accepted
            }
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to accept terms: {str(exc)}") from exc

@auth_router.post("/accept-privacy")
async def accept_privacy_endpoint(
    request: Request,
    data: AcceptPrivacySchema,
    _: None = Depends(verify_auth_token)
):
    """Accept Privacy Policy. Returns True if both Terms and Privacy are now accepted."""
    try:
        user_id = request.state.user["id"]
        both_accepted = await accept_privacy(user_id, data.name, data.date)
        
        # If both are now accepted, send confirmation email
        if both_accepted:
            try:
                await send_confirmation_email_after_acceptance(user_id)
            except Exception as email_error:
                logger.warning(f"Failed to send confirmation email after acceptance: {email_error}")
                # Don't fail the request if email fails
        
        return {
            "success": True,
            "message": "Privacy Policy accepted",
            "result": {
                "privacy_accepted": True,
                "both_accepted": both_accepted
            }
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to accept privacy: {str(exc)}") from exc

@auth_router.get("/acceptance-status")
async def get_acceptance_status(
    request: Request,
    _: None = Depends(verify_auth_token)
):
    """Check if user has accepted both Terms and Privacy Policy."""
    try:
        user_id = request.state.user["id"]
        status = await check_acceptance_status(user_id)
        return {
            "success": True,
            "result": status
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to check acceptance status: {str(exc)}") from exc