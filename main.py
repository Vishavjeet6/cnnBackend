from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import List, Dict, Set
from imagededup.methods import CNN
from pathlib import Path
import shutil
import os
import uvicorn
import logging
import time
import subprocess
from PIL import Image
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Function to convert HEIC to JPG
def convert_heic_to_jpg(input_file, output_file):
    try:
        # Try using pillow-heif if available
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
            Image.open(input_file).convert("RGB").save(output_file, "JPEG")
            logger.info(f"Converted {input_file} to {output_file} using pillow-heif")
            return True
        except ImportError:
            pass
        
        # Try using ImageMagick if available
        try:
            result = subprocess.run(
                ["magick", "convert", str(input_file), str(output_file)],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Converted {input_file} to {output_file} using ImageMagick")
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.warning(f"ImageMagick conversion failed for {input_file}")
        
        logger.error(f"No available method to convert {input_file}")
        return False
    except Exception as e:
        logger.error(f"Error converting {input_file}: {str(e)}")
        return False

# Function to delete converted files
def delete_converted_files():
    """Delete any JPG files that were converted from HEIC files."""
    try:
        count = 0
        for jpg_path in UPLOAD_DIR.glob("*.jpg"):
            # Check if there's a corresponding HEIC file
            heic_path = jpg_path.with_suffix('.HEIC')
            # Check for both upper and lowercase extensions
            heic_path_lower = jpg_path.with_suffix('.heic')
            
            if heic_path.exists() or heic_path_lower.exists():
                # This is a converted file, delete it
                jpg_path.unlink()
                count += 1
                logger.info(f"Deleted converted file: {jpg_path}")
        
        if count > 0:
            logger.info(f"Deleted {count} converted JPG files")
        return count
    except Exception as e:
        logger.error(f"Error deleting converted files: {str(e)}")
        return 0

app = FastAPI()

# Add middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log the request
    logger.info(f"Request received: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.4f}s")
        return response
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url.path} - Error: {str(e)}")
        raise

# Add exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {str(exc)}")
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow React Native to connect
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("photo")
UPLOAD_DIR.mkdir(exist_ok=True)

cnn_encoder = CNN()

@app.get("/ping")
async def ping():
    logger.info("Ping endpoint called")
    return {"message": "pong"}

# Common function to detect duplicates in the directory
def detect_duplicates_in_dir():
    logger.info("Detecting duplicates in the directory")
    try:
        # Check if the directory exists and has valid images
        if not UPLOAD_DIR.exists() or not any(UPLOAD_DIR.iterdir()):
            logger.warning("Upload directory is empty or doesn't exist")
            return []

        # Check if there are any non-HEIC images
        has_standard_images = False
        has_heic_images = False

        # Track original filenames to converted filenames mapping
        original_filenames = {}

        # Check image types and convert HEIC if needed
        for img_path in UPLOAD_DIR.glob("*"):
            if not img_path.is_file():
                continue

            if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                has_standard_images = True
                # Store original filename
                original_filenames[img_path.name] = img_path.name
            elif img_path.suffix.lower() in ['.heic']:
                has_heic_images = True
                # Convert HEIC to JPG
                jpg_path = img_path.with_suffix('.jpg')
                if convert_heic_to_jpg(img_path, jpg_path):
                    has_standard_images = True
                    # Map the JPG filename back to original HEIC filename
                    original_filenames[jpg_path.name] = img_path.name

        # If no valid images, return empty result
        if not has_standard_images:
            logger.warning("No valid image formats found in directory")
            if has_heic_images:
                return {"error": "HEIC images found but couldn't be converted. Please install pillow-heif or ImageMagick."}
            return []

        # Get all duplicates
        duplicates = cnn_encoder.find_duplicates(image_dir=UPLOAD_DIR, scores=True)

        # Create a graph of connected images using original filenames
        connected_images = {}
        for key, value_list in duplicates.items():
            # Use original filename for the key
            original_key = original_filenames.get(key, key)

            if original_key not in connected_images:
                connected_images[original_key] = set()

            for item in value_list:
                filename, score = item
                # Use original filename for duplicates too
                original_filename = original_filenames.get(filename, filename)
                connected_images[original_key].add(original_filename)

                # Ensure the connected image has an entry too
                if original_filename not in connected_images:
                    connected_images[original_filename] = set()
                connected_images[original_filename].add(original_key)

        # Find connected components (groups of duplicates)
        visited = set()
        groups = []

        def dfs(node, component):
            visited.add(node)
            component.add(node)
            for neighbor in connected_images.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, component)

        # Run DFS to find all connected components
        for node in connected_images:
            if node not in visited:
                component = set()
                dfs(node, component)
                if len(component) > 1:  # Only include groups with more than one image
                    groups.append(list(component))

        logger.info(f"Found {len(groups)} duplicate groups")
        return groups
    except RuntimeError as e:
        if "empty TensorList" in str(e):
            logger.error("No valid images could be processed")
            return {"error": "No valid images could be processed. Please check image formats."}
        logger.error(f"Error in detect_duplicates_in_dir: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error in detect_duplicates_in_dir: {str(e)}", exc_info=True)
        raise

