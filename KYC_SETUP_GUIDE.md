# KYC Integration Setup & Testing Guide

This guide walks you through setting up and testing the complete Stripe Identity KYC integration.

## 🎯 Implementation Summary

The KYC integration includes:

### ✅ Backend Implementation (Complete)
- **POST /kyc/start** - Creates Stripe verification session, returns URL for frontend
- **POST /webhooks/stripe** - Handles webhook events with signature validation
- **Database schema** - Added `stripe_verification_session_id` for audit trail
- **Event handlers** - Process `verified`, `requires_input`, `canceled` events
- **Idempotent processing** - Duplicate events handled safely
- **KYC status updates** - Automatic user status changes via webhooks

### 🔧 External Setup Required

## 1. Stripe Configuration

### Get Your API Keys
```bash
# 1. Go to https://dashboard.stripe.com/test/apikeys
# 2. Copy your "Publishable key" and "Secret key"
# 3. Create a .env file with your keys:

cp .env.example .env
# Edit .env with your actual Stripe keys:
STRIPE_SECRET=sk_test_your_actual_stripe_test_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_actual_webhook_secret_here
```

### Enable Identity Verification
```bash
# 1. Go to https://dashboard.stripe.com/test/identity
# 2. Enable Identity verification for your account
# 3. Configure allowed document types (passport, ID, license)
```

## 2. Webhook Setup

### Option A: Using Stripe CLI (Recommended for Development)
```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe
# or download from https://github.com/stripe/stripe-cli

# Login with your API key
stripe login

# Start webhook forwarding
stripe listen --forward-to localhost:8000/webhooks/stripe

# Copy the webhook signing secret (starts with whsec_) to your .env file
```

### Option B: Using Docker Compose
```bash
# Set environment variables
export STRIPE_SECRET=sk_test_your_key_here
export STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# Start the app with Stripe CLI
docker-compose --profile webhook-testing up

# This starts:
# - PostgreSQL database
# - FastAPI app with KYC endpoints  
# - Stripe CLI forwarding webhooks
```

### Option C: Using ngrok (Alternative)
```bash
# Start your app
docker-compose up

# In another terminal, expose with ngrok
ngrok http 8000

# Configure webhook in Stripe Dashboard:
# 1. Go to https://dashboard.stripe.com/test/webhooks
# 2. Add endpoint: https://your-ngrok-url.ngrok.io/webhooks/stripe
# 3. Select events: identity.verification_session.*
# 4. Copy webhook signing secret to .env
```

## 3. Testing the Complete Flow

### Start the Application
```bash
# Option 1: Docker (recommended)
docker-compose up

# Option 2: Local development
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

### Test KYC Flow

#### 1. Register a User
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123"
  }'
```

#### 2. Login to Get JWT Token
```bash
TOKEN=$(curl -X POST http://localhost:8000/auth/jwt/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=testpass123" | \
  jq -r '.access_token')
```

#### 3. Start KYC Verification
```bash
curl -X POST http://localhost:8000/kyc/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Returns: {"url": "https://verify.stripe.com/start/..."}
# Open this URL in browser to complete verification
```

#### 4. Test Verification Gate
```bash
# Before verification - should return 403
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/auth/test-verified

# After verification - should return success
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/kyc/verified-only
```

## 4. Testing Webhook Events

### Manual Event Triggering
```bash
# Trigger verification success
stripe trigger identity.verification_session.verified

# Trigger verification failure  
stripe trigger identity.verification_session.requires_input

# Trigger verification cancellation
stripe trigger identity.verification_session.canceled
```

### Verify Idempotency
```bash
# Send the same webhook event twice
stripe trigger identity.verification_session.verified
stripe trigger identity.verification_session.verified

# Check logs - second event should be marked as "already_processed"
```

## 5. Monitoring & Debugging

### Check Application Logs
```bash
# Docker logs
docker-compose logs -f app

# Local logs - look for these messages:
# "Created verification session vs_xxx for user xxx"
# "Processing webhook event: identity.verification_session.verified"
# "Updated user xxx KYC status to verified"
```

### Check Database Status
```bash
# Connect to database
docker-compose exec db psql -U ultracivic ultracivic

# Check user KYC status
SELECT id, email, kyc_status, stripe_verification_session_id 
FROM "user" 
ORDER BY created_at DESC;
```

### Stripe Dashboard Monitoring
- **Events**: https://dashboard.stripe.com/test/events
- **Identity**: https://dashboard.stripe.com/test/identity  
- **Webhooks**: https://dashboard.stripe.com/test/webhooks

## 6. Production Deployment

### Environment Variables
```bash
# Production .env
DATABASE_URL=postgresql+asyncpg://user:pass@prod-db:5432/ultracivic
DATABASE_URL_SYNC=postgresql://user:pass@prod-db:5432/ultracivic
JWT_SECRET=your-super-secure-jwt-secret-32-chars-min
STRIPE_SECRET=sk_live_your_production_stripe_secret
STRIPE_WEBHOOK_SECRET=whsec_your_production_webhook_secret
ENVIRONMENT=production
```

### Webhook Endpoint Configuration
- Configure webhook endpoint: `https://your-domain.com/webhooks/stripe`
- Subscribe to events: `identity.verification_session.*`
- Ensure webhook secret matches your environment

## 🎉 Success Criteria

Your KYC integration is working correctly when:

✅ **POST /kyc/start** creates verification sessions and returns URLs  
✅ **Webhook events** are received and processed correctly  
✅ **User KYC status** updates automatically based on verification results  
✅ **Verification gate** blocks unverified users with 403 responses  
✅ **Idempotent processing** handles duplicate events without side effects  
✅ **Audit trail** maintains session IDs for debugging and compliance  

## 🔍 Troubleshooting

### Common Issues

**Webhook signature validation fails**
- Verify `STRIPE_WEBHOOK_SECRET` matches your endpoint secret
- Check webhook endpoint URL is correct
- Ensure payload is not modified in transit

**Verification sessions fail to create**  
- Verify `STRIPE_SECRET` is valid and has Identity enabled
- Check Stripe Identity is enabled for your account
- Ensure test mode is configured correctly

**KYC status not updating**
- Check webhook events are being received
- Verify user UUIDs match between session and webhook
- Check database connectivity and transaction commits

**Docker issues**
- Ensure environment variables are exported before `docker-compose up`
- Check that ports 5432 and 8000 are available
- Verify Docker has sufficient resources allocated