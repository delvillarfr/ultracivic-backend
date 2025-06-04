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
RUN pip install poetry

# Configure Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Install dependencies (--no-root to avoid installing the current project)
RUN poetry install --only=main --no-root && rm -rf $POETRY_CACHE_DIR

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]