@app.get("/duplicates")
async def get_duplicates():
    logger.info("Getting duplicate groups")
    groups = detect_duplicates_in_dir()
    
    # Clean up any converted files
    delete_converted_files()
    
    if isinstance(groups, dict) and "error" in groups:
        return JSONResponse(status_code=400, content=groups)
    return {"duplicate_groups": groups}

@app.get("/photos")
async def get_photos():
    logger.info("Getting all photos")
    groups = detect_duplicates_in_dir()
    if isinstance(groups, dict) and "error" in groups:
        return JSONResponse(status_code=400, content=groups)
    return {"duplicate_groups": groups}

@app.post("/upload")
async def upload_photos(files: List[UploadFile] = File(...)):
    logger.info(f"Upload request received with {len(files)} files")
    try:
        # Ensure upload directory exists
        UPLOAD_DIR.mkdir(exist_ok=True)
        
        # Clear existing photos
        if UPLOAD_DIR.exists():
            for f in UPLOAD_DIR.glob("*"):
                if f.is_file():
                    f.unlink()
            logger.info("Cleared existing photos")
        else:
            logger.warning(f"Upload directory {UPLOAD_DIR} does not exist, creating it")
            UPLOAD_DIR.mkdir(exist_ok=True)

        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.heic']
        uploaded_files = 0
        skipped_files = 0
        heic_files = 0

        for file in files:
            # Check if file has valid extension
            _, extension = os.path.splitext(file.filename.lower())
            if extension not in valid_extensions:
                logger.warning(f"Skipping non-image file: {file.filename}")
                skipped_files += 1
                continue  # Skip non-image files
            
            file_path = UPLOAD_DIR / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            # Track HEIC files for potential conversion
            if extension == '.heic':
                heic_files += 1
                
            uploaded_files += 1

        logger.info(f"Successfully uploaded {uploaded_files} files ({heic_files} HEIC files), skipped {skipped_files} non-image files")

        # Convert HEIC files if needed
        converted_count = 0
        if heic_files > 0:
            logger.info(f"Converting {heic_files} HEIC files to JPG format")
            for heic_path in UPLOAD_DIR.glob("*.heic"):
                jpg_path = heic_path.with_suffix('.jpg')
                if convert_heic_to_jpg(heic_path, jpg_path):
                    converted_count += 1
            
            logger.info(f"Successfully converted {converted_count} of {heic_files} HEIC files")

        # Run deduplication only if there are valid images
        if uploaded_files > 0:
            try:
                logger.info("Starting deduplication analysis")
                duplicates = cnn_encoder.find_duplicates(image_dir=UPLOAD_DIR, scores=True)

                # Format result: keep only groups with duplicates
                # Also convert numpy.float32 to Python float to ensure JSON serialization works
                grouped = {}
                for key, value_list in duplicates.items():
                    if len(value_list) > 0:
                        grouped[key] = []
                        for item in value_list:
                            # Each item is a tuple of (filename, score)
                            filename, score = item
                            # Convert numpy.float32 to Python float
                            grouped[key].append((filename, float(score)))

                logger.info(f"Deduplication complete. Found duplicates for {len(grouped)} images")
                # delete converted heic files
                delete_converted_files()

                return grouped
            except RuntimeError as e:
                if "empty TensorList" in str(e):
                    logger.error("No valid images could be processed")
                    return {"error": "No valid images could be processed. Please check image formats."}
                raise
        else:
            logger.warning("No files were uploaded")
            return {"error": "No valid image files were uploaded"}
    except Exception as e:
        logger.error(f"Error in upload_photos: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    logger.info("Starting up FastAPI server")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
