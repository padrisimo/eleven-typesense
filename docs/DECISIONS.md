# Decisions

## Pinned Docker image versions

- **Decision:** Pin `postgres:16.16-alpine3.24`, `typesense/typesense:30.2`, `python:3.12-slim-bookworm`, `caddy:2.9-alpine` and exact Python package versions in `api/pyproject.toml`.
- **Reason:** Reproducibility; the stack must not change unexpectedly because a mutable `latest` tag changed.
- **Alternative rejected:** `latest` tags and loose dependency ranges — a rebuild weeks later could run untested versions.
- **When I would change it:** When a security patch requires a bump, updating the pin deliberately in a commit.

## Typesense healthcheck via bash `/dev/tcp`

- **Decision:** Healthcheck sends an HTTP `GET /health` through bash's `/dev/tcp`, with `Connection: close` and a 2s timeout.
- **Reason:** The official `typesense/typesense:30.2` image is Ubuntu with only `ca-certificates`; it has no `curl` or `wget`. Bash provides a dependency-free TCP socket.
- **Alternative rejected:** Deriving a custom image with `curl` installed — extra build time and maintenance for a single healthcheck. `wget --spider` does not exist in the image either.
- **When I would change it:** If the upstream image starts shipping a HTTP client, switch to it for readability.

## API healthcheck uses `wget --method=GET`

- **Decision:** Container healthcheck calls `wget -q --method=GET -O- http://localhost:8000/health`.
- **Reason:** `wget --spider` sends `HEAD`, but FastAPI only maps `GET` on the route, returning 405 and marking the container unhealthy.
- **Alternative rejected:** `--spider` (405) and adding `HEAD` to the route just to satisfy the probe.
- **When I would change it:** If we add a Python-based probe, drop the `wget` system package from the image.

## `/health` checks Postgres

- **Decision:** `GET /health` runs `SELECT 1` and returns 503 if the pool cannot connect.
- **Reason:** A liveness-only endpoint would report OK while the API is useless, hiding a broken dependency.
- **Alternative rejected:** A separate `/ready` endpoint — overkill for a vertical slice.
- **When I would change it:** If we add more dependencies (queue, GCS), split liveness/readiness properly.

## `indexes.sql` mounted into initdb after benchmarking

- **Decision:** Initially only `schema.sql` was mounted; after recording the benchmark, `indexes.sql` was added back as `02-indexes.sql` so a clean clone gets the final schema.
- **Reason:** The benchmark needed a real "before" state without secondary indexes. Once `docs/EXPLAIN_REPORT.md` captured the numbers, clean clones should start with the tuned schema.
- **Alternative rejected:** Keeping indexes unmounted forever and requiring a manual step after every clone — easy to forget and breaks the definition of done.
- **When I would change it:** If we benchmark again, temporarily drop indexes in a scratch database rather than changing the default compose mounts.

## Partial indexes with `WHERE is_active`

- **Decision:** All secondary indexes on `sounds` are partial on `is_active`.
- **Reason:** The search API only returns active sounds, so inactive rows would only add index size and maintenance cost.
- **Alternative rejected:** Full indexes including inactive rows — larger and slower to update for no query benefit here.
- **When I would change it:** If an admin endpoint needs to query inactive sounds regularly, add a separate index or drop the predicate.

## Keep `pg_trgm` despite a common-term regression

- **Decision:** Keep the GIN trigram index on `title` even though `ILIKE '%explosion%' LIMIT 20` got slower (0.217 → 1.843 ms).
- **Reason:** Selective patterns benefit (`%rusty hatch%`: 5.289 → 1.055 ms); the regression is limited to very common substrings where a seq scan can stop after a few pages.
- **Alternative rejected:** Dropping the index based on that single common-term case — it would remove the win for realistic selective searches.
- **When I would change it:** If production telemetry shows most text queries are common short terms, tune the index (or add a full-text index) based on measured latency.

## Benchmark with 3 runs and buffer counts

