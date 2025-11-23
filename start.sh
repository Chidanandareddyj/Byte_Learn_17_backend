#!/bin/bash

# Startup script for debugging Sevalla deployment

echo "=== Environment Check ==="
echo "Python version: $(python --version)"
echo "PORT: ${PORT:-8000}"
echo "SUPABASE_URL: ${SUPABASE_URL:0:30}..."
echo "SUPABASE_KEY set: $([ -n "$SUPABASE_KEY" ] && echo 'YES' || echo 'NO')"

echo ""
echo "=== Installing Dependencies ==="
pip install --no-cache-dir -r requirements.txt

echo ""
echo "=== Starting Application ==="
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
