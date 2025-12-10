# Stripe Webhook Setup Guide

## Webhook Endpoint URL

**Production:**
```
https://your-domain.com/stripe/webhook
```

**Local Development:**
```
http://localhost:8000/stripe/webhook
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install `stripe==10.5.0`.

### 2. Environment Variables

Add these to your `.env` file:

```env
STRIPE_SECRET_KEY=sk_test_...  # Your Stripe secret key
STRIPE_WEBHOOK_SECRET=whsec_...  # Your webhook signing secret from Stripe Dashboard
```

### 3. Database Setup

Create a `payments` table in Supabase:

```sql
CREATE TABLE IF NOT EXISTS payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stripe_session_id TEXT UNIQUE,
  stripe_customer_id TEXT,
  stripe_payment_intent_id TEXT,
  customer_email TEXT,
  amount DECIMAL(10, 2),
  currency TEXT DEFAULT 'usd',
  payment_status TEXT,
  user_id TEXT,
  custom_session_id TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payments_stripe_session_id ON payments(stripe_session_id);
CREATE INDEX IF NOT EXISTS idx_payments_stripe_customer_id ON payments(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
```

### 4. Add Webhook to Stripe Dashboard

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/webhooks)
2. Click "Add endpoint"
3. Enter your webhook URL: `https://your-domain.com/stripe/webhook`
4. Select events to listen for:
   - `checkout.session.completed`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
5. Copy the "Signing secret" (starts with `whsec_`)
6. Add it to your `.env` as `STRIPE_WEBHOOK_SECRET`

### 5. Test the Webhook

**Test endpoint:**
```
GET /stripe/webhook-test
```

**Local testing with Stripe CLI:**
```bash
stripe listen --forward-to localhost:8000/stripe/webhook
```

This will give you a webhook signing secret for local testing.

## Supported Events

The webhook handles these Stripe events:

- ✅ `checkout.session.completed` - When customer completes checkout
- ✅ `payment_intent.succeeded` - When payment succeeds
- ✅ `payment_intent.payment_failed` - When payment fails
- ✅ `customer.subscription.created` - When subscription is created
- ✅ `customer.subscription.updated` - When subscription is updated
- ✅ `customer.subscription.deleted` - When subscription is deleted

## Metadata Support

When creating a checkout session, you can pass metadata:

```python
session = stripe.checkout.Session.create(
    # ... other params
    metadata={
        "user_id": "user_123",
        "session_id": "session_456"
    }
)
```

This metadata will be stored in the payment record.

## API Endpoints

- `POST /stripe/webhook` - Main webhook endpoint (used by Stripe)
- `GET /stripe/webhook-test` - Test endpoint to verify route is working







