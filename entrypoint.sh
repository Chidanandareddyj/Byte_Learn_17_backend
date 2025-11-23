#!/bin/bash
set -e

# Default PORT to 8000 if not set by Sevalla
export PORT=${PORT:-8000}

echo "========================================="
echo "Starting ByteLearn Backend"
echo "========================================="
echo "PORT: $PORT"
echo "SUPABASE_URL: ${SUPABASE_URL:0:30}..."
echo "SUPABASE_KEY: ${SUPABASE_KEY:+[SET]}${SUPABASE_KEY:-[NOT SET]}"
echo "VIDEO_WEBHOOK_SECRET: ${VIDEO_WEBHOOK_SECRET:+[SET]}${VIDEO_WEBHOOK_SECRET:-[NOT SET]}"
echo "========================================="

# Start uvicorn with the PORT from environment
exec uvicorn main:app --host 0.0.0.0 --port "$PORT"
