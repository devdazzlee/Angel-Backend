from fastapi import APIRouter, Request, HTTPException, Depends
import stripe
import os
from dotenv import load_dotenv
import logging
from pydantic import BaseModel
from typing import Optional
from services.stripe_service import (
    handle_stripe_webhook, 
    create_checkout_session, 
    check_user_payment_status,
    get_user_payments
)
from middlewares.auth import verify_auth_token

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateCheckoutRequest(BaseModel):
    price_id: Optional[str] = None
    success_url: str
    cancel_url: str
    product_name: Optional[str] = "Angel AI Premium"
    amount: Optional[int] = 4999


@router.post("/create-checkout-session")
async def create_checkout(
    request: CreateCheckoutRequest,
    user: dict = Depends(verify_auth_token)
):
    """Create a Stripe checkout session for one-time payment."""
    user_id = user["sub"]
    user_email = user["email"]
    
    has_paid = await check_user_payment_status(user_id)
    if has_paid:
        return {"success": True, "already_paid": True, "message": "You already have premium access"}
    
    session = await create_checkout_session(
        user_id=user_id,
        user_email=user_email,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        product_name=request.product_name,
        amount=request.amount,
        price_id=request.price_id
    )
    
    return {"success": True, "checkout_url": session.url, "session_id": session.id}


@router.get("/check-payment-status")
async def check_payment_status(user: dict = Depends(verify_auth_token)):
    """Check if user has paid and can access premium features."""
    user_id = user["sub"]
    has_paid = await check_user_payment_status(user_id)
    
    return {
        "success": True,
        "has_paid": has_paid,
        "can_download": has_paid
    }


@router.get("/payment-history")
async def payment_history(user: dict = Depends(verify_auth_token)):
    """Get payment history for the authenticated user."""
    user_id = user["sub"]
    payments = await get_user_payments(user_id)
    
    return {"success": True, "payments": payments}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe webhook endpoint."""
    body = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    event = stripe.Webhook.construct_event(body, sig_header, STRIPE_WEBHOOK_SECRET)
    result = await handle_stripe_webhook(event)
    
    return {"success": True, "result": result}
