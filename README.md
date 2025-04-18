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

### `POST /upload/{user_id}`
Upload multiple images for a specific user and get duplicate analysis results.

### `GET /duplicates/{user_id}`
Returns grouped clusters of duplicate images for a specific user, organized into related sets.

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

### Development

Start the server in development mode with auto-reload:
```
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Alternatively, you can run:
```
python main.py
```

The server will run at `http://0.0.0.0:8000` and automatically reload when code changes.

## Deployment Options

### Local Docker Deployment

To run the application using Docker:

```
docker-compose up -d
```

This will build and run the application with the configuration specified in the Dockerfile and docker-compose.yml.

### Free Cloud Deployment Options

#### Render

1. Create a free account at [Render](https://render.com)
2. Create a new Web Service
3. Connect your GitHub repository
4. Select the Docker runtime
5. Configure environment variables if needed
6. Deploy

#### Railway

1. Create a free account at [Railway](https://railway.app)
2. Create a new project
3. Connect your GitHub repository
4. Railway will auto-detect the Dockerfile
5. Configure environment variables if needed
6. Deploy

#### Fly.io

1. Create a free account at [Fly.io](https://fly.io)
2. Install the flyctl CLI
3. Run `flyctl auth login`
4. In your project directory, run `flyctl launch`
5. Deploy with `flyctl deploy`

The application will run on Fly.io using the configuration in fly.toml, which sets up the appropriate region, port, and storage mounts.

## Technical Details

- Built with FastAPI
- Uses the ImageDedupAPI library for CNN-based duplicate detection
- Includes middleware for CORS and request logging
- Handles various image formats (JPG, PNG, GIF, BMP, TIFF)
- Uses Gunicorn with Uvicorn workers in production (via Procfile)
- Docker configuration for containerized deployment

## Development

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Submit a pull request