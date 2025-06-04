# Ultra Civic Backend

This project uses SQLAlchemy with an async driver. Ensure your `DATABASE_URL` includes an async driver such as `postgresql+asyncpg`.

## Running the KYC flow locally

1. **Start the API**
   ```bash
   poetry run uvicorn app.main:app --reload
   ```
2. **Forward Stripe webhooks** (requires the Stripe CLI)
   ```bash
   stripe listen \
     --events identity.verification_session.verified \
     --forward-to localhost:8000/stripe/webhook
   ```
3. **Register and log in**
   ```bash
   http POST :8000/auth/register email=alice@test.com password=secret
   TOKEN=$(http -f POST :8000/auth/jwt/login \
              username=alice@test.com password=secret | jq -r .access_token)
   ```
4. **Kick off KYC**
   ```bash
   http POST :8000/kyc/start "Authorization: Bearer $TOKEN"
   ```
   Open the returned URL in your browser and click **Skip verification** in test mode.
5. **Confirm verification**
   - The Stripe CLI prints the webhook event.
   - The FastAPI server logs `user <id> marked verified`.
   - Query the database to see `kyc_status` set to `verified`.
