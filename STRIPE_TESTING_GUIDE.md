# Stripe Payment Testing Guide

## 🔍 Current Mode: **TEST/SANDBOX MODE**

Your Stripe integration is currently configured in **TEST MODE** (sandbox).

**Evidence:**
- ✅ Secret Key starts with `sk_test_` (not `sk_live_`)
- ✅ Publishable Key starts with `pk_test_` (not `pk_live_`)
- ✅ Webhook secret starts with `whsec_` (works for both test and live)

**This means:**
- ✅ No real money will be charged
- ✅ All transactions are simulated
- ✅ Perfect for testing before going live

---

## 🧪 How to Test Payments

### **Test Card Numbers (Stripe Test Mode)**

Use these test card numbers in the Stripe checkout form:

#### **✅ Successful Payment Cards:**

| Card Number | Description |
|-------------|-------------|
| `4242 4242 4242 4242` | Visa - Always succeeds |
| `5555 5555 5555 4444` | Mastercard - Always succeeds |
| `4000 0000 0000 0002` | Visa - Always succeeds |
| `4000 0025 0000 3155` | Visa - Requires 3D Secure (authentication) |

#### **❌ Failed Payment Cards:**

| Card Number | Description |
|-------------|-------------|
| `4000 0000 0000 0002` | Card declined |
| `4000 0000 0000 9995` | Insufficient funds |
| `4000 0000 0000 0069` | Expired card |

#### **📋 Test Card Details (Use for ALL test cards):**

- **Expiry Date:** Any future date (e.g., `12/34`)
- **CVC:** Any 3 digits (e.g., `123`)
- **ZIP Code:** Any 5 digits (e.g., `12345`)
- **Name:** Any name (e.g., `Test User`)

---

## 🚀 Testing Steps

### **1. Create a Subscription**

**API Endpoint:**
```bash
POST /stripe/create-subscription
Authorization: Bearer <your-auth-token>
Content-Type: application/json

{
  "success_url": "https://yoursite.com/success",
  "cancel_url": "https://yoursite.com/cancel",
  "amount": 4999  // $49.99/month
}
```

**Response:**
```json
{
  "success": true,
  "checkout_url": "https://checkout.stripe.com/c/pay/...",
  "session_id": "cs_test_..."
}
```

### **2. Complete Checkout**

1. Click the `checkout_url` from the response
2. Use test card: `4242 4242 4242 4242`
3. Enter any future expiry date, CVC, and ZIP
4. Click "Subscribe"

### **3. Verify Subscription Status**

**API Endpoint:**
```bash
GET /stripe/check-subscription-status
Authorization: Bearer <your-auth-token>
```

**Response:**
```json
{
  "success": true,
  "has_active_subscription": true,
  "can_download": true,
  "subscription": {
    "subscription_status": "active",
    "current_period_end": "2024-02-10T12:00:00Z",
    "amount": 49.99
  }
}
```

### **4. Test Monthly Auto-Charge**

Stripe will automatically simulate monthly charges. To test this:

1. Go to Stripe Dashboard → **Test Mode** → **Subscriptions**
2. Find your test subscription
3. Click **"..."** → **"Advance subscription"**
4. This simulates the next billing cycle

**Or use Stripe CLI:**
```bash
stripe subscriptions update sub_test_xxx --billing-cycle-anchor now
```

---

## 🔔 Testing Webhooks Locally

### **Using Stripe CLI:**

1. **Install Stripe CLI:**
   ```bash
   # macOS
   brew install stripe/stripe-cli/stripe
   
   # Or download from: https://stripe.com/docs/stripe-cli
   ```

2. **Login:**
   ```bash
   stripe login
   ```

3. **Forward webhooks to local server:**
   ```bash
   stripe listen --forward-to localhost:8000/stripe/webhook
   ```

4. **Trigger test events:**
   ```bash
   # Test subscription created
   stripe trigger checkout.session.completed
   
   # Test payment succeeded
   stripe trigger invoice.payment_succeeded
   
   # Test payment failed
   stripe trigger invoice.payment_failed
   ```

