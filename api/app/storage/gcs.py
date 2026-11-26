import asyncio
from datetime import timedelta
from typing import BinaryIO

from ..config import get_settings
from .base import Storage


class GCSStorage(Storage):
    def __init__(self):
        from google.cloud import storage
        from google.oauth2 import service_account

        settings = get_settings()
        if not settings.gcs_bucket:
            raise RuntimeError("GCS_BUCKET is required when STORAGE_BACKEND=gcs")
        self.settings = settings
        credentials = None
        if settings.gcs_credentials_path:
            credentials = service_account.Credentials.from_service_account_file(
                settings.gcs_credentials_path
            )
        self.client = storage.Client(project=settings.gcs_project_id, credentials=credentials)
        self.bucket = self.client.bucket(settings.gcs_bucket)

    def _blob(self, key: str):
        return self.bucket.blob(key)

    async def upload(self, key: str, data: BinaryIO, content_type: str) -> str:
        data.seek(0)
        await asyncio.to_thread(self._blob(key).upload_from_file, data, content_type=content_type)
        return key

    async def download(self, key: str) -> bytes:
        return await asyncio.to_thread(self._blob(key).download_as_bytes)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._blob(key).delete)

    async def signed_url(self, key: str, ttl_seconds: int) -> str:
        options = {
            "version": "v4",
            "expiration": timedelta(seconds=ttl_seconds),
            "method": "GET",
        }
        if self.settings.gcs_signer_service_account:
            from google.auth import default
            from google.auth.transport.requests import Request

            credentials, _ = default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            await asyncio.to_thread(credentials.refresh, Request())
            options["service_account_email"] = self.settings.gcs_signer_service_account
            options["access_token"] = credentials.token
        return await asyncio.to_thread(self._blob(key).generate_signed_url, **options)
