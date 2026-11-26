from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.generation.mock import MockGenerator
from app.routes.generate import GenerateRequest, audio_format, prompt_hash
from app.storage.local import sign_local_url


def test_prompt_hash_is_stable_case_sensitive_and_ignores_outer_whitespace():
    assert prompt_hash("  Heavy Door  ") == prompt_hash("Heavy Door")
    assert prompt_hash("Heavy Door") != prompt_hash("heavy door")
    assert len(prompt_hash("Heavy Door")) == 64


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        ("audio/mpeg", "mp3"),
        ("audio/wav", "wav"),
        ("audio/x-wav", "wav"),
    ],
)
def test_audio_format_maps_content_type(content_type, expected):
    assert audio_format(content_type) == expected


def test_generate_request_validates_prompt_and_duration():
    request = GenerateRequest(prompt="metal door", duration_seconds=30)
    assert request.prompt == "metal door"
    assert request.duration_seconds == 30

    with pytest.raises(ValidationError):
        GenerateRequest(prompt="", duration_seconds=1)

    with pytest.raises(ValidationError):
        GenerateRequest(prompt="metal door", duration_seconds=31)


def test_sign_local_url_is_deterministic_and_secret_dependent():
    settings = SimpleNamespace(local_signing_secret="test-secret")

    with patch("app.storage.local.get_settings", return_value=settings):
        first = sign_local_url("ai/ab/file.mp3", 123)
        repeated = sign_local_url("ai/ab/file.mp3", 123)
        other_expiry = sign_local_url("ai/ab/file.mp3", 124)

    assert first == repeated
    assert first != other_expiry
    assert len(first) == 64


async def test_mock_generator_returns_a_non_empty_mp3():
    audio = await MockGenerator().generate("anything", 3)

    assert audio.content_type == "audio/mpeg"
    assert audio.license == "mock"
    assert len(audio.data) > 0
