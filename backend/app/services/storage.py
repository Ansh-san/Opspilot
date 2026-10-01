"""
OpsPilot — Storage Provider Abstraction
"""

import abc
import os
import uuid
from pathlib import Path

class StorageProvider(abc.ABC):
    @abc.abstractmethod
    def upload(self, content: bytes, org_id: uuid.UUID, filename: str) -> str:
        """Uploads a file and returns its URI or path."""
        pass

    @abc.abstractmethod
    def download(self, file_uri: str) -> bytes:
        """Downloads a file given its URI or path."""
        pass

    @abc.abstractmethod
    def delete(self, file_uri: str) -> None:
        """Deletes a file given its URI or path."""
        pass


class LocalStorageProvider(StorageProvider):
    """Stores files on the local filesystem. Suitable for development."""
    def __init__(self, upload_root: str = "/app/data/uploads"):
        self.upload_root = Path(upload_root)

    def upload(self, content: bytes, org_id: uuid.UUID, filename: str) -> str:
        dest_dir = self.upload_root / str(org_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = f"{uuid.uuid4().hex}_{filename}"
        dest = dest_dir / safe_filename
        dest.write_bytes(content)
        return str(dest)

    def download(self, file_uri: str) -> bytes:
        path = Path(file_uri)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_uri}")
        return path.read_bytes()

    def delete(self, file_uri: str) -> None:
        path = Path(file_uri)
        if path.exists():
            path.unlink()


class S3StorageProvider(StorageProvider):
    """Stores files in AWS S3. Suitable for production. Relies on IAM roles for auth (no hardcoded keys)."""
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        import boto3
        # Rely on default credential provider chain (IAM Roles / ECS Task Roles)
        self.s3 = boto3.client('s3')

    def upload(self, content: bytes, org_id: uuid.UUID, filename: str) -> str:
        safe_filename = f"{org_id}/{uuid.uuid4().hex}_{filename}"
        self.s3.put_object(Bucket=self.bucket_name, Key=safe_filename, Body=content)
        return f"s3://{self.bucket_name}/{safe_filename}"

    def download(self, file_uri: str) -> bytes:
        if not file_uri.startswith(f"s3://{self.bucket_name}/"):
            raise ValueError("Invalid S3 URI")
        key = file_uri.replace(f"s3://{self.bucket_name}/", "")
        response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
        return response['Body'].read()

    def delete(self, file_uri: str) -> None:
        if not file_uri.startswith(f"s3://{self.bucket_name}/"):
            return
        key = file_uri.replace(f"s3://{self.bucket_name}/", "")
        self.s3.delete_object(Bucket=self.bucket_name, Key=key)

def get_storage_provider() -> StorageProvider:
    # In a real app, this might check settings.ENVIRONMENT
    # For now, we return LocalStorageProvider
    return LocalStorageProvider()
