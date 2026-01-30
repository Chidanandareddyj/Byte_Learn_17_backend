# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for Manim
# Using full LaTeX installation for better rendering support
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    pkg-config \
    ffmpeg \
    libcairo2-dev \
    libpango1.0-dev \
    texlive-full \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

# Create media directory for Manim outputs
RUN mkdir -p /app/media

# Create job queue directory for persistent job storage
RUN mkdir -p /app/job_queue

# Expose port (will be set by Sevalla via PORT env var)
EXPOSE 8000

# Add healthcheck with longer timeout for rendering jobs
# Note: PORT is set via ENV, healthcheck uses default 8000 if PORT not available
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=5 \
    CMD sh -c 'python -c "import urllib.request, os; port=os.getenv(\"PORT\", \"8000\"); urllib.request.urlopen(f\"http://localhost:{port}/health\").read()"' || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Use entrypoint script
ENTRYPOINT ["./entrypoint.sh"]
