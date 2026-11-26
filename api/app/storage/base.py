from abc import ABC, abstractmethod
from typing import BinaryIO


class Storage(ABC):
    @abstractmethod
    async def upload(self, key: str, data: BinaryIO, content_type: str) -> str:
        """Upload data and return the storage key."""
        pass

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download data by key."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete data by key."""
        pass

    @abstractmethod
    async def signed_url(self, key: str, ttl_seconds: int) -> str:
        """Generate a signed URL for the given key."""
        pass
