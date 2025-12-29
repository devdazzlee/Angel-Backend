import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from db.supabase import supabase
import stripe
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


async def send_subscription_confirmation_email(
    user_email: str,
    amount: float,
    currency: str,
    subscription_start_date: str,
    subscription_end_date: str,
    last4: Optional[str] = None
):
    """Send subscription confirmation email when subscription is activated."""
    try:
        # Calculate subscription length in days
        # Handle both ISO format strings and datetime objects
        if isinstance(subscription_start_date, str):
            start = datetime.fromisoformat(subscription_start_date.replace('Z', '+00:00').replace('+00:00', ''))
        else:
            start = subscription_start_date
        
        if isinstance(subscription_end_date, str):
            end = datetime.fromisoformat(subscription_end_date.replace('Z', '+00:00').replace('+00:00', ''))
        else:
            end = subscription_end_date
        
        days = (end - start).days
        
        # Format dates for display
        start_formatted = start.strftime("%B %d, %Y")
        end_formatted = end.strftime("%B %d, %Y")
        
        # Format amount
        amount_formatted = f"${amount:.2f}" if currency.lower() == "usd" else f"{amount:.2f} {currency.upper()}"
        
        subject = "Subscription Confirmation - Angel AI Premium"
        
        # Build email body
        card_info = f"\nCard ending in: {last4}" if last4 else ""
        
        body = f"""
Monthly subscription activated

Dear User,

Your Angel AI Premium subscription has been successfully activated.

Subscription Details:
- Amount: {amount_formatted}
- Start Date: {start_formatted}
- End Date: {end_formatted}
- Length: {days} days{card_info}

Thank you for subscribing to Angel AI Premium!

Best regards,
Angel AI Team
"""
        
        # Use Supabase to send email (if configured) or log for now
        # Note: You may need to configure Supabase email service or use a third-party service
        logger.info(f"Sending subscription confirmation email to {user_email}")
        logger.info(f"Email subject: {subject}")
        logger.info(f"Email body: {body}")
        
        # TODO: Integrate with actual email service (SendGrid, AWS SES, etc.)
        # For now, we'll log it. You can add actual email sending here.
        
        return {"success": True, "email": user_email}
        
    except Exception as e:
        logger.error(f"Failed to send subscription confirmation email: {str(e)}")
        return {"success": False, "error": str(e)}


async def send_subscription_renewal_receipt_email(
    user_email: str,
    amount: float,
    currency: str,
    subscription_start_date: str,
    subscription_end_date: str,
    last4: Optional[str] = None
):
    """Send receipt email when subscription renews monthly."""
    try:
        # Calculate subscription length in days
        # Handle both ISO format strings and datetime objects
        if isinstance(subscription_start_date, str):
            start = datetime.fromisoformat(subscription_start_date.replace('Z', '+00:00').replace('+00:00', ''))
        else:
            start = subscription_start_date
        
        if isinstance(subscription_end_date, str):
            end = datetime.fromisoformat(subscription_end_date.replace('Z', '+00:00').replace('+00:00', ''))
        else:
            end = subscription_end_date
        
        days = (end - start).days
        
        # Format dates for display
        start_formatted = start.strftime("%B %d, %Y")
        end_formatted = end.strftime("%B %d, %Y")
        
        # Format amount
        amount_formatted = f"${amount:.2f}" if currency.lower() == "usd" else f"{amount:.2f} {currency.upper()}"
        
        subject = "Subscription Renewal Receipt - Angel AI Premium"
        
        # Build email body
        card_info = f"\nCard ending in: {last4}" if last4 else ""
        
        body = f"""
Monthly subscription renewal receipt

Dear User,

Your Angel AI Premium subscription has been renewed.

Renewal Details:
- Amount: {amount_formatted}
- Start Date: {start_formatted}
- End Date: {end_formatted}
- Length: {days} days{card_info}

This is your receipt for the renewal payment.

Thank you for continuing with Angel AI Premium!

Best regards,
Angel AI Team
"""
        
        logger.info(f"Sending subscription renewal receipt email to {user_email}")
        logger.info(f"Email subject: {subject}")
        logger.info(f"Email body: {body}")
        
        return {"success": True, "email": user_email}
        
    except Exception as e:
        logger.error(f"Failed to send subscription renewal receipt email: {str(e)}")
        return {"success": False, "error": str(e)}


async def send_subscription_expiring_email(
    user_email: str,
    subscription_end_date: str
):
    """Send email when subscription is expiring soon."""
    try:
        # Format date for display
        if isinstance(subscription_end_date, str):
            end = datetime.fromisoformat(subscription_end_date.replace('Z', '+00:00').replace('+00:00', ''))
        else:
            end = subscription_end_date
        end_formatted = end.strftime("%B %d, %Y")
        
        subject = "Subscription Expiring Soon - Angel AI Premium"
        
        body = f"""
Subscription Expiring Soon

Dear User,

Your Angel AI Premium subscription is set to expire on {end_formatted}.

To continue enjoying premium features, please renew your subscription before it expires.

If you have any questions, please contact our support team.

Best regards,
Angel AI Team
"""
        
        logger.info(f"Sending subscription expiring email to {user_email}")
        logger.info(f"Email subject: {subject}")
        logger.info(f"Email body: {body}")
        
        return {"success": True, "email": user_email}
        
    except Exception as e:
        logger.error(f"Failed to send subscription expiring email: {str(e)}")
        return {"success": False, "error": str(e)}


