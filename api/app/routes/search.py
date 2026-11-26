from fastapi import APIRouter

router = APIRouter(tags=["search"])


@router.get("/search")
async def search():
    return {"hits": [], "facet_counts": {}, "search_time_ms": 0, "suggest_generate": False}
