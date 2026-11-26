from fastapi import APIRouter
from ..db import get_connection

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    async with get_connection() as conn:
        await conn.execute("SELECT 1")
    return {"status": "ok", "database": "connected"}
