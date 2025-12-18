import stripe
import logging
import os
from db.supabase import supabase
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


async def create_checkout_session(
    user_id: str,
    user_email: str,
    success_url: str,
    cancel_url: str,
    product_name: str = "Angel AI Premium",
    amount: int = 4999,
    price_id: str = None
):
    """Create a Stripe checkout session for one-time payment."""
    
    line_items = [{"price": price_id, "quantity": 1}] if price_id else [{
        "price_data": {
            "currency": "usd",
            "product_data": {
                "name": product_name,
                "description": "One-time payment for premium access to Angel AI"
            },
            "unit_amount": amount
        },
        "quantity": 1
    }]
    
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=cancel_url,
        customer_email=user_email,
        line_items=line_items,
        metadata={"user_id": user_id, "product": product_name},
        payment_intent_data={"metadata": {"user_id": user_id, "product": product_name}}
    )
    
    logger.info(f"Created checkout session {session.id} for user {user_id}")
    return session


async def check_user_payment_status(user_id: str) -> bool:
    """Check if user has made a successful payment."""
    result = supabase.table("user_payments").select("id").eq(
        "user_id", user_id
    ).eq(
        "payment_status", "paid"
    ).limit(1).execute()
    
    return len(result.data) > 0


async def get_user_payments(user_id: str) -> list:
    """Get all payments for a user."""
    result = supabase.table("user_payments").select("*").eq(
        "user_id", user_id
    ).order("created_at", desc=True).execute()
    
    return result.data


async def grant_premium_access(user_id: str, payment_data: dict):
    """Grant premium access to user after successful payment."""
    payment_record = {
        "user_id": user_id,
        "stripe_session_id": payment_data["stripe_session_id"],
        "stripe_customer_id": payment_data["stripe_customer_id"],
        "stripe_payment_intent_id": payment_data["stripe_payment_intent_id"],
        "customer_email": payment_data["customer_email"],
        "amount": payment_data["amount"],
        "currency": payment_data["currency"],
        "payment_status": "paid",
        "product_name": payment_data["product_name"],
        "has_premium_access": True,
        "paid_at": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    result = supabase.table("user_payments").upsert(
        payment_record,
        on_conflict="user_id"
    ).execute()
    
    logger.info(f"Granted premium access to user {user_id}")
    return result.data


async def handle_stripe_webhook(event: dict):
    """Handle Stripe webhook events."""
    event_type = event["type"]
    object_data = event["data"]["object"]
    
    logger.info(f"Processing Stripe webhook: {event_type}")
    
    handlers = {
        "checkout.session.completed": handle_checkout_completed,
        "payment_intent.succeeded": handle_payment_succeeded,
        "payment_intent.payment_failed": handle_payment_failed
    }
    
    handler = handlers.get(event_type)
    if handler:
        return await handler(object_data)
    
    logger.info(f"Unhandled event type: {event_type}")
    return {"status": "unhandled", "event_type": event_type}


async def handle_checkout_completed(session: dict):
    """Handle checkout.session.completed - grants premium access."""
    user_id = session["metadata"]["user_id"]
    
    payment_data = {
        "stripe_session_id": session["id"],
        "stripe_customer_id": session.get("customer"),
        "stripe_payment_intent_id": session.get("payment_intent"),
        "customer_email": session.get("customer_email") or session.get("customer_details", {}).get("email"),
        "amount": session["amount_total"] / 100,
        "currency": session.get("currency", "usd"),
        "product_name": session["metadata"].get("product", "Angel AI Premium")
    }
    
    await grant_premium_access(user_id, payment_data)
    
    return {
        "status": "success",
        "event": "checkout.session.completed",
        "user_id": user_id,
        "premium_granted": True
    }


async def handle_payment_succeeded(payment_intent: dict):
    """Handle payment_intent.succeeded - confirms payment."""
    user_id = payment_intent["metadata"].get("user_id")
    
    if user_id:
        supabase.table("user_payments").update({
            "payment_status": "paid",
            "stripe_payment_intent_id": payment_intent["id"],
            "has_premium_access": True,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("user_id", user_id).execute()
    
    return {
        "status": "success",
        "event": "payment_intent.succeeded",
        "user_id": user_id
    }


async def handle_payment_failed(payment_intent: dict):
    """Handle payment_intent.payment_failed."""
    user_id = payment_intent["metadata"].get("user_id")
    
    if user_id:
        supabase.table("user_payments").update({
            "payment_status": "failed",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("user_id", user_id).execute()
    
    logger.warning(f"Payment failed for user {user_id}")
    
    return {
        "status": "success", 
        "event": "payment_intent.payment_failed",
        "user_id": user_id
    }
