import asyncio
import os
from pathlib import Path

import psycopg

from app.storage.gcs import GCSStorage

SAMPLE = Path("/app/assets/sample.mp3")
KEY = "library/demo-sample.mp3"


async def main() -> None:
    storage = GCSStorage()
    with SAMPLE.open("rb") as audio:
        await storage.upload(KEY, audio, "audio/mpeg")

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sounds SET file_key = %s WHERE source = 'library'", (KEY,)
            )
            print(f"library sounds pointing to {KEY}: {cur.rowcount}")


if __name__ == "__main__":
    asyncio.run(main())
