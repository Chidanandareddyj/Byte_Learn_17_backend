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
import requests
from moviepy import VideoFileClip, AudioFileClip

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

class MuxRequest(BaseModel):
    video_url: str  # Supabase video URL
    audio_url: str  # Supabase audio URL
    output_name: str = "combined_video"  # e.g., "scene1_muxed.mp4"
    bucket_name: str = "muxvideos"  # Your bucket
    audio_speed: float = 1.3  # Speed multiplier for audio (1.0 = normal, 1.3 = 30% faster)

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

    # Write complete Manim script to temp file with UTF-8 encoding for Unicode symbols
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as temp_file:
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
            
            try:
                result = subprocess.run(
                    ["manim", flag, temp_path, scene_name],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout per scene for longer animations
                )
            except subprocess.TimeoutExpired:
                raise HTTPException(
                    status_code=500,
                    detail=f"Scene '{scene_name}' timed out after 300 seconds. The scene likely contains an infinite loop, excessive computations, or animations that take too long. Simplify the scene animations and reduce complexity."
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

@app.post("/mux-audio-video")
async def mux_audio_video(request: MuxRequest):
    video_clip = None
    audio_clip = None
    final_clip = None
    
    # Download files to temp
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            temp_path = Path(temp_dir)
            
            # Download video
            video_path = temp_path / "input_video.mp4"
            video_resp = requests.get(request.video_url, timeout=30)
            if video_resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Failed to download video: {video_resp.status_code}")
            with open(video_path, "wb") as f:
                f.write(video_resp.content)
            
            # Download audio - detect extension from URL
            audio_extension = request.audio_url.split('.')[-1].split('?')[0]  # Extract extension, remove query params
            if audio_extension not in ['mp3', 'wav', 'm4a', 'aac']:
                audio_extension = 'mp3'  # Default fallback
            audio_path = temp_path / f"input_audio.{audio_extension}"
            audio_resp = requests.get(request.audio_url, timeout=30)
            if audio_resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Failed to download audio: {audio_resp.status_code}")
            with open(audio_path, "wb") as f:
                f.write(audio_resp.content)
            
            # Load with MoviePy
            try:
                video_clip = VideoFileClip(str(video_path))
                audio_clip = AudioFileClip(str(audio_path))
            except Exception as load_error:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to load media files: {str(load_error)}. Audio file: {audio_path.name}"
                )
            
            # Speed up audio if requested (using ffmpeg via subprocess for better quality)
            if request.audio_speed != 1.0:
                print(f"Speeding up audio by {request.audio_speed}x")
                sped_audio_path = temp_path / f"sped_audio.{audio_extension}"
                
                # Use ffmpeg atempo filter for audio speed adjustment
                # atempo can only go from 0.5 to 2.0, so we may need to chain filters
                speed = request.audio_speed
                atempo_filters = []
                
                while speed > 2.0:
                    atempo_filters.append("atempo=2.0")
                    speed /= 2.0
                while speed < 0.5:
                    atempo_filters.append("atempo=0.5")
                    speed /= 0.5
                
                atempo_filters.append(f"atempo={speed}")
                filter_str = ",".join(atempo_filters)
                
                ffmpeg_cmd = [
                    "ffmpeg", "-i", str(audio_path),
                    "-filter:a", filter_str,
                    "-y",  # Overwrite output
                    str(sped_audio_path)
                ]
                
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Warning: Failed to speed up audio: {result.stderr}")
                    # Continue with original audio if speed adjustment fails
                else:
                    # Close original audio and load the sped-up version
                    audio_clip.close()
                    audio_clip = AudioFileClip(str(sped_audio_path))
            
            # Get durations
            video_duration = video_clip.duration
            audio_duration = audio_clip.duration
            
            # Mux: Handle different audio/video length scenarios
            if audio_duration > video_duration:
                # Audio is longer - trim audio to video length
                audio_clip = audio_clip.subclipped(0, video_duration)
            elif audio_duration < video_duration:
                # Audio is shorter - you might want to loop audio or just use what's available
                # For now, we'll just use the available audio (video will be silent after audio ends)
                pass
            
            final_clip = video_clip.with_audio(audio_clip)
            
            # Export to temp output
            output_path = temp_path / f"{request.output_name}.mp4"
            final_clip.write_videofile(
                str(output_path), 
                codec="libx264", 
                audio_codec="aac",
                audio_bitrate="192k",  # Explicitly set audio bitrate
                temp_audiofile=str(temp_path / "temp-audio.m4a"),
                remove_temp=True,
                logger=None  # Suppress moviepy progress bars in logs
            )
            
            # Close clips to free resources BEFORE uploading
            try:
                if final_clip:
                    final_clip.close()
                if audio_clip:
                    audio_clip.close()
                if video_clip:
                    video_clip.close()
            except Exception as close_error:
                print(f"Warning: Error closing clips: {close_error}")
            
            # Upload to Supabase
            file_name = f"{request.output_name}.mp4"
            with open(output_path, "rb") as output_file:
                upload_result = supabase.storage.from_(request.bucket_name).upload(
                    file_name, 
                    output_file,
                    {"contentType": "video/mp4", "upsert": "true"}
                )
            
            # Check upload success
            upload_data = getattr(upload_result, "data", upload_result)
            if not upload_data:
                raise HTTPException(status_code=500, detail="Upload to Supabase failed")
            
            # Get public URL (using same pattern as render-and-upload endpoint)
            public_res = supabase.storage.from_(request.bucket_name).get_public_url(file_name)
            public_data = getattr(public_res, "data", public_res)
            if isinstance(public_data, dict):
                public_url = public_data.get("publicUrl") or public_data.get("public_url") or public_data.get("signedUrl")
            else:
                public_url = str(public_data)
            
            if not public_url:
                raise HTTPException(status_code=500, detail="Could not obtain public URL from Supabase")
            
            return {
                "success": True,
                "combined_url": public_url,
                "video_duration": video_duration,
                "audio_duration": audio_duration,
                "message": "Audio and video muxed successfully"
            }
        
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Muxing failed: {str(e)}")
        finally:
            # Ensure all clips are closed even if an error occurs
            try:
                if final_clip:
                    final_clip.close()
                if audio_clip:
                    audio_clip.close()
                if video_clip:
                    video_clip.close()
            except Exception as cleanup_error:
                print(f"Warning: Failed to close video clips: {cleanup_error}")
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)