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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def convert_heic_to_jpg(input_file, output_file):
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

def cleanup_image_dir():
    try:
        if UPLOAD_DIR.exists():
            count = 0
            for f in UPLOAD_DIR.glob("*"):
                if f.is_file():
                    f.unlink()
                    count += 1
            
            if count > 0:
                logger.info(f"Cleaned up {count} files from upload directory")
        return True
    except Exception as e:
        logger.error(f"Error cleaning up directory: {str(e)}")
        return False

app = FastAPI()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"Request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Response: {request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s")
        return response
    except Exception as e:
        logger.error(f"Error: {request.method} {request.url.path} - {str(e)}")
        raise

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {str(exc)}")
    return JSONResponse(status_code=422, content={"detail": str(exc)})

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("photo")
UPLOAD_DIR.mkdir(exist_ok=True)

cnn_encoder = CNN()

@app.get("/ping")
async def ping():
    return {"message": "pong"}

# Common function to detect duplicates in the directory
def detect_duplicates_in_dir():
    try:
        if not UPLOAD_DIR.exists() or not any(UPLOAD_DIR.iterdir()):
            return []

        has_standard_images = False
        has_heic_images = False
        original_filenames = {}

        for img_path in UPLOAD_DIR.glob("*"):
            if not img_path.is_file():
                continue

            if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                has_standard_images = True
                original_filenames[img_path.name] = img_path.name
            elif img_path.suffix.lower() in ['.heic']:
                has_heic_images = True
                jpg_path = img_path.with_suffix('.jpg')
                if convert_heic_to_jpg(img_path, jpg_path):
                    has_standard_images = True
                    original_filenames[jpg_path.name] = img_path.name

        if not has_standard_images:
            if has_heic_images:
                return {"error": "HEIC images found but couldn't be converted. Please install pillow-heif or ImageMagick."}
            return []

        duplicates = cnn_encoder.find_duplicates(image_dir=UPLOAD_DIR, scores=True)

        connected_images = {}
        for key, value_list in duplicates.items():
            original_key = original_filenames.get(key, key)
            if original_key not in connected_images:
                connected_images[original_key] = set()

            for filename, score in value_list:
                original_filename = original_filenames.get(filename, filename)
                connected_images[original_key].add(original_filename)

                if original_filename not in connected_images:
                    connected_images[original_filename] = set()
                connected_images[original_filename].add(original_key)

        visited = set()
        groups = []

        def dfs(node, component):
            visited.add(node)
            component.add(node)
            for neighbor in connected_images.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, component)

        for node in connected_images:
            if node not in visited:
                component = set()
                dfs(node, component)
                if len(component) > 1:
                    groups.append(list(component))

        return groups
    except RuntimeError as e:
        if "empty TensorList" in str(e):
            return {"error": "No valid images could be processed. Please check image formats."}
        logger.error(f"Error processing images: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error detecting duplicates: {str(e)}")
        raise

@app.get("/duplicates")
async def get_duplicates():
    groups = detect_duplicates_in_dir()
    cleanup_image_dir()
    
    if isinstance(groups, dict) and "error" in groups:
        return JSONResponse(status_code=400, content=groups)
    return {"duplicate_groups": groups}

@app.post("/upload")
async def upload_photos(files: List[UploadFile] = File(...)):
    try:
        UPLOAD_DIR.mkdir(exist_ok=True)
        
        # Clear existing photos
        if UPLOAD_DIR.exists():
            for f in UPLOAD_DIR.glob("*"):
                if f.is_file():
                    f.unlink()
        
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.heic']
        uploaded_files = 0
        skipped_files = 0
        
        for file in files:
            _, extension = os.path.splitext(file.filename.lower())
            if extension not in valid_extensions:
                skipped_files += 1
                continue
            
            file_path = UPLOAD_DIR / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_files += 1

        # Run deduplication only if there are valid images
        if uploaded_files > 0:
            groups = detect_duplicates_in_dir()
            cleanup_image_dir()
            
            if isinstance(groups, dict) and "error" in groups:
                return JSONResponse(status_code=400, content=groups)
            return {"duplicate_groups": groups}
        else:
            return {"error": "No valid image files were uploaded"}
    except Exception as e:
        logger.error(f"Error in upload_photos: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
