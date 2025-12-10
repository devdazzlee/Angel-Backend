from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import Response
import stripe
import os
from dotenv import load_dotenv
import logging
from services.stripe_service import handle_stripe_webhook

load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe webhook endpoint for handling checkout events.
    
    Add this URL to your Stripe Dashboard:
    https://your-domain.com/stripe/webhook
    
    Or for local testing with Stripe CLI:
    stripe listen --forward-to localhost:8000/stripe/webhook
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        if not sig_header:
            logger.error("Missing stripe-signature header")
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")
        
        if not STRIPE_WEBHOOK_SECRET:
            logger.error("STRIPE_WEBHOOK_SECRET not configured")
            raise HTTPException(status_code=500, detail="Webhook secret not configured")
        
        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                body, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Handle the event
        result = await handle_stripe_webhook(event)
        
        return {"success": True, "message": "Webhook processed", "result": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

@router.get("/webhook-test")
async def webhook_test():
    """
    Test endpoint to verify webhook route is accessible.
    """
    return {
        "success": True,
        "message": "Stripe webhook endpoint is active",
        "webhook_url": "/stripe/webhook",
        "instructions": "Add this URL to Stripe Dashboard: https://your-domain.com/stripe/webhook"
    }