- **Decision:** Report medians of 3 `EXPLAIN (ANALYZE, BUFFERS)` runs plus shared-buffer page counts instead of a single execution time.
- **Reason:** `shared_buffers=128MB` cannot hold the 200k-row table (~21k pages); single runs varied up to 4× depending on cache state, while buffer counts were stable.
- **Alternative rejected:** A single warm run — too noisy to support a before/after claim.
- **When I would change it:** On dedicated hardware with the dataset fully cached, fewer runs may be enough; still keep buffer counts.

## Synchronous generation with an advisory lock

- **Decision:** `POST /generate` holds a Postgres session advisory lock keyed by the prompt hash for the whole synchronous flow.
- **Reason:** Two concurrent identical requests must produce a single sound; the lock is simple and Postgres-native.
- **Alternative rejected:** A race-prone check-then-insert without a lock, or a queue/worker (out of scope for the slice).
- **When I would change it:** In production, enqueue a job with a lease/idempotency key and never hold a DB connection during an ElevenLabs call.

## Rolling 24-hour generation limit counts attempts

- **Decision:** `GENERATION_DAILY_LIMIT` counts all `generation_jobs` rows created in the last 24 hours, including failed ones; idempotent hits bypass the limit.
- **Reason:** Failed calls can still consume provider credits, and retries must not be an unlimited loophole.
- **Alternative rejected:** Calendar-day counting (resets at midnight) or counting only successful generations.
- **When I would change it:** With real accounts, key the limit by user/API key and use a quota table.

## Typesense failure leaves `indexed_at` NULL

- **Decision:** The sound and job are committed to Postgres before the Typesense upsert; on index failure `indexed_at` stays NULL and `scripts/reindex.py --only-unindexed` repairs it.
- **Reason:** A search-index outage must not lose generated audio or metadata; `indexed_at` acts as a minimal outbox.
- **Alternative rejected:** One distributed transaction across Postgres and Typesense (not possible) or rolling back the sound.
- **When I would change it:** With a queue, publish an indexing event and add retries plus monitoring.

## Local signed URLs are an HMAC stub; GCS uses V4 signBlob

- **Decision:** The local backend returns `/audio/...?expires=&signature=` URLs verified by the API; the GCS backend V4-signs URLs through IAM `signBlob` when using an attached service account.
- **Reason:** The demo needs expiring URLs without GCP; on a VM there is no private key on disk, and Google's documentation recommends IAM `signBlob` over downloading a service-account key.
- **Alternative rejected:** Public bucket objects (no access control) or a downloaded service-account key (security risk).
- **When I would change it:** If running outside GCP, mount a JSON key or use a secret manager; replace the `X-Subscriber` stub with real subscription tokens.

## `X-Subscriber` is an auth stub

- **Decision:** `/sounds/{id}/download` requires `X-Subscriber: true`; preview is public.
- **Reason:** Demonstrates the access-control boundary without building authentication in a vertical slice.
- **Alternative rejected:** No check (hides the requirement) or full OAuth/JWT (out of scope).
- **When I would change it:** Validate a real session/subscription token at the edge and in the API before production.

## ElevenLabs fallback on 401/402/403 with honest licensing

- **Decision:** `GENERATOR=elevenlabs` calls the official `POST https://api.elevenlabs.io/v1/sound-generation` (`xi-api-key`, `text`, optional `duration_seconds` in 0.5–30 s, `output_format` query param) and falls back to the mock only on 401/402/403 when enabled; the stored license reflects the audio actually used.
- **Reason:** Free plans often lack sound-effects access; a narrow fallback keeps the demo runnable without hiding outages or mislabelling free-plan audio.
- **Alternative rejected:** Falling back on every error (masks provider incidents) or storing a commercial license for free-plan audio.
- **When I would change it:** Once the endpoint and commercial license are enabled, remove the fallback and store the real license.

## Reproducible seed with `COPY` and varied `created_at`

