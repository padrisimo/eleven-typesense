from typing import BinaryIO
from .base import Storage
from ..config import get_settings


class GCSStorage(Storage):
    def __init__(self):
        settings = get_settings()
        self.bucket_name = settings.gcs_bucket
        self.project_id = settings.gcs_project_id
        self.credentials_path = settings.gcs_credentials_path
        # TODO: Implement with google-cloud-storage
        # Use V4 signed URLs with IAM service account (no key on disk on GCE)
        raise NotImplementedError("GCS storage not implemented yet")

    async def upload(self, key: str, data: BinaryIO, content_type: str) -> str:
        raise NotImplementedError

    async def download(self, key: str) -> bytes:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    async def signed_url(self, key: str, ttl_seconds: int) -> str:
        raise NotImplementedError
