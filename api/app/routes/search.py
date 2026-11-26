from fastapi import APIRouter, Query

from ..search import get_typesense_client

router = APIRouter(tags=["search"])

COLLECTION = "sounds"


@router.get("/search")
async def search(
    q: str = Query(default="", description="Search query"),
    category: str | None = None,
    format: str | None = None,
    tags: list[str] = Query(default=[]),
    min_duration: int | None = None,
    max_duration: int | None = None,
    page: int = Query(default=1, ge=1),
    mode: str = Query(default="keyword", pattern="^(keyword|hybrid)$"),
):
    filters = []
    if category:
        filters.append(f"category:={category}")
    if format:
        filters.append(f"format:={format}")
    for tag in tags:
        filters.append(f"tags:={tag}")
    if min_duration is not None:
        filters.append(f"duration_ms:>={min_duration}")
    if max_duration is not None:
        filters.append(f"duration_ms:<={max_duration}")

    params = {
        "collection": COLLECTION,
        "q": q or "*",
        "query_by": "title,tags,description",
        "query_by_weights": "3,2,1",
        "facet_by": "category,format,tags,source",
        "filter_by": " && ".join(filters),
        "sort_by": "_text_match:desc,created_at:desc",
        "page": page,
        "per_page": 20,
        "highlight_fields": "title,description",
    }
    if mode == "hybrid":
        params["vector_query"] = "embedding:([], k:100)"

    client = get_typesense_client()
    result = client.collections[COLLECTION].documents.search(params)

    hits = [
        {
            "id": hit["document"]["id"],
            "title": hit["document"]["title"],
            "description": hit["document"]["description"],
            "category": hit["document"]["category"],
            "tags": hit["document"]["tags"],
            "format": hit["document"]["format"],
            "duration_ms": hit["document"]["duration_ms"],
            "score": hit.get("text_match"),
        }
        for hit in result["hits"]
    ]
    return {
        "hits": hits,
        "found": result["found"],
        "facet_counts": result.get("facet_counts", []),
        "search_time_ms": result["search_time_ms"],
        "page": page,
        "suggest_generate": result["found"] < 3,
        "mode": mode,
    }
