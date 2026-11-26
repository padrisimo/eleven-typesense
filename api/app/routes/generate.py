import asyncio
import hashlib
import logging
from io import BytesIO

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import fetchone, get_connection
from ..factories import get_generator, get_storage
from ..search import upsert_sound

logger = logging.getLogger(__name__)
router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    duration_seconds: int | None = Field(default=None, ge=1, le=30)


class GenerateResponse(BaseModel):
    sound_id: int
    idempotent: bool
    indexed: bool
    license: str


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()


def audio_format(content_type: str) -> str:
    return "wav" if "wav" in content_type else "mp3"


@router.post("/generate", status_code=201)
async def generate_sound(request: GenerateRequest):
    settings = get_settings()
    prompt = request.prompt.strip()
    digest = prompt_hash(prompt)
    storage = get_storage()
    generator = get_generator()
    job_id: int | None = None

    async with get_connection() as conn:
        await conn.execute("SELECT pg_advisory_lock(hashtext(%s))", (digest,))
        try:
            existing = await fetchone(conn,
                "SELECT id, indexed_at, license FROM sounds WHERE prompt_hash = %s", (digest,)
            )
            if existing:
                return GenerateResponse(
                    sound_id=existing["id"],
                    idempotent=True,
                    indexed=existing["indexed_at"] is not None,
                    license=existing["license"],
                )

            used = await fetchone(conn,
                "SELECT count(*) AS n FROM generation_jobs "
                "WHERE created_at >= NOW() - INTERVAL '24 hours'"
            )
            if used["n"] >= settings.generation_daily_limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily generation limit of {settings.generation_daily_limit} reached",
                )

            async with conn.transaction():
                job = await fetchone(conn,
                    "INSERT INTO generation_jobs (prompt, prompt_hash, status) "
                    "VALUES (%s, %s, 'pending') RETURNING id",
                    (prompt, digest),
                )
                job_id = job["id"]

            audio = await generator.generate(prompt, request.duration_seconds)
            key = f"ai/{digest[:2]}/{digest}.{audio_format(audio.content_type)}"
            await storage.upload(key, BytesIO(audio.data), audio.content_type)

            duration_ms = request.duration_seconds * 1000 if request.duration_seconds else 1000
            async with conn.transaction():
                sound = await fetchone(conn,
                    """
                    INSERT INTO sounds (
                        title, description, category, tags, duration_ms, bpm, format,
                        sample_rate, file_key, source, prompt_hash, license, is_active,
                        created_at, indexed_at
                    ) VALUES (%s, %s, 'AI', %s, %s, NULL, %s, 44100, %s, 'ai', %s, %s,
                              TRUE, NOW(), NULL)
                    RETURNING id, title, description, category, tags, duration_ms, bpm,
                              format, source, created_at
                    """,
                    (
                        prompt[:120],
                        prompt,
                        ["ai", "generated"],
                        duration_ms,
                        audio_format(audio.content_type),
                        key,
                        digest,
                        audio.license,
                    ),
                )
                await conn.execute(
                    "UPDATE generation_jobs SET status = 'done', sound_id = %s WHERE id = %s",
                    (sound["id"], job_id),
                )

            document = {
                "id": str(sound["id"]),
                "title": sound["title"],
                "description": sound["description"],
                "tags": sound["tags"],
                "category": sound["category"],
                "duration_ms": sound["duration_ms"],
                "bpm": sound["bpm"],
                "format": sound["format"],
                "source": sound["source"],
                "created_at": int(sound["created_at"].timestamp()),
            }
            indexed = True
            try:
                await asyncio.to_thread(upsert_sound, document)
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE sounds SET indexed_at = NOW() WHERE id = %s", (sound["id"],)
                    )
            except Exception:
                indexed = False
                logger.warning(
                    "Typesense upsert failed for sound %s; indexed_at stays NULL",
                    sound["id"],
                    exc_info=True,
                )

            return GenerateResponse(
                sound_id=sound["id"],
                idempotent=False,
                indexed=indexed,
                license=audio.license,
            )
        except HTTPException:
            raise
        except Exception as exc:
            if job_id is not None:
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE generation_jobs SET status = 'failed', error = %s WHERE id = %s",
                        (str(exc)[:500], job_id),
                    )
            raise HTTPException(status_code=502, detail=f"Generation failed: {exc}") from exc
        finally:
            await conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", (digest,))
