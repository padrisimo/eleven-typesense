# Performance and design notes

Environment for local numbers: Colima (4 vCPU / 8 GiB), PostgreSQL 16.16, Typesense 30.2, 200,000 reproducible sounds (`random.seed(42)`), 10 categories, 2,976 rows with `bpm`. Timings are medians of repeated runs on this machine, not production benchmarks.

## Executed GCP trial deployment (single run, 2026-11-26)

Environment: `e2-standard-2` (2 vCPU / 8 GiB), 50 GB `pd-balanced`, Debian 12, the same Compose stack behind Caddy at `https://<VM_IP>.sslip.io`, 200,000 seeded sounds, 10,000 of them in `sounds_v2` with embeddings, audio in GCS and `GENERATOR=mock`. These are single passes through the public HTTPS endpoint, not medians; the local table below remains the controlled comparison.

| Check | Result |
|---|---|
| `GET /health` and `GET /api/health` | `{"status":"ok","database":"connected"}`, real LE certificate via `sslip.io` |
| `GET /` | `<title>Soundseek</title>` served from `ui/dist` by Caddy |
| `GET /search?q=door` | `found=833`, `search_time_ms=7`, top `Rusty Door Closing` |
| `GET /search?q=heavy metallic door sound&mode=hybrid` | `found=586`, `search_time_ms=19`, top `Heavy Door Closing` |
| Two identical `POST /generate` calls | same `sound_id=200001`, second `idempotent: true`, both `indexed: true` |
| GCS V4 signed preview URL | **200**, `audio/mpeg`, 17,180 bytes, signed via IAM `signBlob` (no key on disk) |
| `GET /sounds/200001/download` without header | **403**; with `X-Subscriber: true` a 5-minute signed URL |
| Search for the generated prompt | `found=1`, top `heavy metallic door slam` |

The remote run confirms the parts that cannot be exercised locally: Caddy TLS with `sslip.io`, the built UI behind the same origin, GCS signed URLs with the attached service account, and `mode=hybrid` against the aliased `sounds_v2` collection.

## PostgreSQL indexes: before / after (`EXPLAIN ANALYZE`, 3 runs each)

| Query | Before | After | Plan change | Buffers |
|---|---:|---:|---|---:|
| Q1 category + `ORDER BY created_at DESC LIMIT 20` | 20.927 ms | **0.101 ms** (~207×) | Parallel Seq Scan + top-N heapsort → Index Scan on `(category, created_at DESC)` | 21,725 → 23 |
| Q2 `tags @> ARRAY[...]` | 7.940 ms | **0.368 ms** (~22×) | Parallel Seq Scan → Bitmap Heap Scan on GIN index | 2,909 → 30 |
| Q3 `title ILIKE '%rusty hatch%'` | 5.289 ms | **1.055 ms** (~5×) | Parallel Seq Scan → Bitmap Heap Scan on `pg_trgm` index | 306 → 70 |
| Q4 `GROUP BY category` count | 26.183 ms | **14.726 ms** (~1.8×) | Parallel Seq Scan + HashAggregate → Index Only Scan + GroupAggregate | 21,670 → 900 |
| Q5 common-term `ILIKE '%explosion%' LIMIT 20` | 0.217 ms | **1.843 ms** (regression) | Seq Scan → trigram bitmap + recheck | 26 → 64 |

The interesting result is Q5: an index chosen by the cost estimator is slower for a very common substring with an early `LIMIT`, because the sequential scan stops after a few pages. The regression is kept in the report rather than hidden. Index build took **1.46 s** for 7 indexes plus `pg_trgm`; the table has 200k rows.

Text search comparison: Postgres `ILIKE` is faster for a literal substring with `LIMIT 20` (0.217–1.843 ms), but gives no ranking, typo tolerance or facets. Typesense `q=explosion` took a median **15 ms** with `found=23,331` and four facets; `q=rusty hatch` took **6 ms** with `found=1,139` because tokens match across weighted fields (quoted phrase → 760 hits in 23 ms). Postgres remains the source of truth; Typesense remains the search API.

## Data flow and index synchronization

