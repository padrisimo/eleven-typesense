from fastapi import APIRouter

router = APIRouter(tags=["sounds"])


@router.get("/sounds/{sound_id}")
async def get_sound(sound_id: int):
    return {"id": sound_id, "title": "placeholder"}


@router.get("/sounds/{sound_id}/preview")
async def preview_sound(sound_id: int):
    return {"url": f"/audio/{sound_id}/preview"}


@router.get("/sounds/{sound_id}/download")
async def download_sound(sound_id: int):
    return {"url": f"/audio/{sound_id}/download"}
