import os
import aiofiles
from pathlib import Path
from typing import BinaryIO
from .base import Storage
from ..config import get_settings


class LocalStorage(Storage):
    def __init__(self, base_path: str | None = None):
        settings = get_settings()
        self.base_path = Path(base_path or settings.local_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload(self, key: str, data: BinaryIO, content_type: str) -> str:
        file_path = self.base_path / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, "wb") as f:
            content = data.read()
            await f.write(content)
        return key

    async def download(self, key: str) -> bytes:
        file_path = self.base_path / key
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> None:
        file_path = self.base_path / key
        if file_path.exists():
            file_path.unlink()

    async def signed_url(self, key: str, ttl_seconds: int) -> str:
        # In local mode, just return a local URL (would be proxied by API in real impl)
        return f"/audio/{key}"
