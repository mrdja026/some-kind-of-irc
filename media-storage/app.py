import io
import io
import os
from uuid import uuid4
from urllib.parse import quote
from typing import Optional

import boto3
import requests
from flask import Flask, jsonify, redirect, request
from botocore.exceptions import EndpointConnectionError, ClientError
from werkzeug.exceptions import RequestEntityTooLarge
import json
from PIL import Image, ImageOps, UnidentifiedImageError


ALLOWED_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

PIL_FORMATS = {
    "image/jpeg": ("JPEG", {"quality": 85, "optimize": True}),
    "image/png": ("PNG", {"optimize": True}),
    "image/webp": ("WEBP", {"quality": 85, "method": 6}),
}


def _get_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _should_resize(width: int, height: int, max_width: int, max_height: int) -> bool:
    return width > max_width or height > max_height


def _prepare_image_for_format(image: Image.Image, format_name: str) -> Image.Image:
    if format_name == "JPEG" and image.mode not in {"RGB", "L"}:
        return image.convert("RGB")
    return image


def _encode_image(image: Image.Image, content_type: str) -> bytes:
    format_name, save_kwargs = PIL_FORMATS[content_type]
    prepared = _prepare_image_for_format(image, format_name)
    output = io.BytesIO()
    prepared.save(output, format=format_name, **save_kwargs)
    return output.getvalue()


app = Flask(__name__)

max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "10"))
app.config["MAX_CONTENT_LENGTH"] = max_upload_mb * 1024 * 1024

original_max_width = _get_int_env("MEDIA_ORIGINAL_MAX_WIDTH", 3840)
original_max_height = _get_int_env("MEDIA_ORIGINAL_MAX_HEIGHT", 2160)
display_max_width = _get_int_env("MEDIA_DISPLAY_MAX_WIDTH", 1920)
display_max_height = _get_int_env("MEDIA_DISPLAY_MAX_HEIGHT", 1080)

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


def _ensure_bucket_exists():
    """Ensure bucket exists and is publicly readable."""
    created = False
    try:
        s3_client.head_bucket(Bucket=minio_bucket)
    except ClientError:
        create_kwargs = {"Bucket": minio_bucket}
        if minio_region and minio_region != "us-east-1":
            create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": minio_region}
        s3_client.create_bucket(**create_kwargs)
        created = True

    # Always (re)apply policy in case bucket pre-existed without it
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{minio_bucket}/*"],
            }
        ],
    }
    s3_client.put_bucket_policy(Bucket=minio_bucket, Policy=json.dumps(policy))
    if created:
        print(f"Bucket '{minio_bucket}' created and policy applied.")
    else:
        print(f"Bucket '{minio_bucket}' found; policy ensured.")


@app.get("/health")
def health_check():
    try:
        s3_client.list_buckets()
    except EndpointConnectionError:
        return {"status": "degraded", "minio": "unreachable"}, 503
    return {"status": "ok"}


@app.post("/upload")
def upload_file():
    try:
        _ensure_bucket_exists()
    except ClientError as exc:
        return jsonify({"detail": f"Storage bucket error: {exc}"}), 503
    except EndpointConnectionError:
        return jsonify({"detail": "Storage unavailable"}), 503

    user_id, error = _verify_session()
    if error == "auth_unavailable":
        return jsonify({"detail": "Auth service unavailable"}), 503
    if error:
        return jsonify({"detail": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"detail": "Missing file"}), 400

    file = request.files["file"]
    content_type = file.mimetype or file.content_type
    if content_type not in ALLOWED_MIME_TYPES:
        return jsonify({"detail": "Unsupported media type"}), 415

    extension = ALLOWED_MIME_TYPES[content_type]

    try:
        file.stream.seek(0)
        file_bytes = file.stream.read()
    except OSError:
        return jsonify({"detail": "Failed to read upload"}), 400

    if not file_bytes:
        return jsonify({"detail": "Empty upload"}), 400

    try:
        image = Image.open(io.BytesIO(file_bytes))
        image = ImageOps.exif_transpose(image)
        if image is None:
            return jsonify({"detail": "Invalid image"}), 415
        image.load()
    except UnidentifiedImageError:
        return jsonify({"detail": "Invalid image"}), 415

    width, height = image.size
    needs_original_resize = _should_resize(
        width,
        height,
        original_max_width,
        original_max_height,
    )
    needs_display_resize = _should_resize(
        width,
        height,
        display_max_width,
        display_max_height,
    )

    if needs_original_resize:
        resized_original = ImageOps.contain(
            image,
            (original_max_width, original_max_height),
            Image.Resampling.LANCZOS,
        )
        original_bytes = _encode_image(resized_original, content_type)
    else:
        original_bytes = file_bytes

    if needs_display_resize:
        resized_display = ImageOps.contain(
            image,
            (display_max_width, display_max_height),
            Image.Resampling.LANCZOS,
        )
        display_bytes = _encode_image(resized_display, content_type)
    else:
        display_bytes = file_bytes

    base_id = uuid4().hex
    base_prefix = f"uploads/{user_id}/{base_id}"
    original_key = f"{base_prefix}/original.{extension}"
    display_key = f"{base_prefix}/display.{extension}"

    try:
        s3_client.upload_fileobj(
            io.BytesIO(original_bytes),
            minio_bucket,
            original_key,
            ExtraArgs={"ContentType": content_type},
        )
        s3_client.upload_fileobj(
            io.BytesIO(display_bytes),
            minio_bucket,
            display_key,
            ExtraArgs={"ContentType": content_type},
        )
    except EndpointConnectionError:
        return jsonify({"detail": "Storage unavailable"}), 503

    return jsonify(
        {
            "key": display_key,
            "url": _build_public_url(display_key),
            "contentType": content_type,
            "size": len(display_bytes),
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
