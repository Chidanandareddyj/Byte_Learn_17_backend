"""
Cleanup script for Manim media files
Run this periodically to clean up any orphaned media files
"""
import shutil
from pathlib import Path
import time

def cleanup_old_media(max_age_hours=24):
    """
    Delete media files older than max_age_hours
    
    Args:
        max_age_hours: Maximum age in hours before deletion (default: 24 hours)
    """
    media_dir = Path("media")
    
    if not media_dir.exists():
        print("No media directory found")
        return
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    deleted_count = 0
    
    # Cleanup videos
    videos_dir = media_dir / "videos"
    if videos_dir.exists():
        for temp_dir in videos_dir.iterdir():
            if temp_dir.is_dir() and temp_dir.name.startswith("tmp"):
                dir_age = current_time - temp_dir.stat().st_mtime
                if dir_age > max_age_seconds:
                    print(f"Deleting old video directory: {temp_dir}")
                    shutil.rmtree(temp_dir)
                    deleted_count += 1
    
    # Cleanup images
    images_dir = media_dir / "images"
    if images_dir.exists():
        for temp_dir in images_dir.iterdir():
            if temp_dir.is_dir() and temp_dir.name.startswith("tmp"):
                dir_age = current_time - temp_dir.stat().st_mtime
                if dir_age > max_age_seconds:
                    print(f"Deleting old image directory: {temp_dir}")
                    shutil.rmtree(temp_dir)
                    deleted_count += 1
    
    # Cleanup nested media/media structure
    nested_media = media_dir / "media"
    if nested_media.exists():
        for subdir in ["videos", "images"]:
            subdir_path = nested_media / subdir
            if subdir_path.exists():
                for temp_dir in subdir_path.iterdir():
                    if temp_dir.is_dir() and temp_dir.name.startswith("tmp"):
                        dir_age = current_time - temp_dir.stat().st_mtime
                        if dir_age > max_age_seconds:
                            print(f"Deleting old directory: {temp_dir}")
                            shutil.rmtree(temp_dir)
                            deleted_count += 1
    
    # Cleanup Tex files
    tex_dir = media_dir / "Tex"
    if tex_dir.exists():
        for tex_file in tex_dir.glob("*.tex"):
            file_age = current_time - tex_file.stat().st_mtime
            if file_age > max_age_seconds:
                print(f"Deleting old Tex file: {tex_file}")
                tex_file.unlink()
                deleted_count += 1
    
    print(f"\nCleanup complete! Deleted {deleted_count} items")

def cleanup_all_media():
    """Delete ALL media files (use with caution!)"""
    media_dir = Path("media")
    
    if media_dir.exists():
        print("WARNING: Deleting ALL media files...")
        shutil.rmtree(media_dir)
        print("All media files deleted")
    else:
        print("No media directory found")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        cleanup_all_media()
    else:
        # Default: cleanup files older than 24 hours
        cleanup_old_media(max_age_hours=24)
