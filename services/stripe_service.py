import stripe
import logging
import os
from db.supabase import supabase
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


async def create_subscription_checkout_session(
    user_id: str,
    user_email: str,
    success_url: str,
    cancel_url: str,
    price_id: str = None,
    amount: int = 4999
):
    """Create a Stripe checkout session for monthly subscription."""
    
    line_items = [{"price": price_id, "quantity": 1}] if price_id else [{
        "price_data": {
            "currency": "usd",
            "product_data": {
                "name": "Angel AI Premium",
                "description": "Monthly subscription for premium access to Angel AI"
            },
            "recurring": {"interval": "month"},
            "unit_amount": amount
        },
        "quantity": 1
    }]
    
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=cancel_url,
        customer_email=user_email,
        line_items=line_items,
        metadata={"user_id": user_id},
        subscription_data={"metadata": {"user_id": user_id}}
    )
    
    logger.info(f"Created subscription checkout session {session.id} for user {user_id}")
    return session


async def check_user_subscription_status(user_id: str) -> bool:
    """Check if user has an active subscription."""
    result = supabase.table("user_subscriptions").select("id").eq(
        "user_id", user_id
    ).eq(
        "subscription_status", "active"
    ).limit(1).execute()
    
    return len(result.data) > 0


async def get_user_subscription(user_id: str) -> dict:
    """Get user's active subscription."""
    result = supabase.table("user_subscriptions").select("*").eq(
        "user_id", user_id
    ).order("created_at", desc=True).limit(1).execute()
    
    return result.data[0] if result.data else None


async def create_or_update_subscription(user_id: str, subscription_data: dict):
    """Create or update subscription record."""
    subscription_record = {
            "user_id": user_id,
        "stripe_subscription_id": subscription_data["subscription_id"],
        "stripe_customer_id": subscription_data["customer_id"],
        "subscription_status": subscription_data["status"],
        "current_period_start": subscription_data["current_period_start"],
        "current_period_end": subscription_data["current_period_end"],
        "cancel_at_period_end": subscription_data.get("cancel_at_period_end", False),
        "amount": subscription_data.get("amount"),
        "currency": subscription_data.get("currency", "usd"),
            "updated_at": datetime.utcnow().isoformat()
        }
        
    existing = supabase.table("user_subscriptions").select("id").eq(
        "user_id", user_id
    ).limit(1).execute()
    
    if existing.data:
        result = supabase.table("user_subscriptions").update(subscription_record).eq(
            "user_id", user_id
        ).execute()
    else:
        subscription_record["created_at"] = datetime.utcnow().isoformat()
        result = supabase.table("user_subscriptions").insert(subscription_record).execute()
    
    logger.info(f"Subscription record updated for user {user_id}: {subscription_data['status']}")
    return result.data


async def handle_stripe_webhook(event: dict):
    """Handle Stripe webhook events for subscriptions."""
    event_type = event["type"]
    object_data = event["data"]["object"]
    
    logger.info(f"Processing Stripe webhook: {event_type}")
    
    handlers = {
        "checkout.session.completed": handle_checkout_completed,
        "customer.subscription.created": handle_subscription_created,
        "customer.subscription.updated": handle_subscription_updated,
        "customer.subscription.deleted": handle_subscription_deleted,
        "invoice.payment_succeeded": handle_invoice_payment_succeeded,
        "invoice.payment_failed": handle_invoice_payment_failed
    }
    
    handler = handlers.get(event_type)
    if handler:
        return await handler(object_data)
    
    logger.info(f"Unhandled event type: {event_type}")
    return {"status": "unhandled", "event_type": event_type}


async def handle_checkout_completed(session: dict):
    """Handle checkout.session.completed - subscription created."""
    user_id = session["metadata"]["user_id"]
    subscription_id = session.get("subscription")
    
    if subscription_id:
        subscription = stripe.Subscription.retrieve(subscription_id)
        await process_subscription(subscription, user_id)
        
        return {
            "status": "success",
        "event": "checkout.session.completed",
        "user_id": user_id,
        "subscription_id": subscription_id
    }


