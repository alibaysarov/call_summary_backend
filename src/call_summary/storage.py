"""Synchronous S3 adapter; call from sync endpoints or a worker thread."""

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import boto3
from botocore.config import Config

from call_summary.config import get_settings


class S3Storage:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        s = self.settings
        self.bucket = s.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url,
            region_name=s.s3_region,
            aws_access_key_id=s.s3_access_key_id.get_secret_value(),
            aws_secret_access_key=s.s3_secret_access_key.get_secret_value(),
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": s.s3_addressing_style},
                connect_timeout=3,
                read_timeout=10,
                retries={"max_attempts": 2},
            ),
        )

    def ready(self):
        self.client.head_bucket(Bucket=self.bucket)

    def put(self, key, data: bytes, content_type="application/octet-stream"):
        digest = sha256(data).hexdigest()
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": digest},
        )
        return digest

    def get(self, key, expected_sha256=None):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        try:
            data = response["Body"].read()
        finally:
            response["Body"].close()
        if expected_sha256 is not None and sha256(data).hexdigest() != expected_sha256:
            raise ValueError("Audio SHA-256 mismatch")
        return data

    def head(self, key):
        return self.client.head_object(Bucket=self.bucket, Key=key)

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def list(self, prefix="", *, cursor=None, limit=1000):
        if not 1 <= limit <= 1000:
            raise ValueError("S3 list limit must be between 1 and 1000")
        params = {"Bucket": self.bucket, "Prefix": prefix, "MaxKeys": limit}
        if cursor:
            params["ContinuationToken"] = cursor
        result = self.client.list_objects_v2(**params)
        return {
            "objects": result.get("Contents", []),
            "has_more": result["IsTruncated"],
            "cursor": result.get("NextContinuationToken"),
        }

    @contextmanager
    def download(self, key, expected_sha256):
        """Stream to disk, validate independently of ETag, clean up even on failure."""
        self.settings.audio_temp_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=self.settings.audio_temp_dir) as directory:
            path = Path(directory) / ("audio" + Path(key).suffix)
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            digest = sha256()
            try:
                with path.open("wb") as output:
                    for block in response["Body"].iter_chunks(1024 * 1024):
                        digest.update(block)
                        output.write(block)
            finally:
                response["Body"].close()
            if digest.hexdigest() != expected_sha256:
                raise ValueError("Audio SHA-256 mismatch")
            yield path
