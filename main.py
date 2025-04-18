from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import List
from pathlib import Path
import os
import uvicorn

# Import from our new modules
from logger import logger
from utils import cleanup_image_dir
from services import ImageDuplicateService
from middleware import log_requests, validation_exception_handler, general_exception_handler

app = FastAPI(
    title="Image Deduplication API",
    description="API for detecting duplicate images using CNN",
    version="1.0.0",
)

# Register middleware
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    return await log_requests(request, call_next)

# Register exception handlers
@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    return await validation_exception_handler(request, exc)

@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return await general_exception_handler(request, exc)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set upload directory from environment variable or default
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "photo"))
UPLOAD_DIR.mkdir(exist_ok=True)

# Initialize image service
image_service = ImageDuplicateService(UPLOAD_DIR)

@app.get("/ping")
async def ping():
    return {"message": "pong"}

@app.post("/upload/{user_id}")
async def upload_photos_by_user(user_id: str, files: List[UploadFile] = File(...)):
    try:
        # Process uploaded files
        uploaded_files, skipped_files = await image_service.process_uploaded_files(user_id, files)
            
        # Run deduplication only if there are valid images
        if uploaded_files > 0:
            groups = image_service.detect_duplicates_in_dir(user_id)
            cleanup_image_dir(UPLOAD_DIR, user_id)
            if isinstance(groups, dict) and "error" in groups:
                return JSONResponse(status_code=400, content=groups)
            return {"duplicate_groups": groups}
        else:
            return {"error": "No valid image files were uploaded"}
    except Exception as e:
        logger.error(f"Error in upload_photos_by_user: {str(e)}", exc_info=True)
        raise

@app.get("/duplicates/{user_id}")
async def get_duplicates_by_user(user_id: str):
    groups = image_service.detect_duplicates_in_dir(user_id)
    cleanup_image_dir(UPLOAD_DIR, user_id)
    if isinstance(groups, dict) and "error" in groups:
        return JSONResponse(status_code=400, content=groups)
    return {"duplicate_groups": groups}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
