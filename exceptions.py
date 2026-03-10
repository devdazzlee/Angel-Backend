from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_400_BAD_REQUEST
from pydantic import ValidationError
from gotrue.errors import AuthApiError  
import traceback

async def global_exception_handler(request: Request, exc: Exception):
    print("⚠️ Global Exception Caught")
    print(f"🔗 Path: {request.url.path}")
    print(f"🧵 Exception Type: {type(exc).__name__}")
    print(f"📝 Exception Message: {str(exc)}")
    traceback.print_exc()
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal Server Error",
            "message": str(exc),
        },
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    print("🚨 HTTPException Caught")
    print(f"🔗 Path: {request.url.path}")
    print(f"📦 Status Code: {exc.status_code}")
    print(f"📝 Detail: {exc.detail}")

    # Return FastAPI standard format with detail field
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
        },
    )

async def validation_exception_handler(request: Request, exc: ValidationError):
    print("📛 Validation Error Caught")
    print(f"🔗 Path: {request.url.path}")
    print(f"📝 Errors: {exc.errors()}")

    # Make Pydantic's default messages more user-friendly
    details = exc.errors()
    for err in details:
        try:
            err_type = err.get("type")
            loc = err.get("loc") or []
            field = loc[-1] if loc else "field"
            ctx = err.get("ctx") or {}

            if err_type == "string_too_short" and "min_length" in ctx:
                err["msg"] = f"{field} must be at least {ctx['min_length']} characters."
            elif err_type == "string_too_long" and "max_length" in ctx:
                err["msg"] = f"{field} must be at most {ctx['max_length']} characters."
        except Exception:
            # If formatting fails, keep the original error unchanged
            pass

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Validation Error",
            "details": details,
        },
    )

async def supabase_auth_exception_handler(request: Request, exc: AuthApiError):
    print("🔐 Supabase Auth Error Caught")
    print(f"🔗 Path: {request.url.path}")
    print(f"📝 Error Message: {exc.message}")
    
    # Improve error message for email confirmation errors
    error_message = exc.message.lower()
    error_detail = exc.message  # Default to original message
    
    # Check if this is an email confirmation error
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
    
    # Check if error is related to email confirmation
    is_email_confirmation_error = any(keyword in error_message for keyword in email_confirmation_keywords)
    
    # Also check the request path - if it's a signin/login attempt with unconfirmed email
    if is_email_confirmation_error or (
        "/signin" in str(request.url.path).lower() or 
        "/login" in str(request.url.path).lower() or
        "/auth/signin" in str(request.url.path).lower()
    ):
        # Check if the error might be related to unconfirmed email
        # Supabase sometimes returns different error messages for unconfirmed emails
        unconfirmed_indicators = [
            "invalid login credentials",
            "invalid credentials",
            "email or password is incorrect",
            "user not found"
        ]
        
        # If it's a login attempt and we get generic auth error, it might be unconfirmed email
        # But we should only suggest email confirmation if we're certain
        if is_email_confirmation_error:
            error_detail = "If you just signed up, check your inbox for a validation link. You must confirm your email address before you can sign in."
    
    return JSONResponse(
        status_code=HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": "Authentication Failed",
            "message": error_detail,
        },
    )
