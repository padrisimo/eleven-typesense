import aiofiles
from pathlib import Path
from .base import SoundGenerator
from ..config import get_settings


class MockGenerator(SoundGenerator):
    def __init__(self):
        settings = get_settings()
        self.asset_path = Path(settings.local_storage_path).parent / "assets" / "sample.mp3"

    async def generate(self, prompt: str, duration_seconds: int | None) -> tuple[bytes, str]:
        async with aiofiles.open(self.asset_path, "rb") as f:
            data = await f.read()
        return data, "audio/mpeg"

    def get_license(self) -> str:
        return "mock"
