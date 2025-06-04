# Docker Setup for Ultra Civic Backend

## Quick Start

1. **Install Docker and Docker Compose** (if not already installed):
   ```bash
   # On Ubuntu/Debian
   sudo apt update
   sudo apt install docker.io docker-compose-plugin
   sudo systemctl start docker
   sudo systemctl enable docker
   sudo usermod -aG docker $USER
   # Log out and back in for group changes to take effect
   
   # On macOS
   # Install Docker Desktop from https://www.docker.com/products/docker-desktop
   
   # On Windows
   # Install Docker Desktop from https://www.docker.com/products/docker-desktop
   ```

2. **Set up environment variables**:
   ```bash
   # Copy the template and add your Stripe secrets
   cp .env.docker .env
   
   # Edit .env and add your actual Stripe keys:
   # STRIPE_SECRET=sk_test_your_actual_key_here
   # STRIPE_WEBHOOK_SECRET=whsec_your_actual_webhook_secret_here
   ```

3. **Start the complete environment**:
   ```bash
   docker compose up --build
   ```

   That's it! The application will be available at http://localhost:8000

## What happens when you run `docker compose up`

1. **PostgreSQL database** starts on port 5432
2. **FastAPI application** builds and starts on port 8000
3. **Database migrations** run automatically (Alembic)
4. **Hot reload** is enabled for development

## Useful Commands

```bash
# Start in background
docker compose up -d

# View logs
docker compose logs -f

# Stop everything
docker compose down

# Rebuild and start
docker compose up --build

# Reset database (removes all data!)
docker compose down -v
docker compose up --build

# Run shell in app container
docker compose exec app bash

# Run database migrations manually
docker compose exec app poetry run alembic upgrade head
```

## Testing the API

Once running, you can test the endpoints:

```bash
# Register a user
http POST :8000/auth/register email=test@example.com password=secret

# Start KYC verification
TOKEN=$(http -f POST :8000/auth/jwt/login username=test@example.com password=secret | jq -r .access_token)
http POST :8000/kyc/start "Authorization: Bearer $TOKEN"
```

## Troubleshooting

- **Port conflicts**: If port 8000 or 5432 are in use, modify the ports in `docker-compose.yml`
- **Stripe keys**: Make sure your `.env` file has valid Stripe keys
- **Database issues**: Run `docker compose down -v` to reset the database
- **Build issues**: Run `docker compose build --no-cache` to rebuild from scratch