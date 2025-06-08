FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including PostgreSQL dev headers
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache
RUN pip install --upgrade pip && pip install poetry

# Copy application code 
COPY . .

# Install dependencies and project
RUN poetry install --only main,dev && rm -rf $POETRY_CACHE_DIR

# Expose port
EXPOSE 8000

# Run the application
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
