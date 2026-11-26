from pathlib import Path

from .base import GeneratedAudio, SoundGenerator


class MockGenerator(SoundGenerator):
    def __init__(self):
        self.asset_path = Path(__file__).resolve().parents[2] / "assets" / "sample.mp3"

    async def generate(self, prompt: str, duration_seconds: int | None) -> GeneratedAudio:
        return GeneratedAudio(self.asset_path.read_bytes(), "audio/mpeg", "mock")
