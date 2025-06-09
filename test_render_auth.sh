#!/bin/bash

# Test script for Render auth flow
API_BASE="https://ultracivic-backend.onrender.com"
TEST_EMAIL="test-$(date +%s)@example.com"  # Unique email
TEST_PASSWORD="testpass123"

echo "🚀 Testing Ultra Civic auth flow on Render..."
echo "API Base: $API_BASE"
echo "Test Email: $TEST_EMAIL"
echo

# Step 1: Test health endpoint
echo "1️⃣ Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s "$API_BASE/health")
echo "Response: $HEALTH_RESPONSE"
if [[ $HEALTH_RESPONSE == *'"status":"ok"'* ]]; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    exit 1
fi
echo

# Step 2: Test user registration
echo "2️⃣ Testing user registration..."
REGISTER_RESPONSE=$(curl -s -X POST "$API_BASE/auth/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$TEST_PASSWORD\",
    \"is_active\": true,
    \"is_verified\": false
  }")

echo "Response: $REGISTER_RESPONSE"
if [[ $REGISTER_RESPONSE == *'"email"'* ]]; then
    echo "✅ Registration successful"
else
    echo "❌ Registration failed"
    exit 1
fi
echo

# Step 3: Test user login
echo "3️⃣ Testing user login..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_BASE/auth/jwt/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$TEST_EMAIL&password=$TEST_PASSWORD")

echo "Response: $LOGIN_RESPONSE"
TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [[ -n "$TOKEN" ]]; then
    echo "✅ Login successful"
    echo "Token: ${TOKEN:0:20}..."
else
    echo "❌ Login failed"
    exit 1
fi
echo

# Step 4: Test authenticated endpoint
echo "4️⃣ Testing authenticated endpoint (/me)..."
ME_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$API_BASE/me")
echo "Response: $ME_RESPONSE"
if [[ $ME_RESPONSE == *'"email"'* ]]; then
    echo "✅ Authenticated endpoint works"
else
    echo "❌ Authentication failed"
    exit 1
fi
echo

# Step 5: Test verification gate (should fail)
echo "5️⃣ Testing verification gate (should return 403)..."
VERIFY_RESPONSE=$(curl -s -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$API_BASE/auth/test-verified")
HTTP_CODE="${VERIFY_RESPONSE: -3}"
echo "HTTP Code: $HTTP_CODE"
if [[ "$HTTP_CODE" == "403" ]]; then
    echo "✅ Verification gate working correctly (403 as expected)"
else
    echo "❌ Verification gate not working properly"
    exit 1
fi
echo

echo "🎉 All auth flow tests passed!"
echo "Your Render deployment is working correctly."