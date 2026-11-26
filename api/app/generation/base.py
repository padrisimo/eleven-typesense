from abc import ABC, abstractmethod
from typing import BinaryIO


class SoundGenerator(ABC):
    @abstractmethod
    async def generate(self, prompt: str, duration_seconds: int | None) -> tuple[bytes, str]:
        """
        Generate audio from prompt.
        Returns (audio_data, content_type).
        """
        pass

    @abstractmethod
    def get_license(self) -> str:
        """Return the license string for generated audio."""
        pass
