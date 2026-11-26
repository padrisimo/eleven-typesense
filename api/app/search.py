from typesense import Client

from .config import get_settings


SCHEMA_V1 = {
    "name": "sounds_v1",
    "fields": [
        {"name": "title", "type": "string"},
        {"name": "description", "type": "string"},
        {"name": "tags", "type": "string[]", "facet": True},
        {"name": "category", "type": "string", "facet": True},
        {"name": "format", "type": "string", "facet": True},
        {"name": "source", "type": "string", "facet": True},
        {"name": "duration_ms", "type": "int32"},
        {"name": "bpm", "type": "int32", "optional": True},
        {"name": "created_at", "type": "int64"},
    ],
    "default_sorting_field": "created_at",
}


def get_typesense_client() -> Client:
    settings = get_settings()
    return Client(
        {
            "api_key": settings.typesense_api_key,
            "nodes": [
                {
                    "host": settings.typesense_host,
                    "port": str(settings.typesense_port),
                    "protocol": settings.typesense_protocol,
                }
            ],
            "connection_timeout_seconds": 300,
        }
    )
