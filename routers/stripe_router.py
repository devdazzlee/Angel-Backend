from fastapi import APIRouter, Request, HTTPException, Depends, Query
import stripe
import os
from dotenv import load_dotenv
import logging
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from services.stripe_service import (
    handle_stripe_webhook, 
    create_subscription_checkout_session, 
    check_user_subscription_status,
    get_user_subscription,
    create_or_update_subscription
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
    amount: Optional[int] = 2000


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
    subscription = await get_user_subscription(user_id)
    
    # Check if subscription exists but payment failed
    payment_failed = False
    cancel_at_period_end = False
    if subscription:
        status = subscription.get("subscription_status", "").lower()
        payment_failed = status in ["past_due", "unpaid"]
        cancel_at_period_end = subscription.get("cancel_at_period_end", False)
    
    logger.info(f"Subscription check result for user {user_id}: has_active={has_active}, subscription={subscription}, payment_failed={payment_failed}, cancel_at_period_end={cancel_at_period_end}")
    
    return {
        "success": True,
        "has_active_subscription": has_active,
        "can_download": has_active and not payment_failed,
        "payment_failed": payment_failed,
        "cancel_at_period_end": cancel_at_period_end,
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
    user_email = user.get("email")
    subscription = await get_user_subscription(user_id)
    
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    stripe_subscription = stripe.Subscription.modify(
        subscription["stripe_subscription_id"],
        cancel_at_period_end=True
    )
    
    # Update database with cancel_at_period_end flag
    from db.supabase import supabase
    from datetime import datetime
    from services.email_service import send_subscription_cancellation_email
    
    update_result = supabase.table("user_subscriptions").update({
        "cancel_at_period_end": True,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("user_id", user_id).execute()
    
    # Send cancellation email
    try:
        if user_email and subscription.get("current_period_end"):
            await send_subscription_cancellation_email(
                user_email=user_email,
                subscription_end_date=subscription["current_period_end"]
            )
    except Exception as e:
        logger.error(f"Failed to send cancellation email: {str(e)}")
    
    logger.info(f"Subscription canceled at period end for user {user_id}")
    
    return {
        "success": True,
        "message": "Subscription will be canceled at period end",
        "cancel_at_period_end": stripe_subscription.cancel_at_period_end
    }


@router.post("/toggle-auto-renewal")
async def toggle_auto_renewal(
    http_request: Request,
    enable: bool = Query(..., description="Enable or disable auto-renewal"),
    _: None = Depends(verify_auth_token)
):
    """Toggle auto-renewal for user's subscription."""
    user = http_request.state.user
    user_id = user["id"]
    subscription = await get_user_subscription(user_id)
    
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    # enable=True means auto-renewal ON (cancel_at_period_end=False)
    # enable=False means auto-renewal OFF (cancel_at_period_end=True)
    cancel_at_period_end = not enable
    
    stripe_subscription = stripe.Subscription.modify(
        subscription["stripe_subscription_id"],
        cancel_at_period_end=cancel_at_period_end
    )
    
    # Get amount and currency from existing subscription (keep existing values)
    amount = subscription.get("amount")
    currency = subscription.get("currency", "usd")
    
    # Update database - use existing subscription data with updated cancel_at_period_end
    # Convert timestamps if they're numbers, otherwise keep as is
    current_period_start = subscription.get("current_period_start")
    current_period_end = subscription.get("current_period_end")
    
    # If timestamps are in ISO format strings, keep them; if they're numbers from Stripe, convert
    if hasattr(stripe_subscription, 'current_period_start') and stripe_subscription.current_period_start:
        if isinstance(stripe_subscription.current_period_start, (int, float)):
            current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start).isoformat()
        else:
            current_period_start = stripe_subscription.current_period_start
    
    if hasattr(stripe_subscription, 'current_period_end') and stripe_subscription.current_period_end:
        if isinstance(stripe_subscription.current_period_end, (int, float)):
            current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end).isoformat()
        else:
            current_period_end = stripe_subscription.current_period_end
    
    await create_or_update_subscription(user_id, {
        "subscription_id": stripe_subscription.id,
        "customer_id": str(stripe_subscription.customer),
        "status": stripe_subscription.status,
        "current_period_start": current_period_start,
        "current_period_end": current_period_end,
        "cancel_at_period_end": cancel_at_period_end,
        "amount": amount,
        "currency": currency,
    })
    
    return {
        "success": True,
        "message": f"Auto-renewal {'enabled' if enable else 'disabled'}",
        "auto_renewal_enabled": enable,
        "cancel_at_period_end": cancel_at_period_end
    }


@router.get("/subscription-history")
async def get_subscription_history(
    http_request: Request,
    _: None = Depends(verify_auth_token)
):
    """Get subscription payment history (invoices) for the user."""
    user = http_request.state.user
    user_id = user["id"]
    subscription = await get_user_subscription(user_id)
    
    if not subscription or not subscription.get("stripe_customer_id"):
        return {
            "success": True,
            "history": []
        }
    
    try:
        # Get invoices for this customer
        invoices = stripe.Invoice.list(
            customer=subscription["stripe_customer_id"],
            limit=50
        )
        
        history = []
        for invoice in invoices.data:
            history.append({
                "id": invoice.id,
                "amount": invoice.amount_paid / 100 if invoice.amount_paid else 0,
                "currency": invoice.currency.upper(),
                "status": invoice.status,
                "paid": invoice.paid,
                "date": datetime.fromtimestamp(invoice.created).isoformat() if invoice.created else None,
                "period_start": datetime.fromtimestamp(invoice.period_start).isoformat() if invoice.period_start else None,
                "period_end": datetime.fromtimestamp(invoice.period_end).isoformat() if invoice.period_end else None,
                "invoice_pdf": invoice.invoice_pdf,
                "hosted_invoice_url": invoice.hosted_invoice_url,
            })
        
        # Sort by date (newest first)
        history.sort(key=lambda x: x["date"] or "", reverse=True)
        
        return {
            "success": True,
            "history": history
        }
    except Exception as e:
        logger.error(f"Failed to fetch subscription history: {str(e)}")
        return {
            "success": False,
            "message": "Failed to fetch subscription history",
            "history": []
        }


@router.post("/create-portal-session")
async def create_portal_session(
    http_request: Request,
    _: None = Depends(verify_auth_token)
):
    """Create a Stripe customer portal session for managing subscription and payment methods."""
    user = http_request.state.user
    user_id = user["id"]
    subscription = await get_user_subscription(user_id)
    
    if not subscription or not subscription.get("stripe_customer_id"):
        raise HTTPException(status_code=404, detail="No subscription found")
    
    try:
        # Create a billing portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=subscription["stripe_customer_id"],
            return_url=f"{http_request.base_url}profile"
        )
        
        return {
            "success": True,
            "url": portal_session.url
        }
    except Exception as e:
        logger.error(f"Failed to create portal session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create portal session")


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
