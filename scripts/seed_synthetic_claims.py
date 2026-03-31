#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a MinIO bucket and upload synthetic claims JSON files."
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        help="Directory containing synthetic_claims JSON files.",
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("SYNTHETIC_CLAIMS_BUCKET", "synt-data"),
        help="Bucket name for synthetic claims.",
    )
    parser.add_argument(
        "--prefix",
        default=os.getenv("SYNTHETIC_CLAIMS_PREFIX", "synthetic_claims"),
        help="Object key prefix for uploaded JSON files.",
    )
    return parser.parse_args()


def build_s3_client() -> tuple[BaseClient, str, bool]:
    endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    region = os.getenv("MINIO_REGION", "us-east-1")
    use_ssl = os.getenv("MINIO_USE_SSL", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    access = os.getenv("MINIO_ACCESS_KEY")
    secret = os.getenv("MINIO_SECRET_KEY")
    if not access or not secret:
        raise SystemExit("MINIO_ACCESS_KEY and MINIO_SECRET_KEY are required")
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region,
        use_ssl=use_ssl,
    )
    return s3, region, use_ssl


def ensure_bucket(s3: BaseClient, bucket: str, region: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"Bucket '{bucket}' already exists.")
        return
    except ClientError:
        create_kwargs: dict[str, object] = {"Bucket": bucket}
        if region and region != "us-east-1":
            create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
        s3.create_bucket(**create_kwargs)
        print(f"Bucket '{bucket}' created.")


def upload_json_files(
    s3: BaseClient, bucket: str, prefix: str, source_dir: Path
) -> int:
    files = sorted(
        path
        for path in source_dir.iterdir()
        if path.is_file() and path.suffix == ".json"
    )
    if not files:
        raise SystemExit(f"No .json files found in {source_dir}")

    normalized_prefix = prefix.strip("/")
    uploaded = 0
    for path in files:
        key = f"{normalized_prefix}/{path.name}" if normalized_prefix else path.name
        s3.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={"ContentType": "application/json"},
        )
        uploaded += 1
    return uploaded


def upload_companion_folders(
    s3: BaseClient, bucket: str, source_dir: Path
) -> int:
    """Upload companion data folders ({claim-id}-data/data/*) to MinIO."""
    MIME_MAP = {
        ".json": "application/json",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }
    uploaded = 0
    for data_dir in sorted(source_dir.iterdir()):
        if not data_dir.is_dir() or not data_dir.name.endswith("-data"):
            continue
        inner = data_dir / "data"
        if not inner.is_dir():
            continue
        for file_path in sorted(inner.iterdir()):
            if not file_path.is_file():
                continue
            ext = file_path.suffix.lower()
            content_type = MIME_MAP.get(ext)
            if not content_type:
                continue
            key = f"{data_dir.name}/data/{file_path.name}"
            s3.upload_file(
                str(file_path),
                bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            uploaded += 1
    return uploaded


def main() -> None:
    args = parse_args()
    source_dir = Path(args.source_dir)
    if not source_dir.is_dir():
        raise SystemExit(f"Source directory does not exist: {source_dir}")

    s3, region, _ = build_s3_client()
    ensure_bucket(s3, args.bucket, region)
    uploaded = upload_json_files(s3, args.bucket, args.prefix, source_dir)
    companion_uploaded = upload_companion_folders(s3, args.bucket, source_dir)
    prefix = args.prefix.strip("/")
    prefix_display = f"{prefix}/" if prefix else ""
    print(f"Uploaded {uploaded} JSON files to s3://{args.bucket}/{prefix_display}")
    if companion_uploaded:
        print(f"Uploaded {companion_uploaded} companion data files to s3://{args.bucket}/")


if __name__ == "__main__":
    main()
