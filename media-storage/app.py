import os
from uuid import uuid4
from urllib.parse import quote
from typing import Optional

import boto3
import requests
from flask import Flask, jsonify, redirect, request
from botocore.exceptions import EndpointConnectionError
from werkzeug.exceptions import RequestEntityTooLarge


ALLOWED_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _get_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


app = Flask(__name__)

max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "10"))
app.config["MAX_CONTENT_LENGTH"] = max_upload_mb * 1024 * 1024

minio_endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
minio_public_endpoint = os.getenv("MINIO_PUBLIC_ENDPOINT", minio_endpoint)
minio_bucket = os.getenv("MINIO_BUCKET", "media")
minio_region = os.getenv("MINIO_REGION", "us-east-1")
minio_access_key = os.getenv("MINIO_ACCESS_KEY")
minio_secret_key = os.getenv("MINIO_SECRET_KEY")
minio_use_ssl = _get_bool(os.getenv("MINIO_USE_SSL"), False)

backend_verify_url = os.getenv("BACKEND_VERIFY_URL", "http://localhost:8002/auth/me")
public_base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:9101")

s3_client = boto3.client(
    "s3",
    endpoint_url=minio_endpoint,
    aws_access_key_id=minio_access_key,
    aws_secret_access_key=minio_secret_key,
    region_name=minio_region,
    use_ssl=minio_use_ssl,
)


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(_error):
    return jsonify({"detail": f"File exceeds {max_upload_mb} MB limit"}), 413


def _verify_session():
    try:
        response = requests.get(
            backend_verify_url,
            cookies=request.cookies,
            timeout=5,
        )
    except requests.RequestException:
        return None, "auth_unavailable"

    if response.status_code != 200:
        return None, "unauthorized"

    try:
        payload = response.json()
    except ValueError:
        return None, "invalid_auth_response"

    user_id = payload.get("id")
    if not user_id:
        return None, "invalid_auth_response"

    return user_id, None


def _build_public_url(key: str) -> str:
    return f"{public_base_url.rstrip('/')}/media/{key}"


@app.get("/health")
def health_check():
    try:
        s3_client.list_buckets()
    except EndpointConnectionError:
        return {"status": "degraded", "minio": "unreachable"}, 503
    return {"status": "ok"}


@app.post("/upload")
def upload_file():
    user_id, error = _verify_session()
    if error == "auth_unavailable":
        return jsonify({"detail": "Auth service unavailable"}), 503
    if error:
        return jsonify({"detail": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"detail": "Missing file"}), 400

    file = request.files["file"]
    content_type = file.mimetype
    if content_type not in ALLOWED_MIME_TYPES:
        return jsonify({"detail": "Unsupported media type"}), 415

    extension = ALLOWED_MIME_TYPES[content_type]
    key = f"uploads/{user_id}/{uuid4().hex}.{extension}"

    try:
        s3_client.upload_fileobj(
            file.stream,
            minio_bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
    except EndpointConnectionError:
        return jsonify({"detail": "Storage unavailable"}), 503

    return jsonify(
        {
            "key": key,
            "url": _build_public_url(key),
            "contentType": content_type,
            "size": request.content_length,
        }
    )


@app.get("/media/<path:key>")
def get_media(key: str):
    encoded_key = quote(key)
    url = f"{minio_public_endpoint.rstrip('/')}/{minio_bucket}/{encoded_key}"
    return redirect(url, code=302)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9101"))
    app.run(host="0.0.0.0", port=port)
