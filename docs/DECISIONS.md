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

## `indexes.sql` is not mounted into initdb (Phase 1)

- **Decision:** Only `schema.sql` is mounted in `docker-entrypoint-initdb.d`; `indexes.sql` is applied manually in Phase 3.
- **Reason:** Phase 3 measures `EXPLAIN (ANALYZE, BUFFERS)` before and after creating indexes. Mounting both would remove the "before" state and invalidate the report.
- **Alternative rejected:** Applying indexes at startup and measuring with a temporary index drop — riskier and less reproducible.
- **When I would change it:** After Phase 3, once the report is recorded, mount both files so a clean clone has the final schema.

## Reproducible seed with `COPY` and varied `created_at` (Phase 1)

- **Decision:** `db/seed.py` uses `random.seed(42)`, `psycopg`'s `copy.write_row()` and spreads `created_at` over 730 days from 2023-01-01.
- **Reason:** 200k individual `INSERT`s would be too slow; a fixed timestamp would make the Phase 3 "filter by category + order by date" benchmark meaningless.
- **Alternative rejected:** Generating a CSV on the host and `\copy` — an extra intermediate file and a second toolchain (host Python) to maintain.
- **When I would change it:** If the dataset grows past a few million rows, generate partitioned files and parallel `COPY` workers.
