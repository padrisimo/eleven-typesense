# Decisions

## Pinned Docker image versions (Phase 0)

- **Decision:** Pin `postgres:16.16-alpine3.24`, `typesense/typesense:30.2`, `python:3.12-slim-bookworm`, `caddy:2.9-alpine` and exact Python package versions in `api/pyproject.toml`.
- **Reason:** Reproducibility; the interview demo must not break because a mutable `latest` tag changed.
- **Alternative rejected:** `latest` tags and loose dependency ranges — a rebuild weeks later could run untested versions.
- **When I would change it:** When a security patch requires a bump, updating the pin deliberately in a commit.

## Typesense healthcheck via bash `/dev/tcp` (Phase 0)

- **Decision:** Healthcheck sends an HTTP `GET /health` through bash's `/dev/tcp`, with `Connection: close` and a 2s timeout.
- **Reason:** The official `typesense/typesense:30.2` image is Ubuntu with only `ca-certificates`; it has no `curl` or `wget`. Bash provides a dependency-free TCP socket.
- **Alternative rejected:** Deriving a custom image with `curl` installed — extra build time and maintenance for a single healthcheck. `wget --spider` does not exist in the image either.
- **When I would change it:** If the upstream image starts shipping a HTTP client, switch to it for readability.

## API healthcheck uses `wget --method=GET` (Phase 0)

- **Decision:** Container healthcheck calls `wget -q --method=GET -O- http://localhost:8000/health`.
- **Reason:** `wget --spider` sends `HEAD`, but FastAPI only maps `GET` on the route, returning 405 and marking the container unhealthy.
- **Alternative rejected:** `--spider` (405) and adding `HEAD` to the route just to satisfy the probe.
- **When I would change it:** If we add a Python-based probe, drop the `wget` system package from the image.

## `/health` checks Postgres (Phase 0)

- **Decision:** `GET /health` runs `SELECT 1` and returns 503 if the pool cannot connect.
- **Reason:** A liveness-only endpoint would report OK while the API is useless, hiding a broken dependency.
- **Alternative rejected:** A separate `/ready` endpoint — overkill for a vertical slice.
- **When I would change it:** If we add more dependencies (queue, GCS), split liveness/readiness properly.

## `indexes.sql` mounted into initdb only after Phase 3

- **Decision:** During Phases 1–2 only `schema.sql` was mounted; after recording the benchmark, `indexes.sql` was added back as `02-indexes.sql` so a clean clone gets the final schema.
- **Reason:** Phase 3 needed a real "before" state without secondary indexes. Once `docs/EXPLAIN_REPORT.md` captured the numbers, clean clones should start with the tuned schema.
- **Alternative rejected:** Keeping indexes unmounted forever and requiring a manual step after every clone — easy to forget and breaks the definition of done.
- **When I would change it:** If we benchmark again, temporarily drop indexes in a scratch database rather than changing the default compose mounts.

## Partial indexes with `WHERE is_active` (Phase 3)

- **Decision:** All secondary indexes on `sounds` are partial on `is_active`.
- **Reason:** The search API only returns active sounds, so inactive rows would only add index size and maintenance cost.
- **Alternative rejected:** Full indexes including inactive rows — larger and slower to update for no query benefit here.
- **When I would change it:** If an admin endpoint needs to query inactive sounds regularly, add a separate index or drop the predicate.

## Keep `pg_trgm` despite a common-term regression (Phase 3)

- **Decision:** Keep the GIN trigram index on `title` even though `ILIKE '%explosion%' LIMIT 20` got slower (0.217 → 1.843 ms).
- **Reason:** Selective patterns benefit (`%rusty hatch%`: 5.289 → 1.055 ms); the regression is limited to very common substrings where a seq scan can stop after a few pages.
- **Alternative rejected:** Dropping the index based on that single common-term case — it would remove the win for realistic selective searches.
- **When I would change it:** If production telemetry shows most text queries are common short terms, tune the index (or add a full-text index) based on measured latency.

## Benchmark with 3 runs and buffer counts (Phase 3)

- **Decision:** Report medians of 3 `EXPLAIN (ANALYZE, BUFFERS)` runs plus shared-buffer page counts instead of a single execution time.
- **Reason:** `shared_buffers=128MB` cannot hold the 200k-row table (~21k pages); single runs varied up to 4× depending on cache state, while buffer counts were stable.
- **Alternative rejected:** A single warm run — too noisy to support a before/after claim.
- **When I would change it:** On dedicated hardware with the dataset fully cached, fewer runs may be enough; still keep buffer counts.

## Reproducible seed with `COPY` and varied `created_at` (Phase 1)

- **Decision:** `db/seed.py` uses `random.seed(42)`, `psycopg`'s `copy.write_row()` and spreads `created_at` over 730 days from 2023-01-01.
- **Reason:** 200k individual `INSERT`s would be too slow; a fixed timestamp would make the Phase 3 "filter by category + order by date" benchmark meaningless.
- **Alternative rejected:** Generating a CSV on the host and `\copy` — an extra intermediate file and a second toolchain (host Python) to maintain.
- **When I would change it:** If the dataset grows past a few million rows, generate partitioned files and parallel `COPY` workers.

## Versioned collection + alias, batch import with `upsert` (Phase 2)

- **Decision:** Index into `sounds_v1` and query the alias `sounds`; `scripts/reindex.py` imports in 500-document JSONL batches with `action=upsert` and marks `indexed_at` in Postgres.
- **Reason:** Aliases let Phase 5 switch collections atomically with no client change; `upsert` makes re-running the reindex idempotent; batches keep memory bounded.
- **Alternative rejected:** Indexing straight into a fixed `sounds` collection one document at a time — no alias swap, and 200k HTTP calls would be far slower.
- **When I would change it:** If the corpus grows past ~10M documents, shard into multiple collections and use multi-search.

## `created_at` indexed as Unix `int64` (Phase 2)

- **Decision:** Store `created_at` as `int64` (Unix seconds) in Typesense, with `default_sorting_field` set to it.
- **Reason:** Typesense 30.2 has no native `datetime` field type; an integer epoch sorts chronologically and works in range filters.
- **Alternative rejected:** Indexing the ISO-8601 string — lexical sorting works for UTC but range filters become brittle.
- **When I would change it:** If Typesense adds a datetime type, switch and reindex.

## `query_by` weights `title:3, tags:2, description:1` (Phase 2)

- **Decision:** Rank title matches highest, then tags, then description; sort by `_text_match:desc,created_at:desc`.
- **Reason:** Sound-effect searches are mostly by short name/tag; description is verbose and noisy. Tie-breaking by recency gives stable results.
- **Alternative rejected:** Equal weights — generic words in descriptions dominate top hits.
- **When I would change it:** After collecting real user clicks, tune weights or add curated rules.