- Postgres owns metadata, jobs, quota and `indexed_at`; Typesense is derived and rebuildable from it with `scripts/reindex.py`.
- Generation commits to Postgres first, then upserts to Typesense. If the index is down, `indexed_at` stays NULL and `--only-unindexed` repairs it. This is a minimal outbox marker, not a durable queue — enough to find and fix gaps.
- Collections are versioned (`sounds_v1`, `sounds_v2`) behind the `sounds` alias. The API never hardcodes a collection name; `--only-alias` flips the alias in one atomic `upsert`, with the old collection still available for rollback. No restart, no downtime.
- Keyword measurements on 200k docs: `explosion` 40 ms / 23,331 found; `footsteps` + filters 51 ms / 1,870 found; nonsense query 0 ms / `suggest_generate=true`.
- `sounds_v2` auto-embeds `title + description` with Typesense's built-in `ts/all-MiniLM-L12-v2` (384 dims, cosine). Only 10k docs are embedded because CPU inference is slow; a production backfill would use workers/GPU.

## Generation: idempotency and cost control

- `POST /generate` holds a Postgres advisory lock on `sha256(prompt.strip())` for the whole synchronous flow; two identical concurrent requests produce one sound.
- An idempotent hit returns the existing sound without calling the provider and without consuming quota.
- `GENERATION_DAILY_LIMIT` (default 10) counts all `generation_jobs` attempts in the last 24 hours, including failures — failed calls can still spend credits.
- Failure halfway through is safe: audio upload or provider errors mark the job `failed`; a Typesense error leaves the sound in Postgres with `indexed_at=NULL` for later repair.
- Verified: two identical calls → same `sound_id`, second `idempotent: true`; with limit 1 a new prompt returns **429** while the old prompt still returns its cached sound.
- ElevenLabs uses the official `POST https://api.elevenlabs.io/v1/sound-generation` (`xi-api-key`, `text`, `duration_seconds` 0.5–30, `output_format`). On 401/402/403 with fallback enabled it uses the mock and stores `license='mock'` rather than claiming a commercial license for free-tier audio.

## Signed URLs and access control

- `GET /sounds/{id}` reads Postgres; `/preview` returns a 30-second URL; `/download` requires `X-Subscriber: true` and returns a 5-minute URL.
- Local backend: HMAC over `key:expires`, verified by `/audio/{key}`; path traversal is blocked with `Path.is_relative_to`. Verified **403** without header, **200 audio/mpeg** with it.
- GCS backend: V4 signed URLs through IAM `signBlob` with the attached service account — no private key on disk (Google's own docs discourage downloading one). Requires `roles/iam.serviceAccountTokenCreator` on the app service account.
- `X-Subscriber` is an explicit stub: real deployments validate a session/subscription token at the edge and in the API.

## Deployment shape and scaling path

- A single Debian VM with Compose matches the target stack: Caddy on `edge`, API + Postgres + Typesense on `backend`, named volumes for data, healthchecks and log rotation. Only Caddy publishes 80/443.
- Verified production stack: `https://localhost/health` → `{"status":"ok","database":"connected"}`, HTTP → **308** redirect, hybrid search through Caddy → `Creaking Door Closing` as top hit.
- As it grows: Cloud Run for stateless API replicas, Cloud SQL for Postgres (PITR, automated backups), a managed queue/worker for generation and reindexing, PgBouncer if connection counts become the bottleneck (not needed at 4 workers), and structured logging/metrics/tracing instead of `docker compose logs`.
- Embeddings and generation are the first things to move out of the request path: CPU inference and third-party latency do not belong in a synchronous web worker at scale.

## Current scope vs production

The current implementation deliberately keeps simple credentials, synchronous generation, HMAC/auth stubs, a mock generator, single-node Typesense, logical backups, a 10k embedding subset, no per-user rate limiting and no monitoring/alerting. Production would add real identity and subscription checks, secrets in Secret Manager, queues with retries and dead-letter handling, per-user quotas, a full embedding backfill, Postgres PITR, multi-node Typesense with snapshots, observability and cost alerts. The parts worth keeping are the interfaces (`Storage`, `SoundGenerator`), the versioned alias and the `indexed_at` gap detector — they are the seams where those production pieces plug in.

## Semantic vs keyword search (medians of 5 runs)

Query: `sound of a creaky hinge` against the 10k-doc `sounds_v2`.

| Mode | found | median | Top 3 titles |
|---|---:|---:|---|
| `keyword` | 2,456 | 7 ms | Tense Soundscape Space, Heavy Gate Knocking, Heavy Door Revolving |
| `hybrid` | 2,520 | 14 ms | **Creaking Door Closing, Creaking Entrance Locking, Walking Steps Creaking** |

Keyword search matches generic tokens ("sound", "hinge") and ranks generic ambience first; hybrid search puts actual creaking-door effects at the top at roughly 2× the latency. Filters and facets behave identically in both modes.