async def send_subscription_expired_email(
    user_email: str,
    subscription_end_date: str
):
    """Send email when subscription has expired."""
    try:
        # Format date for display
        if isinstance(subscription_end_date, str):
            end = datetime.fromisoformat(subscription_end_date.replace('Z', '+00:00').replace('+00:00', ''))
        else:
            end = subscription_end_date
        end_formatted = end.strftime("%B %d, %Y")
        
        subject = "Subscription Expired - Angel AI Premium"
        
        body = f"""
Subscription Expired

Dear User,

Your Angel AI Premium subscription has expired on {end_formatted}.

To continue using premium features, please renew your subscription.

If you have any questions, please contact our support team.

Best regards,
Angel AI Team
"""
        
        logger.info(f"Sending subscription expired email to {user_email}")
        logger.info(f"Email subject: {subject}")
        logger.info(f"Email body: {body}")
        
        return {"success": True, "email": user_email}
        
    except Exception as e:
        logger.error(f"Failed to send subscription expired email: {str(e)}")
        return {"success": False, "error": str(e)}


async def send_billing_problem_email(
    user_email: str,
    amount: float,
    currency: str,
    invoice_url: Optional[str] = None
):
    """Send email when there's a billing problem (payment failed)."""
    try:
        # Format amount
        amount_formatted = f"${amount:.2f}" if currency.lower() == "usd" else f"{amount:.2f} {currency.upper()}"
        
        subject = "Billing Problem - Angel AI Premium"
        
        # Build email body
        invoice_link = f"\n\nPlease update your payment method here: {invoice_url}" if invoice_url else ""
        
        body = f"""
Billing Problem

Dear User,

We encountered a problem processing your payment for Angel AI Premium.

Amount: {amount_formatted}

Please update your payment method to continue your subscription. Your access may be limited until payment is successful.{invoice_link}

If you have any questions, please contact our support team.

Best regards,
Angel AI Team
"""
        
        logger.info(f"Sending billing problem email to {user_email}")
        logger.info(f"Email subject: {subject}")
        logger.info(f"Email body: {body}")
        
        return {"success": True, "email": user_email}
        
    except Exception as e:
        logger.error(f"Failed to send billing problem email: {str(e)}")
        return {"success": False, "error": str(e)}


async def send_subscription_cancellation_email(
    user_email: str,
    subscription_end_date: str
):
    """Send email when subscription is cancelled."""
    try:
        # Format date for display
        if isinstance(subscription_end_date, str):
            end = datetime.fromisoformat(subscription_end_date.replace('Z', '+00:00').replace('+00:00', ''))
        else:
            end = subscription_end_date
        end_formatted = end.strftime("%B %d, %Y")
        
        subject = "Subscription Cancellation - Angel AI Premium"
        
        body = f"""
Subscription Cancellation

Dear User,

Your Angel AI Premium subscription has been cancelled and will end on {end_formatted}.

You will continue to have access to premium features until {end_formatted}.

We're sorry to see you go! If you change your mind, you can reactivate your subscription anytime.

If you have any questions, please contact our support team.

Best regards,
Angel AI Team
"""
        
        logger.info(f"Sending subscription cancellation email to {user_email}")
        logger.info(f"Email subject: {subject}")
        logger.info(f"Email body: {body}")
        
        return {"success": True, "email": user_email}
        
    except Exception as e:
        logger.error(f"Failed to send subscription cancellation email: {str(e)}")
        return {"success": False, "error": str(e)}


async def get_payment_method_last4(customer_id: str) -> Optional[str]:
    """Get last 4 digits of customer's payment method."""
    try:
        customer = stripe.Customer.retrieve(customer_id)
        if hasattr(customer, 'invoice_settings') and customer.invoice_settings.default_payment_method:
            payment_method = stripe.PaymentMethod.retrieve(customer.invoice_settings.default_payment_method)
            if hasattr(payment_method, 'card') and payment_method.card:
                return payment_method.card.last4
        # Try to get from payment methods list
        payment_methods = stripe.PaymentMethod.list(customer=customer_id, type="card", limit=1)
        if payment_methods.data and len(payment_methods.data) > 0:
            if hasattr(payment_methods.data[0], 'card') and payment_methods.data[0].card:
                return payment_methods.data[0].card.last4
        return None
    except Exception as e:
        logger.warning(f"Could not retrieve payment method last4: {str(e)}")
        return None

