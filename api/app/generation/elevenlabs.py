import httpx
from .base import SoundGenerator
from ..config import get_settings


class ElevenLabsGenerator(SoundGenerator):
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.elevenlabs_api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        self.fallback_to_mock = settings.generator_fallback_to_mock

    async def generate(self, prompt: str, duration_seconds: int | None) -> tuple[bytes, str]:
        if not self.api_key:
            if self.fallback_to_mock:
                from .mock import MockGenerator
                return await MockGenerator().generate(prompt, duration_seconds)
            raise ValueError("ElevenLabs API key not configured")

        # TODO: Implement actual ElevenLabs sound effects generation
        # Check the official docs for the exact endpoint and parameters
        # https://elevenlabs.io/docs/api-reference/sound-generation
        raise NotImplementedError("ElevenLabs generator not implemented yet")

    def get_license(self) -> str:
        return "elevenlabs-free-noncommercial"
