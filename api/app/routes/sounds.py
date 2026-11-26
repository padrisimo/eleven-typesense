import hmac
import time
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse

from ..config import get_settings
from ..db import fetchone, get_connection
from ..factories import get_storage
from ..storage.local import sign_local_url

router = APIRouter(tags=["sounds"])


async def load_sound(sound_id: int) -> dict:
    async with get_connection() as conn:
        sound = await fetchone(conn,
            "SELECT * FROM sounds WHERE id = %s AND is_active", (sound_id,)
        )
    if sound is None:
        raise HTTPException(status_code=404, detail="Sound not found")
    return sound


@router.get("/sounds/{sound_id}")
async def get_sound(sound_id: int):
    return await load_sound(sound_id)


@router.get("/sounds/{sound_id}/preview")
async def preview_sound(sound_id: int):
    sound = await load_sound(sound_id)
    url = await get_storage().signed_url(sound["file_key"], 30)
    return {"url": url, "expires_in": 30}


@router.get("/sounds/{sound_id}/download")
async def download_sound(
    sound_id: int,
    x_subscriber: str | None = Header(default=None, alias="X-Subscriber"),
):
    if (x_subscriber or "").lower() != "true":
        raise HTTPException(status_code=403, detail="Subscriber access required")
    sound = await load_sound(sound_id)
    url = await get_storage().signed_url(sound["file_key"], 300)
    return {"url": url, "expires_in": 300}


@router.get("/audio/{key:path}")
async def serve_audio(key: str, expires: int, signature: str):
    if expires < int(time.time()) or not hmac.compare_digest(
        sign_local_url(key, expires), signature
    ):
        raise HTTPException(status_code=403, detail="Invalid or expired signed URL")
    base = Path(get_settings().local_storage_path).resolve()
    path = (base / key).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise HTTPException(status_code=404, detail="Audio not found")
    media_type = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
    }.get(path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=media_type)