- **Decision:** `db/seed.py` uses `random.seed(42)`, `psycopg`'s `copy.write_row()` and spreads `created_at` over 730 days from 2023-01-01.
- **Reason:** 200k individual `INSERT`s would be too slow; a fixed timestamp would make the category/date benchmark meaningless.
- **Alternative rejected:** Generating a CSV on the host and `\copy` — an extra intermediate file and a second toolchain (host Python) to maintain.
- **When I would change it:** If the dataset grows past a few million rows, generate partitioned files and parallel `COPY` workers.

## Versioned collection + alias, batch import with `upsert`

- **Decision:** Index into `sounds_v1` and query the alias `sounds`; `scripts/reindex.py` imports in 500-document JSONL batches with `action=upsert` and marks `indexed_at` in Postgres.
- **Reason:** Aliases allow atomic collection switches with no client change; `upsert` makes re-running the reindex idempotent; batches keep memory bounded.
- **Alternative rejected:** Indexing straight into a fixed `sounds` collection one document at a time — no alias swap, and 200k HTTP calls would be far slower.
- **When I would change it:** If the corpus grows past ~10M documents, shard into multiple collections and use multi-search.

## `created_at` indexed as Unix `int64`

- **Decision:** Store `created_at` as `int64` (Unix seconds) in Typesense, with `default_sorting_field` set to it.
- **Reason:** Typesense 30.2 has no native `datetime` field type; an integer epoch sorts chronologically and works in range filters.
- **Alternative rejected:** Indexing the ISO-8601 string — lexical sorting works for UTC but range filters become brittle.
- **When I would change it:** If Typesense adds a datetime type, switch and reindex.

## `query_by` weights `title:3, tags:2, description:1`

- **Decision:** Rank title matches highest, then tags, then description; sort by `_text_match:desc,created_at:desc`.
- **Reason:** Sound-effect searches are mostly by short name/tag; description is verbose and noisy. Tie-breaking by recency gives stable results.
- **Alternative rejected:** Equal weights — generic words in descriptions dominate top hits.
- **When I would change it:** After collecting real user clicks, tune weights or add curated rules.

## Versioned collection with auto-embeddings and atomic alias switch

- **Decision:** `sounds_v2` adds an auto-embedding `float[]` field built from `title + description` with the built-in `ts/all-MiniLM-L12-v2` model (384 dims, cosine distance). Hybrid queries put `embedding` into `query_by` with weights `1,3,2,1` and `vector_query=embedding:([], k:100)`; the API always queries the `sounds` alias, switched with a single `aliases.upsert`.
- **Reason:** A new schema can be built and validated offline, then published atomically without downtime or code changes. Official Typesense 30.2 docs use `embed.model_config.model_name` and `query_by: "embedding,<keyword fields>"` for hybrid search.
- **Alternative rejected:** An in-place schema change (no rollback path) or an API-side model call (extra dependency and latency). The earlier draft used `float32[]` and a bare `model_name`; the pinned docs require `float[]` and `model_config`.
- **When I would change it:** With a GPU worker or a hosted embedding API, index all documents instead of the CPU-limited 10k subset and switch models via a new collection version.

## Limited 10k embedding subset for the demo

- **Decision:** Only the first 10,000 active sounds are embedded into `sounds_v2`; Postgres still holds 200,000+, and generated sounds are upserted into the active collection individually.
- **Reason:** CPU inference is slow; the vertical slice needs a measurable semantic-vs-keyword comparison, not a full production backfill.
- **Alternative rejected:** Embedding all 200k on CPU (too slow for the time budget) or leaving v1 active (no semantic search).
- **When I would change it:** In production, backfill all documents with a batch/GPU worker and monitor index coverage; keep the same alias-swap mechanism.

## Caddy as the only published port in production

- **Decision:** `docker-compose.prod.yml` adds Caddy 2.9 on the `edge` network publishing 80/443 (and 443/udp), while Postgres, Typesense and the API expose no host ports; the dev override still binds them to `127.0.0.1`.
- **Reason:** One TLS terminator with automatic HTTPS, a smaller attack surface, and the same Compose file works locally and on the VM.
- **Alternative rejected:** Terminating TLS in FastAPI (extra complexity, harder certificate renewal) or publishing the API directly (no single place for access control).
- **When I would change it:** Behind a managed load balancer or Cloud Run, where HTTPS is provided by the platform.

