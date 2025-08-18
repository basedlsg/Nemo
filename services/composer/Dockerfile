FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application code
COPY services/ ./services/
COPY data/ ./data/

# Set environment variables
ENV PYTHONPATH=/app
ENV GAEA_ENV=prod

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the composer service
CMD ["python", "-m", "uvicorn", "services.composer.api:app", "--host", "0.0.0.0", "--port", "8080"]