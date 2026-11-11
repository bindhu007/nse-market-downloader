# Dockerfile for NSE Market Data Downloader
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and tests
COPY . .

# Create volume mount points
RUN mkdir -p output logs

# Default entrypoint runs full data pipeline
ENTRYPOINT ["python", "main.py"]
CMD []
