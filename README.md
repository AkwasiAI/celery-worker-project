# Celery Worker Project

This project contains the Celery worker and task definitions for background processing.

## Setup

1.  Create a virtual environment: `python -m venv venv`
2.  Activate it: `source venv/bin/activate` (Linux/macOS) or `venv\Scripts\activate` (Windows)
3.  Install dependencies: `pip install -r requirements.txt`

## Running Locally (Requires a local Redis server)

1.  Ensure a Redis server is running on `localhost:6379`.
2.  Set the `REDIS_IP` environment variable if needed: `export REDIS_IP=localhost`
3.  Run the worker: `celery -A celery_config.celery_app worker --loglevel=info`

## Building and Pushing the Docker Image

### Configure Docker for GCP Artifact Registry

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### Build the Docker Image

```bash
docker build -f Dockerfile -t us-central1-docker.pkg.dev/hedgefundintelligence/celery-workers/hello-worker:latest .
```

### Push to Google Cloud Artifact Registry

```bash
docker push us-central1-docker.pkg.dev/hedgefundintelligence/celery-workers/hello-worker:latest
```