# ByteLearn Backend - Manim Video Rendering API

FastAPI backend for rendering Manim animations and uploading to Supabase.

## Setup

1. **Install dependencies:**
```bash
pip install fastapi uvicorn supabase python-dotenv
pip install manim
```

2. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

3. **Run the server:**
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### POST /render-and-upload

Renders a Manim animation and uploads it to Supabase storage.

**Request Body:**
```json
{
  "script_code": "from manim import *\n\nclass MyScene(Scene):\n    def construct(self):\n        # Your Manim code here",
  "scene_name": "MyScene",
  "quality": "low"
}
```

**Quality Options:**
- `low` - 480p15 (fast, good for testing)
- `medium` - 720p30
- `high` - 1080p60
- `4k` - 2160p60

**Response:**
```json
{
  "success": true,
  "video_url": "https://your-supabase-url/storage/v1/object/public/videos/MyScene_low.mp4",
  "message": "Rendered and uploaded: MyScene_low.mp4"
}
```

## Media Files & Cleanup

### Automatic Cleanup
The API automatically deletes temporary media files after successful upload to Supabase.

### Manual Cleanup
Run the cleanup script to remove old files:

```bash
# Clean files older than 24 hours (default)
python cleanup_media.py

# Clean ALL media files (use with caution!)
python cleanup_media.py --all
```

### Production Recommendations

1. **Set up a cron job** to run cleanup periodically:
   ```bash
   # Run cleanup daily at 2 AM
   0 2 * * * cd /path/to/backend && python cleanup_media.py
   ```

2. **Monitor disk space** - even with cleanup, monitor your server's disk usage

3. **Don't commit media folder** - it's in `.gitignore` for a reason

4. **Use environment variables** for sensitive data (Supabase keys, etc.)

## File Structure

```
byte_learn_backend/
├── main.py              # FastAPI application
├── cleanup_media.py     # Media cleanup utility
├── .env                 # Environment variables (not committed)
├── .env.example         # Environment template
├── .gitignore           # Git ignore rules
└── media/               # Temporary Manim output (auto-deleted)
    ├── videos/
    ├── images/
    └── Tex/
```

## Security Notes

- The API blocks potentially unsafe code (imports of `os`, `subprocess`, `exec`, etc.)
- In production, consider running Manim in a sandboxed environment
- Implement rate limiting to prevent abuse
- Use HTTPS in production
- Keep your Supabase keys secure

## Troubleshooting

### MiKTeX/LaTeX Issues
If you see LaTeX errors, update MiKTeX:
```bash
miktex update
```

### Port Already in Use
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### Manim Not Found
```bash
pip install manim
# or
pip install manim-community
```
