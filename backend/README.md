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
PYTHONPATH=. python -m src.main --host 0.0.0.0 --port 8002
```

## API Documentation

Once the server is running, you can access the API documentation:

- Swagger UI: http://localhost:8002/docs
- ReDoc: http://localhost:8002/redoc

## Database Setup

The backend now targets Postgres by default.

- Default DB: `app_db`
- Default user: `app_user`
- Password: from `DB_PASSWORD` or `DB_PASSWORD_FILE`
- Default DSN format: `postgresql+psycopg://<user>:<password>@<host>:<port>/<db>`

Run migrations with Alembic:

```bash
alembic upgrade head
```

## Environment Variables

You can configure the application using environment variables:

```bash
# .env file (optional)
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DB_HOST=postgres
DB_PORT=5432
DB_NAME=app_db
DB_USER=app_user
DB_PASSWORD=change-me-local-password
```
