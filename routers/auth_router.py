from fastapi import APIRouter
from fastapi import HTTPException
from schemas.auth_schemas import SignUpSchema, SignInSchema, ResetPasswordSchema, RefreshTokenSchema
from services.auth_service import (
    create_user,
    authenticate_user,
    send_reset_password_email,
    refresh_session
)

auth_router = APIRouter()

@auth_router.post("/signup")
async def signup(user: SignUpSchema):
    created_user = await create_user(user.email, user.password)
    return {"success": True, "message": "User created successfully", "result": {"user": created_user}}

@auth_router.post("/signin")
async def signin(user: SignInSchema):
    session = await authenticate_user(user.email, user.password)
    return {"success": True, "message": "User authenticated successfully", "result": {"session": session}}

@auth_router.post("/reset-password")
async def reset_password(user: ResetPasswordSchema):
    response = await send_reset_password_email(user.email)
    return {"success": True, "message": "Reset password email sent", "result": response}

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