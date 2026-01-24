# Storage Service

Flask-based upload proxy for MinIO. Authenticated uploads are validated against the backend session, and public media URLs redirect to MinIO objects.

## Configuration

Environment variables:

- `MINIO_ENDPOINT` (default: `http://localhost:9000`)
- `MINIO_PUBLIC_ENDPOINT` (default: `MINIO_ENDPOINT`)
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_BUCKET` (default: `media`)
- `MINIO_REGION` (default: `us-east-1`)
- `MINIO_USE_SSL` (default: `false`)
- `BACKEND_VERIFY_URL` (default: `http://localhost:8002/auth/me`)
- `PUBLIC_BASE_URL` (default: `http://localhost:9101`)
- `MAX_UPLOAD_MB` (default: `10`)
- `PORT` (default: `9101`)

## Run

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Local MinIO (No Docker)

1) Download `minio.exe` for Windows and place it at `media-storage/minio.exe`.
2) Start MinIO (data stored in `media-storage/data`):

```bash
pixi run minio
```

3) Open the console at `http://localhost:9001` and create the `media` bucket.
   The S3 API runs on `http://localhost:9000`, which is what the storage service uses.
4) Set the bucket to public read (Anonymous access) so redirects work.

## Upload Example

```bash
curl -i -X POST http://localhost:9101/upload \
  -H "Cookie: access_token=Bearer <token>" \
  -F "file=@sample.jpg"
```
