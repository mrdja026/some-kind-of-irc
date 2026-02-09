# Data Processor Service

A Django REST framework microservice for document annotation, OCR extraction, and template management.

## Overview

The data-processor service provides:

- **Document Upload & Processing**: Upload images for OCR text extraction
- **Annotation Management**: Create and manage bounding box annotations on documents
- **Template Management**: Save and apply reusable annotation templates
- **Data Export**: Export extracted data as JSON, CSV, or SQL

## Architecture

This is a standalone microservice that:

- Runs independently from the main FastAPI backend
- Uses in-memory storage for MVP (data cleared on restart)
- Integrates with MinIO for image storage
- Communicates with the FastAPI backend for channel/user context

## Tech Stack

- **Framework**: Django 4.2 with Django REST Framework
- **OCR Engine**: Tesseract OCR 5.x
- **Image Processing**: OpenCV, scikit-image
- **Storage**: In-memory (MVP), MinIO for images
- **Server**: Gunicorn

## API Endpoints

| Endpoint               | Method | Description                 |
| ---------------------- | ------ | --------------------------- |
| `/api/health`          | GET    | Health check                |
| `/api/documents/`      | GET    | List documents              |
| `/api/documents/`      | POST   | Upload and process document |
| `/api/documents/{id}/` | GET    | Get document details        |
| `/api/documents/{id}/` | PUT    | Update document             |
| `/api/documents/{id}/` | DELETE | Delete document             |
| `/api/templates/`      | GET    | List templates              |
| `/api/templates/`      | POST   | Create template             |
| `/api/templates/{id}/` | GET    | Get template details        |
| `/api/templates/{id}/` | PUT    | Update template             |
| `/api/templates/{id}/` | DELETE | Delete template             |

## Configuration

Environment variables (with defaults):

| Variable           | Default                             | Description             |
| ------------------ | ----------------------------------- | ----------------------- |
| `DEBUG`            | `false`                             | Enable debug mode       |
| `ALLOWED_HOSTS`    | `*`                                 | Allowed host headers    |
| `ALLOWED_ORIGINS`  | `http://localhost,http://127.0.0.1` | CORS allowed origins    |
| `MINIO_ENDPOINT`   | `http://minio:9000`                 | MinIO internal endpoint |
| `MINIO_BUCKET`     | `media`                             | MinIO bucket name       |
| `MINIO_ACCESS_KEY` | `minioadmin`                        | MinIO access key        |
| `MINIO_SECRET_KEY` | `minioadmin`                        | MinIO secret key        |
| `BACKEND_URL`      | `http://backend:8002`               | FastAPI backend URL     |
| `MAX_IMAGE_WIDTH`  | `1024`                              | Maximum image width     |
| `MAX_IMAGE_HEIGHT` | `1024`                              | Maximum image height    |

## Local Development

The service is part of the docker-compose stack. To run:

```bash
./deploy-local.sh
```

Access the API at: `http://localhost/data-processor/api/`

## Image Processing Constraints

- Maximum image dimensions: 1024x1024 pixels (larger images auto-resized)
- Sequential document processing (one at a time)
- Supported formats: PNG, JPG, TIFF

## MVP Limitations

- **In-memory storage**: All data is lost on service restart
- **No persistent database**: Templates and documents exist only in memory
- **Single-user sessions**: One user per document at a time
- **SQLite-only SQL export**: Export format limited to SQLite syntax

## Directory Structure

```
data-processor/
├── Dockerfile
├── requirements.txt
├── manage.py
├── README.md
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── api/
│   ├── __init__.py
│   ├── apps.py
│   ├── urls.py
│   └── views.py
├── services/
│   └── __init__.py
└── storage/
    └── __init__.py
```
