from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Manim API with Supabase")

# Supabase config (use env vars in prod)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Changed from SUPABASE_ANON_KEY to match .env file
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class RenderRequest(BaseModel):
    script_code: str  # Complete Manim script with scene class definition
    scene_name: str  # Name of the scene class to render
    quality: str = "low"  # low, medium, high, 4k

# Map quality to Manim flags
QUALITY_FLAGS = {
    "low": "-ql",
    "medium": "-qm",
    "high": "-qh",
    "4k": "-qk",
}

@app.post("/render-and-upload")
async def render_and_upload(request: RenderRequest):
    # Basic security check (expand in prod, e.g., sandbox with restricted globals)
    unsafe_keywords = ["import os", "subprocess", "exec", "__import__", "open(", "file("]
    if any(keyword in request.script_code for keyword in unsafe_keywords):
        raise HTTPException(status_code=400, detail="Unsafe code detected")

    # Validate that the script contains the specified scene class
    if f"class {request.scene_name}" not in request.script_code:
        raise HTTPException(status_code=400, detail=f"Scene class '{request.scene_name}' not found in script")

    # Write complete Manim script to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_file:
        temp_file.write(request.script_code)
        temp_path = temp_file.name

    try:
        # Render with Manim
        flag = QUALITY_FLAGS.get(request.quality, "-ql")
        
        result = subprocess.run(
            ["manim", flag, temp_path, request.scene_name],
            capture_output=True,
            text=True
        )

        # Log the Manim output for debugging
        print("=== Manim STDOUT ===")
        print(result.stdout)
        print("=== Manim STDERR ===")
        print(result.stderr)
        print("=== Return Code ===")
        print(result.returncode)

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Render failed: {result.stderr}")

        # Find the actual output file (Manim creates subdirectories based on temp file name)
        temp_file_base = Path(temp_path).stem
        quality_folder = {
            "low": "480p15",
            "medium": "720p30", 
            "high": "1080p60",
            "4k": "2160p60"
        }.get(request.quality, "480p15")
        
        # Search for the output file in the media directory
        output_file = None
        media_dir = Path("media")
        
        # Check both possible locations
        possible_paths = [
            media_dir / "videos" / temp_file_base / quality_folder / f"{request.scene_name}.mp4",
            media_dir / "media" / "videos" / temp_file_base / quality_folder / f"{request.scene_name}.mp4",
        ]
        
        for path in possible_paths:
            if path.exists():
                output_file = path
                break
        
        if not output_file or not output_file.exists():
            # Check what files actually exist in the media directory
            media_dir = Path("media")
            existing_files = []
            if media_dir.exists():
                for item in media_dir.rglob("*.mp4"):
                    existing_files.append(str(item))
            
            error_msg = f"Output file not generated. Checked paths: {[str(p) for p in possible_paths]}"
            if existing_files:
                error_msg += f"\nFound MP4 files: {existing_files}"
            else:
                error_msg += "\nNo MP4 files found in media directory"
            
            raise HTTPException(status_code=500, detail=error_msg)

        # Upload to Supabase Storage
        bucket_name = "videos"  # Ensure this bucket exists in your Supabase project
        file_path = f"{request.scene_name}_{request.quality}.mp4"
        with open(output_file, "rb") as video_file:
            # python supabase client doesn't accept 'options' kwarg on upload; content type is inferred
            upload_result = supabase.storage.from_(bucket_name).upload(
                file_path, video_file
            )

        # Basic success check (structure differs by client version)
        upload_data = getattr(upload_result, "data", upload_result)
        if not upload_data:
            raise HTTPException(status_code=500, detail="Upload failed")

        # Get public URL (structure differs by client version)
        public_res = supabase.storage.from_(bucket_name).get_public_url(file_path)
        public_data = getattr(public_res, "data", public_res)
        if isinstance(public_data, dict):
            public_url = public_data.get("publicUrl") or public_data.get("public_url") or public_data.get("signedUrl")
        else:
            public_url = str(public_data)
        if not public_url:
            raise HTTPException(status_code=500, detail="Could not obtain public URL from Supabase")

        # Clean up: Delete the rendered video file and its directory
        try:
            output_file.unlink()  # Delete the video file
            
            # Delete the entire temp directory created by Manim
            temp_file_base = Path(temp_path).stem
            media_dir = Path("media")
            
            # Clean up videos directory
            video_dir = media_dir / "videos" / temp_file_base
            if video_dir.exists():
                shutil.rmtree(video_dir)
            
            # Clean up images directory (if any)
            images_dir = media_dir / "images" / temp_file_base
            if images_dir.exists():
                shutil.rmtree(images_dir)
                
            # Also check nested media/media structure
            nested_video_dir = media_dir / "media" / "videos" / temp_file_base
            if nested_video_dir.exists():
                shutil.rmtree(nested_video_dir)
                
            nested_images_dir = media_dir / "media" / "images" / temp_file_base
            if nested_images_dir.exists():
                shutil.rmtree(nested_images_dir)
                
        except Exception as cleanup_error:
            # Log cleanup errors but don't fail the request
            print(f"Warning: Failed to cleanup media files: {cleanup_error}")

        return {
            "success": True,
            "video_url": public_url,
            "message": f"Rendered and uploaded: {file_path}"
        }

    finally:
        # Clean up temp script
        os.unlink(temp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)