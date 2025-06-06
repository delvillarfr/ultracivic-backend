#!/bin/bash

# Test script for Ultra Civic auth+KYC flow

echo "🚀 Testing Ultra Civic Auth+KYC Flow"
echo "====================================="

# Test backend health
echo "1. Testing backend health..."
HEALTH=$(curl -s http://localhost:8000/health)
if [[ $HEALTH == *"ok"* ]]; then
    echo "✅ Backend healthy: $HEALTH"
else
    echo "❌ Backend not responding"
    exit 1
fi

# Test frontend accessibility
echo "2. Testing frontend accessibility..."
if curl -s http://localhost:8080/auth.html | grep -q "Ultra Civic - Authentication"; then
    echo "✅ Frontend auth page accessible"
else
    echo "❌ Frontend not accessible"
    exit 1
fi

# Test CORS preflight
echo "3. Testing CORS configuration..."
CORS=$(curl -s -X OPTIONS -H "Origin: http://localhost:8080" \
       -H "Access-Control-Request-Method: POST" \
       -H "Access-Control-Request-Headers: Content-Type,Authorization" \
       http://localhost:8000/auth/register -D -)

if [[ $CORS == *"access-control-allow-origin"* ]]; then
    echo "✅ CORS configured correctly"
else
    echo "❌ CORS not working"
    exit 1
fi

echo ""
echo "🎉 All tests passed! Ready for manual testing:"
echo "   Frontend: http://localhost:8080/auth.html"
echo "   Backend API: http://localhost:8000/docs"
echo ""
echo "Next steps:"
echo "1. Start ngrok: ngrok http 8000"
echo "2. Configure Stripe webhook with ngrok URL"
echo "3. Test complete registration → verification flow"