import logging

import httpx

from ..config import get_settings
from .base import GeneratedAudio, SoundGenerator
from .mock import MockGenerator

logger = logging.getLogger(__name__)


class ElevenLabsError(RuntimeError):
    """ElevenLabs request failed without a usable fallback."""


class ElevenLabsGenerator(SoundGenerator):
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.elevenlabs_api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        self.fallback_to_mock = settings.generator_fallback_to_mock

    async def generate(self, prompt: str, duration_seconds: int | None) -> GeneratedAudio:
        if not self.api_key:
            if self.fallback_to_mock:
                logger.warning("ElevenLabs API key missing; using mock generator")
                return await MockGenerator().generate(prompt, duration_seconds)
            raise ElevenLabsError("ElevenLabs API key not configured")

        body = {"text": prompt, "model_id": "eleven_text_to_sound_v2"}
        if duration_seconds is not None:
            body["duration_seconds"] = duration_seconds
        headers = {"xi-api-key": self.api_key}
        params = {"output_format": "mp3_44100_128"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/sound-generation",
                    json=body,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in {401, 402, 403} and self.fallback_to_mock:
                    logger.warning("ElevenLabs returned %s; using mock generator", status)
                    return await MockGenerator().generate(prompt, duration_seconds)
                detail = exc.response.text[:200]
                raise ElevenLabsError(f"ElevenLabs returned {status}: {detail}") from exc
            except httpx.RequestError as exc:
                raise ElevenLabsError(f"ElevenLabs request failed: {exc}") from exc

        return GeneratedAudio(
            response.content, "audio/mpeg", "elevenlabs-free-noncommercial"
        )
