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

    # Extract all scene class names from the script
    import re
    scene_pattern = r'class\s+(\w+)\s*\(\s*Scene\s*\)'
    scene_matches = re.findall(scene_pattern, request.script_code)
    
    if not scene_matches:
        raise HTTPException(status_code=400, detail="No Scene classes found in script")
    
    print(f"Found {len(scene_matches)} scenes: {scene_matches}")

    # Write complete Manim script to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_file:
        temp_file.write(request.script_code)
        temp_path = temp_file.name

    rendered_videos = []
    temp_file_base = Path(temp_path).stem
    
    try:
        # Render each scene individually
        flag = QUALITY_FLAGS.get(request.quality, "-ql")
        quality_folder = {
            "low": "480p15",
            "medium": "720p30", 
            "high": "1080p60",
            "4k": "2160p60"
        }.get(request.quality, "480p15")
        
        for scene_name in scene_matches:
            print(f"Rendering scene: {scene_name}")
            
            result = subprocess.run(
                ["manim", flag, temp_path, scene_name],
                capture_output=True,
                text=True
            )

            # Log the Manim output for debugging
            print(f"=== Manim STDOUT for {scene_name} ===")
            print(result.stdout)
            print(f"=== Manim STDERR for {scene_name} ===")
            print(result.stderr)
            print(f"=== Return Code for {scene_name} ===")
            print(result.returncode)

            if result.returncode != 0:
                # Check if it's a LaTeX error
                error_msg = result.stderr
                if "LaTeX" in error_msg or "tex" in error_msg.lower():
                    raise HTTPException(
                        status_code=500, 
                        detail=f"LaTeX rendering failed in scene '{scene_name}'. Use Text() instead of Tex() for simple text. Error: {result.stderr[:500]}"
                    )
                raise HTTPException(status_code=500, detail=f"Render failed for scene '{scene_name}': {result.stderr[:500]}")

            # Find the rendered video file
            media_dir = Path("media")
            possible_paths = [
                media_dir / "videos" / temp_file_base / quality_folder / f"{scene_name}.mp4",
                media_dir / "media" / "videos" / temp_file_base / quality_folder / f"{scene_name}.mp4",
            ]
            
            output_file = None
            for path in possible_paths:
                if path.exists():
                    output_file = path
                    break
            
            if not output_file or not output_file.exists():
                raise HTTPException(
                    status_code=500, 
                    detail=f"Output file not generated for scene '{scene_name}'. Checked: {[str(p) for p in possible_paths]}"
                )
            
            rendered_videos.append(output_file)
            print(f"Successfully rendered: {output_file}")

        # Concatenate all videos into one using ffmpeg
        if len(rendered_videos) == 1:
            # Only one video, no need to concatenate
            final_video = rendered_videos[0]
        else:
            # Create a temporary file list for ffmpeg concat
            concat_list_path = Path("media") / f"{temp_file_base}_concat.txt"
            with open(concat_list_path, "w") as f:
                for video in rendered_videos:
                    f.write(f"file '{video.absolute()}'\n")
            
            # Output path for concatenated video
            final_video = Path("media") / "videos" / temp_file_base / quality_folder / "final_output.mp4"
            final_video.parent.mkdir(parents=True, exist_ok=True)
            
            # Concatenate videos using ffmpeg
            concat_result = subprocess.run(
                ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(concat_list_path), 
                 "-c", "copy", str(final_video)],
                capture_output=True,
                text=True
            )
            
            if concat_result.returncode != 0:
                print(f"FFmpeg concatenation error: {concat_result.stderr}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to concatenate videos: {concat_result.stderr[:500]}"
                )
            
            # Clean up concat list file
            concat_list_path.unlink()
            print(f"Successfully concatenated {len(rendered_videos)} videos into: {final_video}")

        # Upload the final video to Supabase Storage
        bucket_name = "videos"
        timestamp = int(Path(temp_path).stem.replace("tmp", "")[-8:], 36) if "tmp" in temp_path else ""
        file_path = f"manim_{timestamp}_{request.quality}.mp4"
        
        with open(final_video, "rb") as video_file:
            upload_result = supabase.storage.from_(bucket_name).upload(
                file_path, video_file, {"upsert": "true"}
            )

        # Basic success check
        upload_data = getattr(upload_result, "data", upload_result)
        if not upload_data:
            raise HTTPException(status_code=500, detail="Upload failed")

        # Get public URL
        public_res = supabase.storage.from_(bucket_name).get_public_url(file_path)
        public_data = getattr(public_res, "data", public_res)
        if isinstance(public_data, dict):
            public_url = public_data.get("publicUrl") or public_data.get("public_url") or public_data.get("signedUrl")
        else:
            public_url = str(public_data)
        if not public_url:
            raise HTTPException(status_code=500, detail="Could not obtain public URL from Supabase")

        # Clean up: Delete all rendered videos and directories
        try:
            # Delete individual scene videos
            for video in rendered_videos:
                if video.exists():
                    video.unlink()
            
            # Delete final video if it's different from individual videos
            if final_video not in rendered_videos and final_video.exists():
                final_video.unlink()
            
            # Delete the entire temp directory created by Manim
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
            "message": f"Rendered and uploaded {len(scene_matches)} scenes: {file_path}",
            "scenes_rendered": len(scene_matches)
        }

    finally:
        # Clean up temp script
        os.unlink(temp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)