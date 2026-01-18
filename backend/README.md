# Backend Setup

## Requirements

- Python 3.10+
- pip (Python package manager)

## Setup Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Activate virtual environment (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Run the Server

```bash
# Activate virtual environment first (if not already active)
# venv\Scripts\activate (Windows)
# source venv/bin/activate (macOS/Linux)

# Run the development server
PYTHONPATH=. python -m src.main --host 0.0.0.0 --port 8000
```

## API Documentation

Once the server is running, you can access the API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Database Setup

The application uses SQLite by default. The database file will be created automatically when the server starts for the first time.

## Environment Variables

You can configure the application using environment variables:

```bash
# .env file (optional)
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=sqlite:///./chat.db
```