async def handle_subscription_created(subscription: dict):
    """Handle customer.subscription.created."""
    user_id = subscription["metadata"].get("user_id")
    if user_id:
        await process_subscription(subscription, user_id)
        
        return {
            "status": "success",
            "event": "customer.subscription.created",
        "subscription_id": subscription["id"]
    }


async def handle_subscription_updated(subscription: dict):
    """Handle customer.subscription.updated."""
    user_id = subscription["metadata"].get("user_id")
    if user_id:
        await process_subscription(subscription, user_id)
        
        return {
            "status": "success",
            "event": "customer.subscription.updated",
        "subscription_id": subscription["id"]
    }


async def handle_subscription_deleted(subscription: dict):
    """Handle customer.subscription.deleted - subscription cancelled."""
    user_id = subscription["metadata"].get("user_id")
    
    if user_id:
        subscription_data = {
            "subscription_id": subscription["id"],
            "customer_id": subscription["customer"],
            "status": "canceled",
            "current_period_start": datetime.fromtimestamp(subscription.get("current_period_start", 0)).isoformat() if subscription.get("current_period_start") else None,
            "current_period_end": datetime.fromtimestamp(subscription.get("current_period_end", 0)).isoformat() if subscription.get("current_period_end") else None,
            "cancel_at_period_end": False
        }
        await create_or_update_subscription(user_id, subscription_data)
    
    logger.info(f"Subscription canceled: {subscription['id']}")
    
    return {
        "status": "success",
        "event": "customer.subscription.deleted",
        "subscription_id": subscription["id"]
    }


async def handle_invoice_payment_succeeded(invoice: dict):
    """Handle invoice.payment_succeeded - monthly payment successful."""
    subscription_id = invoice.get("subscription")
    
    if subscription_id:
        subscription = stripe.Subscription.retrieve(subscription_id)
        user_id = subscription["metadata"].get("user_id")
        if user_id:
            await process_subscription(subscription, user_id)
    
    logger.info(f"Invoice payment succeeded: {invoice['id']}")
    
    return {
        "status": "success",
        "event": "invoice.payment_succeeded",
        "invoice_id": invoice["id"]
    }


async def handle_invoice_payment_failed(invoice: dict):
    """Handle invoice.payment_failed - monthly payment failed."""
    subscription_id = invoice.get("subscription")
    
    if subscription_id:
        subscription = stripe.Subscription.retrieve(subscription_id)
        user_id = subscription["metadata"].get("user_id")
        if user_id:
            subscription_data = {
                "subscription_id": subscription["id"],
                "customer_id": subscription["customer"],
                "status": "past_due",
                "current_period_start": datetime.fromtimestamp(subscription.get("current_period_start", 0)).isoformat() if subscription.get("current_period_start") else None,
                "current_period_end": datetime.fromtimestamp(subscription.get("current_period_end", 0)).isoformat() if subscription.get("current_period_end") else None,
                "cancel_at_period_end": False
            }
            await create_or_update_subscription(user_id, subscription_data)
    
    logger.warning(f"Invoice payment failed: {invoice['id']}")
    
    return {
        "status": "success",
        "event": "invoice.payment_failed",
        "invoice_id": invoice["id"]
    }


async def process_subscription(subscription: dict, user_id: str):
    """Process subscription data and update database."""
    items = subscription.get("items", {}).get("data", [])
    price = items[0].get("price") if items else {}
    amount = price.get("unit_amount", 0) if price else 0
    
    subscription_data = {
        "subscription_id": subscription["id"],
        "customer_id": subscription["customer"],
        "status": subscription["status"],
        "current_period_start": datetime.fromtimestamp(subscription["current_period_start"]).isoformat(),
        "current_period_end": datetime.fromtimestamp(subscription["current_period_end"]).isoformat(),
        "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
        "amount": amount / 100 if amount else None,
        "currency": price.get("currency", "usd") if price else "usd"
    }
    
    await create_or_update_subscription(user_id, subscription_data)