## Deployment delivered as a runbook, not executed

- **Decision:** `docs/DEPLOY.md` contains the gcloud commands for a VM, bucket, least-privilege service account, firewall and a final teardown; no gcloud command was run and no paid resource was created.
- **Reason:** The user controls cloud spend and account permissions; the runbook documents the decisions and a reproducible path.
- **Alternative rejected:** Creating resources during development (cost and cleanup risk) or omitting the runbook (no deployment story).
- **When I would change it:** On explicit confirmation, execute the runbook with real credentials and record the resulting instance/bucket names.

## Optional React UI with Ant Design behind a Vite proxy

- **Decision:** `ui/` is a React 19 + Vite 8 + TypeScript 5.9 client using Ant Design 6.7.2, with exact pinned versions and a GitHub link in the top-right corner. Vite proxies `/api` to the local API and strips the prefix; the UI does not call `http://localhost:8000` directly.
- **Reason:** Ant Design gives a polished search/filter/modal UI without custom component work, and the proxy avoids adding CORS middleware to a small API only for development.
- **Alternative rejected:** Plain CSS components (more code for the same result), server-rendered templates (poorer interaction), or direct cross-origin calls (would require new API middleware).
- **When I would change it:** If the UI ships to production, add a Caddy `handle /api/*` rewrite or serve the built assets behind the same origin; for a larger app, consider route/code splitting to reduce the current 825 kB bundle.

## Minimal unit tests, smoke test kept as the e2e suite

- **Decision:** `api/tests/test_unit.py` covers only pure functions with no database or network; `scripts/smoke.sh` remains the end-to-end check against the running stack.
- **Reason:** The risky behaviour is idempotency, URL signing and the generation flow already verified by smoke. Mocking psycopg and Typesense would duplicate implementation details rather than catch real regressions.
- **Alternative rejected:** A broad pytest suite with fake connections and fake search clients (high maintenance, low signal for a vertical slice) or duplicating `smoke.sh` in pytest (no extra coverage).
- **When I would change it:** When generation or search logic grows branches worth isolating, or when CI needs a typed e2e runner; then add integration tests with a disposable database and Typesense instance.

## Free-tier deployment path and `sslip.io` hostname

