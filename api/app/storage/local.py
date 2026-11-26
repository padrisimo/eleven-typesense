import hashlib
import hmac
import time
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

from ..config import get_settings
from .base import Storage


def sign_local_url(key: str, expires: int) -> str:
    settings = get_settings()
    message = f"{key}:{expires}".encode()
    secret = settings.local_signing_secret.encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


class LocalStorage(Storage):
    def __init__(self, base_path: str | None = None):
        settings = get_settings()
        self.base_path = Path(base_path or settings.local_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload(self, key: str, data: BinaryIO, content_type: str) -> str:
        path = self.base_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        data.seek(0)
        path.write_bytes(data.read())
        return key

    async def download(self, key: str) -> bytes:
        return (self.base_path / key).read_bytes()

    async def delete(self, key: str) -> None:
        (self.base_path / key).unlink(missing_ok=True)

    async def signed_url(self, key: str, ttl_seconds: int) -> str:
        expires = int(time.time()) + ttl_seconds
        signature = sign_local_url(key, expires)
        return f"/audio/{quote(key, safe='/')}?expires={expires}&signature={signature}"
