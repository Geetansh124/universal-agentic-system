# Production Multi-Stage Dockerfile for Universal Agentic Platform
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging configuration and install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir uvicorn fastapi pydantic requests && \
    pip install --no-cache-dir -e .

# Copy application source code and web assets
COPY src/ src/
COPY config/llm_router_config.example.json config/llm_router_config.json
COPY CLAUDE.md .

# Cloud Run / Serverless exposes dynamic $PORT
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

# Launch production server
CMD ["sh", "-c", "uvicorn src.web.server:app --host 0.0.0.0 --port ${PORT}"]
