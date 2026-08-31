from __future__ import annotations

from pathlib import Path

import boto3
from botocore.client import BaseClient

from .config import Settings


class R2Storage:
    def __init__(self, settings: Settings, client: BaseClient | None = None):
        self.bucket = settings.r2_bucket
        self.client = client or boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )

    def upload(self, source: Path, key: str, content_type: str) -> None:
        self.client.upload_file(str(source), self.bucket, key, ExtraArgs={"ContentType": content_type})

    def upload_bytes(self, content: bytes, key: str, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.client.exceptions.ClientError as error:
            if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            raise

    def size(self, key: str) -> int:
        response = self.client.head_object(Bucket=self.bucket, Key=key)
        return int(response["ContentLength"])

    def temporary_input_url(self, key: str, expires_in_seconds: int = 10 * 60) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )

    def temporary_download_url(self, key: str, expires_in_seconds: int = 15 * 60) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )
