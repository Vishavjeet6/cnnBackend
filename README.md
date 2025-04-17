# Image Deduplication API

A FastAPI-based backend service for detecting and grouping duplicate images using deep learning techniques.

## Features

- Image upload and storage
- Duplicate detection using CNN (Convolutional Neural Networks)
- Multiple endpoints for different types of duplicate analysis
- Comprehensive logging
- CORS support for frontend integration

## Endpoints

### `GET /ping`
Health check endpoint that returns a "pong" message.

### `GET /photos`
Returns all photos with their duplicate matches and similarity scores.

### `GET /duplicates`
Returns grouped clusters of duplicate images, organized into related sets.

### `POST /upload`
Upload multiple images and get duplicate analysis results.

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv310
   venv310\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

Start the server:
```
python main.py
```

The server will run at `http://0.0.0.0:8000` and automatically reload when code changes.

## Technical Details

- Built with FastAPI
- Uses the ImageDedupAPI library for CNN-based duplicate detection
- Includes middleware for CORS and request logging
- Handles various image formats (JPG, PNG, GIF, BMP, TIFF)

## Development

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Submit a pull request