#!/usr/bin/env python3
"""Index all active sounds from Postgres into a versioned Typesense collection."""

import argparse
import os
import sys

import psycopg
from typesense.exceptions import ObjectAlreadyExists

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from app.search import SCHEMA_V1, get_typesense_client  # noqa: E402

BATCH_SIZE = 500
ALIAS = "sounds"


def create_collection(client, name: str, with_embeddings: bool):
    schema = dict(SCHEMA_V1)
    schema["name"] = name
    if with_embeddings:
        schema["fields"] = list(schema["fields"]) + [
            {
                "name": "embedding",
                "type": "float[]",
                "embed": {
                    "from": ["title", "description"],
                    "model_config": {"model_name": "ts/all-MiniLM-L12-v2"},
                },
            }
        ]
    try:
        client.collections.create(schema)
        print(f"Created collection {name}")
    except ObjectAlreadyExists:
        print(f"Collection {name} already exists")


def set_alias(client, name: str):
    client.aliases.upsert(ALIAS, {"collection_name": name})
    print(f"Alias {ALIAS} -> {name}")


def index_sounds(dsn: str, client, name: str, limit: int | None, only_unindexed: bool):
    condition = "AND indexed_at IS NULL" if only_unindexed else ""
    query = f"""
        SELECT id, title, description, tags, category, duration_ms, bpm,
               format, source, created_at
        FROM sounds
        WHERE is_active {condition}
        ORDER BY id
    """
    if limit:
        query += f" LIMIT {limit}"

    collection = client.collections[name]
    total = 0
    all_ids: list[int] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DECLARE sounds_cursor CURSOR FOR " + query)
            while True:
                cur.execute("FETCH FORWARD %d FROM sounds_cursor" % BATCH_SIZE)
                rows = cur.fetchall()
                if not rows:
                    break
                documents = []
                ids = []
                for row in rows:
                    (
                        sid, title, description, tags, category, duration_ms, bpm,
                        fmt, source, created_at,
                    ) = row
                    ids.append(sid)
                    documents.append(
                        {
                            "id": str(sid),
                            "title": title,
                            "description": description,
                            "tags": tags,
                            "category": category,
                            "duration_ms": duration_ms,
                            "bpm": bpm,
                            "format": fmt,
                            "source": source,
                            "created_at": int(created_at.timestamp()),
                        }
                    )
                result = collection.documents.import_(documents, {"action": "upsert"})
                failures = [r for r in result if not r.get("success")]
                if failures:
                    raise RuntimeError(f"Import failures: {failures[:3]}")
                total += len(documents)
                all_ids.extend(ids)
                print(f"Indexed {total} documents", end="\r", flush=True)
    print(f"\nIndexed {total} documents into {name}")
    return all_ids


def mark_indexed(dsn: str, ids: list[int]):
    if not ids:
        return
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sounds SET indexed_at = NOW() WHERE id = ANY(%s)",
                (ids,),
            )
    print(f"Marked {len(ids)} rows as indexed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default="sounds_v1")
    parser.add_argument("--with-embeddings", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--only-unindexed", action="store_true")
    parser.add_argument("--set-alias", action="store_true")
    parser.add_argument("--only-alias", action="store_true")
    parser.add_argument(
        "--dsn",
        default=os.getenv(
            "DATABASE_URL",
            "postgresql://soundsnap:soundsnap@localhost:5432/soundsnap",
        ),
    )
    args = parser.parse_args()

    client = get_typesense_client()
    if args.only_alias:
        set_alias(client, args.collection)
        return
    create_collection(client, args.collection, args.with_embeddings)
    ids = index_sounds(args.dsn, client, args.collection, args.limit, args.only_unindexed)
    mark_indexed(args.dsn, ids)
    if args.set_alias:
        set_alias(client, args.collection)


if __name__ == "__main__":
    main()
