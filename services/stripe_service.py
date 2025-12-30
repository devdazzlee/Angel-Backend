import stripe
import logging
import os
from db.supabase import supabase
from datetime import datetime
from dotenv import load_dotenv
from services.email_service import (
    send_subscription_confirmation_email,
    send_subscription_renewal_receipt_email,
    send_subscription_expiring_email,
    send_subscription_expired_email,
    send_billing_problem_email,
    send_subscription_cancellation_email,
    get_payment_method_last4
)

load_dotenv()

logger = logging.getLogger(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


async def create_subscription_checkout_session(
    user_id: str,
    user_email: str,
    success_url: str,
    cancel_url: str,
    price_id: str = None,
    amount: int = 2000  # $20/month in cents
):
    """Create a Stripe checkout session for monthly subscription."""
    
    line_items = [{"price": price_id, "quantity": 1}] if price_id else [{
        "price_data": {
            "currency": "usd",
            "product_data": {
                "name": "Founderport Premium",
                "description": "Monthly subscription for Founderport - Roadmapping and Implementation phases"
            },
            "recurring": {"interval": "month"},
            "unit_amount": amount  # $20/month
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
    """Check if user has an active subscription (active or trialing)."""
    # Check for active or trialing subscriptions
    result = supabase.table("user_subscriptions").select("id, subscription_status").eq(
        "user_id", user_id
    ).in_(
        "subscription_status", ["active", "trialing"]
    ).limit(1).execute()
    
    has_active = len(result.data) > 0
    if result.data:
        logger.info(f"User {user_id} subscription status: {result.data[0].get('subscription_status')}, has_active: {has_active}")
    else:
        logger.info(f"User {user_id} has no active/trialing subscription")
    
    return has_active


async def get_user_subscription(user_id: str) -> dict:
    """Get user's subscription (any status)."""
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
        
        # Send subscription confirmation email
        try:
            # Get user email
            user_response = supabase.auth.admin.get_user_by_id(user_id)
            if user_response and user_response.user and user_response.user.email:
                user_email = user_response.user.email
                
                # Get subscription details
                items = subscription.get("items", {}).get("data", [])
                price = items[0].get("price") if items else {}
                amount = (price.get("unit_amount", 0) / 100) if price else 0
                currency = price.get("currency", "usd") if price else "usd"
                
                # Get payment method last4
                customer_id = subscription.get("customer")
                last4 = await get_payment_method_last4(customer_id) if customer_id else None
                
                # Format dates
                period_start = datetime.fromtimestamp(subscription["current_period_start"]).isoformat()
                period_end = datetime.fromtimestamp(subscription["current_period_end"]).isoformat()
                
                await send_subscription_confirmation_email(
                    user_email=user_email,
                    amount=amount,
                    currency=currency,
                    subscription_start_date=period_start,
                    subscription_end_date=period_end,
                    last4=last4
                )
        except Exception as e:
            logger.error(f"Failed to send subscription confirmation email: {str(e)}")
        
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
        
        # Check if subscription is expiring (cancel_at_period_end is True)
        if subscription.get("cancel_at_period_end", False):
            try:
                user_response = supabase.auth.admin.get_user_by_id(user_id)
                if user_response and user_response.user and user_response.user.email:
                    user_email = user_response.user.email
                    period_end = datetime.fromtimestamp(subscription.get("current_period_end", 0)).isoformat() if subscription.get("current_period_end") else None
                    
                    if period_end:
                        await send_subscription_expiring_email(
                            user_email=user_email,
                            subscription_end_date=period_end
                        )
            except Exception as e:
                logger.error(f"Failed to send subscription expiring email: {str(e)}")
        
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
        
        # Send subscription expired email
        try:
            user_response = supabase.auth.admin.get_user_by_id(user_id)
            if user_response and user_response.user and user_response.user.email:
                user_email = user_response.user.email
                period_end = datetime.fromtimestamp(subscription.get("current_period_end", 0)).isoformat() if subscription.get("current_period_end") else None
                
                if period_end:
                    await send_subscription_expired_email(
                        user_email=user_email,
                        subscription_end_date=period_end
                    )
        except Exception as e:
            logger.error(f"Failed to send subscription expired email: {str(e)}")
    
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
            
            # Send renewal receipt email (only if not the first payment)
            try:
                # Check if this is a renewal (not initial subscription)
                # If subscription was created more than 1 day ago, it's a renewal
                subscription_created = datetime.fromtimestamp(subscription.get("created", 0))
                days_since_creation = (datetime.now() - subscription_created).days
                
                if days_since_creation > 1:  # This is a renewal
                    # Get user email
                    user_response = supabase.auth.admin.get_user_by_id(user_id)
                    if user_response and user_response.user and user_response.user.email:
                        user_email = user_response.user.email
                        
                        # Get invoice details
                        amount = (invoice.get("amount_paid", 0) / 100) if invoice.get("amount_paid") else 0
                        currency = invoice.get("currency", "usd")
                        
                        # Get payment method last4
                        customer_id = subscription.get("customer")
                        last4 = await get_payment_method_last4(customer_id) if customer_id else None
                        
                        # Format dates
                        period_start = datetime.fromtimestamp(subscription["current_period_start"]).isoformat()
                        period_end = datetime.fromtimestamp(subscription["current_period_end"]).isoformat()
                        
                        await send_subscription_renewal_receipt_email(
                            user_email=user_email,
                            amount=amount,
                            currency=currency,
                            subscription_start_date=period_start,
                            subscription_end_date=period_end,
                            last4=last4
                        )
            except Exception as e:
                logger.error(f"Failed to send renewal receipt email: {str(e)}")
    
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
            
            # Send billing problem email
            try:
                user_response = supabase.auth.admin.get_user_by_id(user_id)
                if user_response and user_response.user and user_response.user.email:
                    user_email = user_response.user.email
                    amount = (invoice.get("amount_due", 0) / 100) if invoice.get("amount_due") else 0
                    currency = invoice.get("currency", "usd")
                    invoice_url = invoice.get("hosted_invoice_url")
                    
                    await send_billing_problem_email(
                        user_email=user_email,
                        amount=amount,
                        currency=currency,
                        invoice_url=invoice_url
                    )
            except Exception as e:
                logger.error(f"Failed to send billing problem email: {str(e)}")
    
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
