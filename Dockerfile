FROM python:3.11-slim

# Set environment variables
ENV POETRY_VERSION=1.8.2
ENV POETRY_NO_INTERACTION=1
ENV POETRY_CACHE_DIR=/tmp/poetry_cache

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==$POETRY_VERSION

# Set working directory
WORKDIR /app

# Copy Poetry files
COPY pyproject.toml poetry.lock* ./

# Install Python dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-root \
    && rm -rf $POETRY_CACHE_DIR

# Copy application code
COPY . .

# Install the application
RUN poetry install --no-dev

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Run the application
CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 