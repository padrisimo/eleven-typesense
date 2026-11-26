from typing import Any
from typesense.client import Client
from .config import get_settings


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
            "connection_timeout_seconds": 2,
        }
    )