- **Decision:** `docs/DEPLOY.md` now offers a free-tier demo: e2-micro in `us-central1`, 30 GB standard disk, 10k seeded sounds, one gunicorn worker, local audio, no embeddings and `DOMAIN=<VM_IP>.sslip.io`. The full-size paid path remains documented.
- **Reason:** GCP's Free Program covers one e2-micro in three US regions, 30 GB-months of standard disk and 1 GB egress; the full 200k/4-worker setup would not fit 1 GB RAM. `sslip.io` gives a real DNS name for Caddy's Let's Encrypt HTTP-01 challenge without buying a domain.
- **Alternative rejected:** Cloud Run alone (no free Postgres/Typesense), GitHub Pages as an API proxy (static hosting only, no backend or proxy), or a bare public IP (Let's Encrypt does not issue certificates for plain IPs).
- **When I would change it:** When traffic or dataset size outgrows e2-micro, or when a real domain is available; then switch to the standard path and a branded hostname.

## Serve the built UI from Caddy in production

- **Decision:** The production Caddyfile serves `ui/dist` at `/`, proxies `/api/*` to FastAPI with the prefix stripped, and keeps `/health` proxied for compatibility. `docker-compose.prod.yml` mounts the built bundle read-only at `/srv`.
- **Reason:** Same-origin UI and API avoid CORS and let one TLS endpoint serve the whole app. The UI bundle is built before `up` because the VM does not need Node installed.
- **Alternative rejected:** Hosting the UI on GitHub Pages (would require CORS and a separate public API URL) or adding a second web server.
- **When I would change it:** If the frontend is deployed independently to a CDN, keep only the `/api/*` proxy and add explicit CORS/origin checks.

## Trial deployment: bounded ambitious plan in a dedicated project

- **Decision:** Use the €300 trial credit to run `<PROJECT_ID>` with an e2-standard-2 VM, 200k sounds, GCS audio and 10k embeddings, a 50 EUR budget alert and teardown before 2026-02-25. The free-tier path stays the documented default.
- **Reason:** The credit covers roughly 50 EUR/month for three months, and the remote run validates GCS `signBlob`, Caddy TLS via `sslip.io`, alias switching and hybrid search — none of which can be exercised locally. The vertical slice stays the goal, so the scope is time-bounded rather than permanent.
- **Alternative rejected:** Leaving the larger VM always on until the credit expires (surprise bill afterwards), reusing `My First Project` (immutable long ID and messy teardown), making the repo public only to unblock the VM clone (the source was copied via tarball instead; the user later made it public anyway), Cloud Run/GKE (outside the target stack).
- **When I would change it:** If the demo must stay public after February, get explicit approval for a paid budget and a real domain; if traffic or data grows, follow the Cloud SQL/queue path in `docs/ARCHITECTURE.md`.

## Keep Typesense for search; ElevenLabs stays generation-only

- **Decision:** Do not integrate ElevenLabs as a sound-search source. Search remains Typesense hybrid (`query_by=embedding,title,tags,description`) with its bundled model; ElevenLabs is only an optional `SoundGenerator` implementation.
- **Reason:** The official OpenAPI spec has no sound-effect search endpoint — only `POST /v1/sound-generation`; `/v1/assets` covers the caller's own workspace files. The curated effects library is browsable on the website but has no public API, and the free plan is non-commercial. Typesense already provides semantic search with no external calls or cost.
- **Alternative rejected:** Scraping the ElevenLabs web library (unofficial, brittle, licensing risk), adding Freesound (external service outside the target stack and needs an API key), or paying for credits to generate audio when the request was for search.
- **When I would change it:** If ElevenLabs publishes an officially supported SFX search/library API with clear commercial licensing, or a real external catalog becomes a core requirement; then add it as another source behind the existing search/storage seams.

## ElevenLabs generation stays off for now

- **Decision:** Keep `GENERATOR=mock` in the deployed stack. `ElevenLabsGenerator` is implemented and documented, but the user is still weighing whether to enable it; no API key was configured and no ElevenLabs call was made.
- **Reason:** The request was about sound search, and ElevenLabs has no SFX search API. Generation is a separate feature that changes licensing, cost control and latency, so it deserves an explicit choice rather than a silent switch.
- **Pros of enabling:** Real, varied audio instead of the tiny `sample.mp3` bundled with the mock; the Free plan gives 10,000 credits/month and officially includes Sound Effects via `POST /v1/sound-generation`; the code is already behind `GENERATOR`/`ELEVENLABS_API_KEY` with a mock fallback on 401/402/403; idempotency by prompt hash and the daily limit prevent accidental spend.
- **Cons of enabling:** Free-plan output is non-commercial only (`license='elevenlabs-free-noncommercial'`); an API key must live in the VM `.env` and could be abused if leaked; generation is synchronous and adds third-party latency and failure modes; generated audio only appears after a user asks for it, so it does not make the regular search results sound any richer.
- **Alternative rejected (for now):** Scraping ElevenLabs' web library to seed real sounds (no public API, brittle, licensing risk), and buying a paid plan just for nicer demo audio (out of scope for the free trial). Instead, `api/assets/sample.mp3` was replaced with a locally synthesized 1.2 s percussive thud (`random.seed(42)`, mono 44.1 kHz, 128 kbps, mean -18.7 dB / peak -2.7 dB): no external licence or API key, and the mock preview is audible. Verified through the signed URL after generating sound 200020.
- **When I would change it:** As soon as the user decides; then set `GENERATOR=elevenlabs` and `ELEVENLABS_API_KEY` in the VM `.env`, restart the API and verify one generation. Revisit licensing if the demo becomes commercial.
