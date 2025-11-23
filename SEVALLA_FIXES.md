# Sevalla Deployment - Important Notes

## Container Restart Issue

Your container is restarting during video generation because:

1. **Long-running processes** - Rendering 17 Manim scenes takes 5-10+ minutes
2. **Platform timeouts** - Sevalla has HTTP request timeouts (~60s) and health check timeouts
3. **Resource limits** - Container may hit memory/CPU limits

## Solutions Applied

### 1. Persistent Job Queue
- Jobs are now saved to `/app/job_queue` directory
- Non-daemon threads prevent job loss
- Jobs can be recovered after restart

### 2. Better Health Checks
- Longer timeout intervals
- Job status tracking
- Active job monitoring at `/health` endpoint

### 3. To Configure in Sevalla

#### Add Persistent Volume:
1. Go to Sevalla Dashboard
2. Add volume mount: `/app/job_queue` 
3. This ensures jobs persist across restarts

#### Increase Timeouts:
- Set HTTP timeout to 300+ seconds
- Adjust health check intervals if possible

## Recommended: Split Scene Rendering

Instead of rendering all 17 scenes in one request, modify your frontend to:
1. Send individual render requests for each scene
2. Combine videos on the frontend after all complete
3. This prevents timeouts and allows progress tracking

## Environment Variables Checklist

```
SUPABASE_URL=https://geruuvhlyduaoelpwqbj.supabase.co
SUPABASE_KEY=eyJhbG...
VIDEO_WEBHOOK_SECRET=srfgtwyuhsdf87w4e5y6t7y8u9ioju76y (NO QUOTES!)
PORT=3000 (auto-set by Sevalla)
```

## Monitoring

- Health check: `https://your-backend.sevalla.app/health`
- Job status: `https://your-backend.sevalla.app/jobs/{job_id}`
