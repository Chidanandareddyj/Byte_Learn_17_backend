# Sevalla Deployment Guide

## Environment Variables Required

Set these in your Sevalla dashboard:

```bash
SUPABASE_URL=https://geruuvhlyduaoelpwqbj.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdlcnV1dmhseWR1YW9lbHB3cWJqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjExMzgxMDYsImV4cCI6MjA3NjcxNDEwNn0.OA5amTXoUYmRLZ-RVu5gcUgU798l7j_D_FNpdNj_FjM
VIDEO_WEBHOOK_SECRET=srfgtwyuhsdf87w4e5y6t7y8u9ioju76y
PORT=8000
```

## Deployment Steps

1. **Push code to GitHub** (if not already done)
2. **Connect Sevalla to your repository**
3. **Set environment variables** in Sevalla dashboard
4. **Deploy**

## Important Notes

- Sevalla will automatically detect the `Procfile` and use it to start the app
- Make sure `runtime.txt` specifies Python 3.11
- The app needs FFmpeg, LaTeX, and other dependencies listed in Dockerfile
- If using Docker deployment, ensure Dockerfile is properly configured

## Troubleshooting

### Error: "Worker threw exception"
- Check Sevalla logs for specific error messages
- Verify all environment variables are set
- Ensure Python version matches runtime.txt

### Error: "Connection refused"
- Check if the PORT environment variable is set correctly
- Verify the application is binding to 0.0.0.0, not localhost
- Check Sevalla build logs for compilation errors

### Missing Dependencies
If you see errors about missing packages:
- Ensure requirements.txt includes all dependencies
- For system packages (ffmpeg, latex), you may need Docker deployment

## Healthcheck Endpoints

- `GET /` - Basic health check
- `GET /health` - Health status

## API Endpoints

- `POST /render-and-upload` - Render Manim video
- `POST /render-and-upload-async` - Async render with callback
- `POST /mux-audio-video` - Combine audio and video
