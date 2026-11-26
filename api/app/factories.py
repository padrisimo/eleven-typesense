from .config import get_settings
from .generation.base import SoundGenerator
from .generation.elevenlabs import ElevenLabsGenerator
from .generation.mock import MockGenerator
from .storage.base import Storage
from .storage.gcs import GCSStorage
from .storage.local import LocalStorage


def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "gcs":
        return GCSStorage()
    return LocalStorage()


def get_generator() -> SoundGenerator:
    settings = get_settings()
    if settings.generator == "elevenlabs":
        return ElevenLabsGenerator()
    return MockGenerator()
