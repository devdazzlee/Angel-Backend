import stripe
import logging
from db.supabase import supabase
from datetime import datetime

logger = logging.getLogger(__name__)

async def handle_stripe_webhook(event):
    """
    Handle Stripe webhook events.
    
    Supported events:
    - checkout.session.completed: When a customer completes a checkout
    - payment_intent.succeeded: When a payment is successful
    - payment_intent.payment_failed: When a payment fails
    - customer.subscription.created: When a subscription is created
    - customer.subscription.updated: When a subscription is updated
    - customer.subscription.deleted: When a subscription is deleted
    """
    event_type = event.get("type")
    data = event.get("data", {})
    object_data = data.get("object", {})
    
    logger.info(f"Processing Stripe webhook event: {event_type}")
    
    try:
        if event_type == "checkout.session.completed":
            return await handle_checkout_completed(object_data)
        
        elif event_type == "payment_intent.succeeded":
            return await handle_payment_succeeded(object_data)
        
        elif event_type == "payment_intent.payment_failed":
            return await handle_payment_failed(object_data)
        
        elif event_type == "customer.subscription.created":
            return await handle_subscription_created(object_data)
        
        elif event_type == "customer.subscription.updated":
            return await handle_subscription_updated(object_data)
        
        elif event_type == "customer.subscription.deleted":
            return await handle_subscription_deleted(object_data)
        
        else:
            logger.info(f"Unhandled event type: {event_type}")
            return {
                "status": "unhandled",
                "event_type": event_type,
                "message": f"Event type {event_type} is not handled"
            }
    
    except Exception as e:
        logger.error(f"Error handling webhook event {event_type}: {e}")
        raise

async def handle_checkout_completed(session):
    """
    Handle checkout.session.completed event.
    This is triggered when a customer successfully completes a checkout session.
    """
    try:
        customer_id = session.get("customer")
        customer_email = session.get("customer_email")
        amount_total = session.get("amount_total", 0) / 100  # Convert from cents
        currency = session.get("currency", "usd")
        payment_status = session.get("payment_status")
        session_id = session.get("id")
        metadata = session.get("metadata", {})
        
        # Extract user/session info from metadata if provided
        user_id = metadata.get("user_id")
        session_id_custom = metadata.get("session_id")
        
        logger.info(f"Checkout completed - Session: {session_id}, Customer: {customer_email}, Amount: {amount_total} {currency}")
        
        # Store payment record in database
        payment_data = {
            "stripe_session_id": session_id,
            "stripe_customer_id": customer_id,
            "customer_email": customer_email,
            "amount": amount_total,
            "currency": currency,
            "payment_status": payment_status,
            "user_id": user_id,
            "custom_session_id": session_id_custom,
            "metadata": metadata,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Insert into payments table (create table if it doesn't exist)
        try:
            result = supabase.table("payments").insert(payment_data).execute()
            logger.info(f"Payment record created: {result.data}")
        except Exception as db_error:
            logger.error(f"Database error storing payment: {db_error}")
            # Continue even if DB insert fails - webhook should still return success
        
        return {
            "status": "success",
            "event": "checkout.session.completed",
            "session_id": session_id,
            "customer_email": customer_email,
            "amount": amount_total,
            "currency": currency,
            "message": "Checkout completed successfully"
        }
    
    except Exception as e:
        logger.error(f"Error handling checkout completed: {e}")
        raise

async def handle_payment_succeeded(payment_intent):
    """
    Handle payment_intent.succeeded event.
    """
    try:
        payment_id = payment_intent.get("id")
        amount = payment_intent.get("amount", 0) / 100
        currency = payment_intent.get("currency", "usd")
        customer_id = payment_intent.get("customer")
        
        logger.info(f"Payment succeeded - Payment ID: {payment_id}, Amount: {amount} {currency}")
        
        # Update payment status if record exists
        try:
            supabase.table("payments").update({
                "payment_status": "paid",
                "stripe_payment_intent_id": payment_id,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("stripe_customer_id", customer_id).execute()
        except Exception as db_error:
            logger.error(f"Database error updating payment: {db_error}")
        
        return {
            "status": "success",
            "event": "payment_intent.succeeded",
            "payment_id": payment_id,
            "amount": amount,
            "currency": currency
        }
    
    except Exception as e:
        logger.error(f"Error handling payment succeeded: {e}")
        raise

async def handle_payment_failed(payment_intent):
    """
    Handle payment_intent.payment_failed event.
    """
    try:
        payment_id = payment_intent.get("id")
        amount = payment_intent.get("amount", 0) / 100
        currency = payment_intent.get("currency", "usd")
        customer_id = payment_intent.get("customer")
        
        logger.warning(f"Payment failed - Payment ID: {payment_id}, Amount: {amount} {currency}")
        
        # Update payment status if record exists
        try:
            supabase.table("payments").update({
                "payment_status": "failed",
                "stripe_payment_intent_id": payment_id,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("stripe_customer_id", customer_id).execute()
        except Exception as db_error:
            logger.error(f"Database error updating payment: {db_error}")
        
        return {
            "status": "success",
            "event": "payment_intent.payment_failed",
            "payment_id": payment_id,
            "message": "Payment failure recorded"
        }
    
    except Exception as e:
        logger.error(f"Error handling payment failed: {e}")
        raise

async def handle_subscription_created(subscription):
    """
    Handle customer.subscription.created event.
    """
    try:
        subscription_id = subscription.get("id")
        customer_id = subscription.get("customer")
        status = subscription.get("status")
        
        logger.info(f"Subscription created - Subscription ID: {subscription_id}, Status: {status}")
        
        return {
            "status": "success",
            "event": "customer.subscription.created",
            "subscription_id": subscription_id,
            "customer_id": customer_id,
            "status": status
        }
    
    except Exception as e:
        logger.error(f"Error handling subscription created: {e}")
        raise

async def handle_subscription_updated(subscription):
    """
    Handle customer.subscription.updated event.
    """
    try:
        subscription_id = subscription.get("id")
        status = subscription.get("status")
        
        logger.info(f"Subscription updated - Subscription ID: {subscription_id}, Status: {status}")
        
        return {
            "status": "success",
            "event": "customer.subscription.updated",
            "subscription_id": subscription_id,
            "status": status
        }
    
    except Exception as e:
        logger.error(f"Error handling subscription updated: {e}")
        raise

async def handle_subscription_deleted(subscription):
    """
    Handle customer.subscription.deleted event.
    """
    try:
        subscription_id = subscription.get("id")
        
        logger.info(f"Subscription deleted - Subscription ID: {subscription_id}")
        
        return {
            "status": "success",
            "event": "customer.subscription.deleted",
            "subscription_id": subscription_id
        }
    
    except Exception as e:
        logger.error(f"Error handling subscription deleted: {e}")
        raise