---

## 📊 View Test Data in Stripe Dashboard

1. Go to: https://dashboard.stripe.com/test
2. Make sure you're in **"Test mode"** (toggle in top right)
3. View:
   - **Customers** - Test customers created
   - **Subscriptions** - Test subscriptions
   - **Payments** - Test payment attempts
   - **Webhooks** - Webhook event logs

---

## 🔄 Switching to Live Mode

When ready for production:

### **1. Get Live Keys from Stripe:**

1. Go to: https://dashboard.stripe.com/apikeys
2. Switch to **"Live mode"** (toggle in top right)
3. Copy:
   - **Publishable key** (starts with `pk_live_`)
   - **Secret key** (starts with `sk_live_`)

### **2. Update Environment Variables:**

**In `.env` file:**
```bash
STRIPE_PUBLISHABLE_KEY=pk_live_YOUR_LIVE_KEY
STRIPE_SECRET_KEY=sk_live_YOUR_LIVE_KEY
STRIPE_WEBHOOK_SECRET=whsec_YOUR_LIVE_WEBHOOK_SECRET
```

**In Vercel (Production):**
1. Go to Vercel Dashboard → Your Project → Settings → Environment Variables
2. Update:
   - `STRIPE_SECRET_KEY` → Live secret key
   - `STRIPE_WEBHOOK_SECRET` → Live webhook secret

### **3. Update Webhook in Stripe:**

1. Go to: https://dashboard.stripe.com/webhooks
2. Switch to **"Live mode"**
3. Create new webhook endpoint:
   - **URL:** `https://angel-backend.vercel.app/stripe/webhook`
   - **Events to listen for:**
     - `checkout.session.completed`
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_succeeded`
     - `invoice.payment_failed`
4. Copy the **Signing secret** (starts with `whsec_`)
5. Update `STRIPE_WEBHOOK_SECRET` in Vercel

### **4. Test Live Mode:**

⚠️ **WARNING:** Live mode charges REAL money!

1. Use a small test amount first
2. Use a real card you control
3. Monitor transactions closely
4. Have refund process ready

---

## 🧪 Quick Test Checklist

- [ ] Create subscription with test card `4242 4242 4242 4242`
- [ ] Verify subscription status shows `active`
- [ ] Check database has subscription record
- [ ] Test webhook receives `checkout.session.completed`
- [ ] Test monthly auto-charge (advance subscription)
- [ ] Test payment failure with card `4000 0000 0000 0002`
- [ ] Test subscription cancellation
- [ ] Verify download access is granted after payment

---

## 📝 Test Card Reference

**Full list:** https://stripe.com/docs/testing

**Common Test Cards:**
- `4242 4242 4242 4242` - Success (Visa)
- `5555 5555 5555 4444` - Success (Mastercard)
- `4000 0000 0000 0002` - Declined
- `4000 0000 0000 9995` - Insufficient funds
- `4000 0025 0000 3155` - Requires 3D Secure

**All test cards use:**
- Expiry: Any future date
- CVC: Any 3 digits
- ZIP: Any 5 digits

---

## 🆘 Troubleshooting

### **Webhook not receiving events:**
1. Check webhook URL is correct
2. Verify webhook secret matches
3. Check Stripe Dashboard → Webhooks → Event logs
4. Test with Stripe CLI locally

### **Subscription not activating:**
1. Check database `user_subscriptions` table
2. Verify webhook events are being processed
3. Check backend logs for errors
4. Verify user_id in subscription metadata

### **Payment failing:**
1. Check card number is valid test card
2. Verify amount is correct (in cents)
3. Check Stripe Dashboard for error details
4. Review webhook event logs

---

## ✅ Current Configuration Summary

- **Mode:** TEST/SANDBOX ✅
- **Secret Key:** `sk_test_...` ✅
- **Publishable Key:** `pk_test_...` ✅
- **Webhook Secret:** `whsec_...` ✅
- **Webhook URL:** `https://angel-backend.vercel.app/stripe/webhook` ✅

**You're all set for testing!** 🎉

