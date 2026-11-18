"""Where backup archives live: a local directory or an S3-compatible bucket."""
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse


class FileStore:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, local_path: str, key: str) -> None:
        shutil.copyfile(local_path, self.root / key)

    def get(self, key: str, local_path: str) -> None:
        shutil.copyfile(self.root / key, local_path)

    def delete(self, key: str) -> None:
        (self.root / key).unlink(missing_ok=True)


class S3Store:
    def __init__(self, bucket: str, prefix: str):
        import boto3

        self.client = boto3.client("s3", endpoint_url=os.environ.get("PGRV_S3_ENDPOINT") or None)
        self.bucket, self.prefix = bucket, prefix.strip("/")

    def _key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def put(self, local_path: str, key: str) -> None:
        self.client.upload_file(local_path, self.bucket, self._key(key))

    def get(self, key: str, local_path: str) -> None:
        self.client.download_file(self.bucket, self._key(key), local_path)

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))


def open_store(url: str):
    u = urlparse(url)
    if u.scheme == "file":
        return FileStore((u.netloc + u.path) or ".")
    if u.scheme == "s3":
        return S3Store(u.netloc, u.path)
    raise ValueError(f"unsupported store URL: {url}")
