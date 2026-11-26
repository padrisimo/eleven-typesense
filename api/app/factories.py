from .config import get_settings
from .storage.base import Storage
from .storage.local import LocalStorage
from .storage.gcs import GCSStorage
from .generation.base import SoundGenerator
from .generation.mock import MockGenerator
from .generation.elevenlabs import ElevenLabsGenerator


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
