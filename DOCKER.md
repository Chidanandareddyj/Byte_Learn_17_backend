# Docker Setup Guide

## Prerequisites

- Docker Desktop installed on your machine
- Docker Compose (included with Docker Desktop)

## Quick Start

### 1. Build the Docker Image

```bash
docker build -t bytelearn-backend .
```

### 2. Run with Docker Compose (Recommended)

```bash
docker-compose up -d
```

This will:
- Build the image if it doesn't exist
- Start the container in detached mode
- Expose the API on port 8000
- Load environment variables from `.env` file

### 3. Run with Docker Only

```bash
docker run -d \
  --name bytelearn-backend \
  -p 8000:8000 \
  --env-file .env \
  -v ${PWD}/media:/app/media \
  bytelearn-backend
```

## Docker Commands

### View logs
```bash
docker-compose logs -f
```

### Stop the container
```bash
docker-compose down
```

### Restart the container
```bash
docker-compose restart
```

### Rebuild after code changes
```bash
docker-compose up -d --build
```

### Access container shell
```bash
docker exec -it bytelearn-backend bash
```

## Environment Variables

Make sure your `.env` file contains:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

## Port Configuration

The default port is 8000. To change it, modify the `docker-compose.yml`:
```yaml
ports:
  - "3001:8000"  # Change 3001 to your desired port
```

## Volume Mounts

The `media` directory is mounted to persist generated videos and images:
```yaml
volumes:
  - ./media:/app/media
```

## Production Deployment

### Option 1: Deploy to Cloud Run (GCP)

1. Build and tag the image:
```bash
docker build -t gcr.io/YOUR-PROJECT-ID/bytelearn-backend .
```

2. Push to Google Container Registry:
```bash
docker push gcr.io/YOUR-PROJECT-ID/bytelearn-backend
```

3. Deploy to Cloud Run:
```bash
gcloud run deploy bytelearn-backend \
  --image gcr.io/YOUR-PROJECT-ID/bytelearn-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Option 2: Deploy to AWS ECS

1. Create ECR repository and push image
2. Create task definition
3. Create service in ECS

### Option 3: Deploy to Railway/Render

1. Connect your GitHub repository
2. Railway/Render will auto-detect the Dockerfile
3. Set environment variables in the dashboard
4. Deploy

## Troubleshooting

### Container exits immediately
Check logs: `docker-compose logs`

### Port already in use
Change the port in `docker-compose.yml` or stop the conflicting service

### Permission issues with media folder
On Linux/Mac: `sudo chown -R 1000:1000 media/`

### Build fails on dependencies
Ensure you have a stable internet connection. LaTeX packages are large.

## Health Check

The container includes a health check. View status:
```bash
docker ps
```

Look for "healthy" status in the STATUS column.

## Performance Notes

- First build takes 5-10 minutes (LaTeX installation)
- Subsequent builds are faster due to Docker layer caching
- Container size: ~2-3 GB (due to Manim dependencies)
- Recommended resources: 2GB RAM minimum, 4GB+ recommended
