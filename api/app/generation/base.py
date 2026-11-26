from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedAudio:
    data: bytes
    content_type: str
    license: str


class SoundGenerator(ABC):
    @abstractmethod
    async def generate(self, prompt: str, duration_seconds: int | None) -> GeneratedAudio:
        """Generate audio and report the license that applies to it."""
