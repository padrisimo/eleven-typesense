from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    prompt: str
    duration_seconds: int | None = None


class GenerateResponse(BaseModel):
    sound_id: int
    idempotent: bool


@router.post("/generate")
async def generate_sound(request: GenerateRequest):
    return GenerateResponse(sound_id=0, idempotent=False)
