from fastapi import APIRouter, Request, HTTPException, Depends
import stripe
import os
from dotenv import load_dotenv
import logging
from pydantic import BaseModel
from typing import Optional
from services.stripe_service import (
    handle_stripe_webhook, 
    create_subscription_checkout_session, 
    check_user_subscription_status,
    get_user_subscription
)
from middlewares.auth import verify_auth_token

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateSubscriptionRequest(BaseModel):
    price_id: Optional[str] = None
    success_url: str
    cancel_url: str
    amount: Optional[int] = 4999


@router.post("/create-subscription")
async def create_subscription(
    subscription_request: CreateSubscriptionRequest,
    http_request: Request,
    _: None = Depends(verify_auth_token)
):
    """Create a Stripe checkout session for monthly subscription."""
    user = http_request.state.user
    user_id = user["id"]
    user_email = user["email"]
    
    has_active = await check_user_subscription_status(user_id)
    if has_active:
        return {"success": True, "already_subscribed": True, "message": "You already have an active subscription"}
    
    session = await create_subscription_checkout_session(
        user_id=user_id,
        user_email=user_email,
        success_url=subscription_request.success_url,
        cancel_url=subscription_request.cancel_url,
        price_id=subscription_request.price_id,
        amount=subscription_request.amount
    )
    
    return {"success": True, "checkout_url": session.url, "session_id": session.id}


@router.get("/check-subscription-status")
async def check_subscription_status(
    http_request: Request,
    _: None = Depends(verify_auth_token)
):
    """Check if user has an active subscription."""
    user = http_request.state.user
    user_id = user["id"]
    user_email = user.get("email", "unknown")
    
    logger.info(f"Checking subscription status for user {user_id} ({user_email})")
    
    has_active = await check_user_subscription_status(user_id)
    subscription = await get_user_subscription(user_id) if has_active else None
    
    logger.info(f"Subscription check result for user {user_id}: has_active={has_active}, subscription={subscription}")
    
    return {
        "success": True,
        "has_active_subscription": has_active,
        "can_download": has_active,
        "subscription": subscription
    }


@router.post("/cancel-subscription")
async def cancel_subscription(
    http_request: Request,
    _: None = Depends(verify_auth_token)
):
    """Cancel user's subscription at period end."""
    user = http_request.state.user
    user_id = user["id"]
    subscription = await get_user_subscription(user_id)
    
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    stripe_subscription = stripe.Subscription.modify(
        subscription["stripe_subscription_id"],
        cancel_at_period_end=True
    )
    
    return {
        "success": True,
        "message": "Subscription will be canceled at period end",
        "cancel_at_period_end": stripe_subscription.cancel_at_period_end
    }


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe webhook endpoint for subscription events."""
    body = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    event = stripe.Webhook.construct_event(body, sig_header, STRIPE_WEBHOOK_SECRET)
    result = await handle_stripe_webhook(event)
    
    return {"success": True, "result": result}


@router.get("/webhook-test")
async def webhook_test():
    """Test endpoint to verify webhook route is accessible."""
    return {
        "success": True,
        "message": "Stripe webhook endpoint is active",
        "webhook_url": "/stripe/webhook",
        "full_url": "https://angel-backend.vercel.app/stripe/webhook"
    }
