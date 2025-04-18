import subprocess
from PIL import Image
import shutil
from pathlib import Path
from logger import logger

def convert_heic_to_jpg(input_file, output_file):
    """
    Convert HEIC images to JPG format using either pillow-heif or ImageMagick
    """
    try:
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
            Image.open(input_file).convert("RGB").save(output_file, "JPEG")
            return True
        except ImportError:
            pass
        
        try:
            subprocess.run(
                ["magick", "convert", str(input_file), str(output_file)],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        return False
    except Exception as e:
        logger.error(f"Error converting {input_file}: {str(e)}")
        return False

def cleanup_image_dir(upload_dir, user_dir=None):
    """
    Delete the entire directory for a specific user
    """
    try:
        target_dir = upload_dir / user_dir if user_dir else upload_dir
        
        if target_dir.exists():
            if user_dir:  # Only delete the entire directory if it's a user directory
                shutil.rmtree(target_dir)
                logger.info(f"Deleted entire directory: {target_dir}")
        return True
    except Exception as e:
        logger.error(f"Error cleaning up directory {target_dir}: {str(e)}")
        return False