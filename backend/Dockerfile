# ============================================
# Predictive Maintenance - Backend Dockerfile
# ============================================
# Production-ready container for Render/Railway deployment

FROM python:3.10-slim

LABEL maintainer="Predictive Maintenance Team"
LABEL description="Backend API for Industrial Asset Health Monitoring"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies (minimal for production)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
# Note: When building from backend/ context, we copy to backend/ subdirectory
# to maintain import paths (backend.api.main, backend.config, etc.)
COPY . ./backend/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
# Using backend.api.main:app because PYTHONPATH=/app and code is in /app/backend/
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
