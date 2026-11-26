# Soundseek

Sound effects search engine. PostgreSQL is the source of truth; Typesense is a derived search index. When search returns nothing good, the API can generate a new sound (mock by default, ElevenLabs behind a flag), store it and make it searchable.

## Quickstart

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python /db/seed.py --dsn postgresql://soundsnap:soundsnap@db:5432/soundsnap
docker compose exec api python /scripts/reindex.py --dsn postgresql://soundsnap:soundsnap@db:5432/soundsnap --set-alias
curl http://localhost:8000/health
```

The seed loads 200,000 reproducible rows (`random.seed(42)`). The reindex bulk-imports them into `sounds_v1` and points the alias `sounds` at it.

## Endpoints

- `GET /health` — liveness + Postgres connectivity.
- `GET /search?q=&category=&format=&tags=&min_duration=&max_duration=&page=&mode=keyword|hybrid`
- `GET /sounds/{id}`, `/sounds/{id}/preview`, `/sounds/{id}/download`
- `POST /generate {prompt, duration_seconds?}`

## Example searches (measured)

All queries ran against 200,000 indexed documents on Typesense 30.2 (Colima, 4 vCPU/8 GiB), with weights `title:3, tags:2, description:1`.

### 1. Keyword + facet

```bash
curl 'http://localhost:8000/search?q=explosion&category=Explosions'
```

```json
{
  "found": 23331,
  "search_time_ms": 40,
  "facet_fields": ["category", "format", "tags", "source"],
  "first_hit": {"id": "41857", "title": "Small Explosion In Tunnel", "format": "flac", "duration_ms": 3275},
  "suggest_generate": false
}
```

### 2. Keyword + multiple filters

```bash
curl 'http://localhost:8000/search?q=footsteps&format=wav&min_duration=500&max_duration=3000'
```

```json
{
  "found": 1870,
  "search_time_ms": 51,
  "hits_returned": 20,
  "suggest_generate": false
}
```

### 3. No results triggers generation suggestion

```bash
curl 'http://localhost:8000/search?q=xyzzynonexistent'
```

```json
{
  "found": 0,
  "search_time_ms": 0,
  "suggest_generate": true
}
```

## Generation and signed URLs (verified)

```bash
curl -s -X POST http://localhost:8000/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"heavy metallic door slam","duration_seconds":2}'
```

```json
{"sound_id": 200005, "idempotent": false, "indexed": true, "license": "mock"}
```

The same prompt again returns the same `sound_id` with `idempotent: true` and creates no second sound. The new record is immediately searchable through the `sounds` alias. `GENERATOR=elevenlabs` uses the official `POST /v1/sound-generation` endpoint; on 401/402/403 it falls back to the mock when `GENERATOR_FALLBACK_TO_MOCK=true`.

`GET /sounds/{id}/preview` returns a 30-second signed URL; `GET /sounds/{id}/download` requires `X-Subscriber: true` and returns a 5-minute URL. With `STORAGE_BACKEND=local` these URLs are HMAC-signed and served by `/audio/{key}`.

Run the end-to-end smoke test with `./scripts/smoke.sh`.

## Hybrid search and alias swap (verified)

```bash
docker compose exec api python /scripts/reindex.py --collection sounds_v2 --with-embeddings --limit 10000 --dsn postgresql://soundsnap:soundsnap@db:5432/soundsnap
docker compose exec api python /scripts/reindex.py --collection sounds_v2 --only-alias
curl 'http://localhost:8000/search?q=sound%20of%20a%20creaky%20hinge&mode=hybrid'
```

`sounds_v2` adds an auto-embedding field built from `title + description` with Typesense's built-in `ts/all-MiniLM-L12-v2` model (384 dims). The alias `sounds` is switched atomically with a single `upsert`; the API always queries the alias, so no restart or downtime is needed. For the demo only 10,000 documents are embedded (CPU inference is slow); generated sounds are upserted into the active collection and get an embedding automatically.

Measured medians of 5 runs (same query, top 5 titles):

| mode | found | median ms | top hits |
|---|---:|---:|---|
| `keyword` | 2456 | 7 | Tense Soundscape Space, Heavy Gate Knocking, Heavy Door Revolving, … |
| `hybrid` | 2520 | 14 | **Creaking Door Closing, Creaking Entrance Locking, Walking Steps Creaking**, … |

Keyword matching tokens ("sound", "hinge") returns generic ambience; hybrid search surfaces actual creaking-door effects. Filters and facets work unchanged in hybrid mode.

## Production

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Only Caddy publishes ports (80/443 with automatic HTTPS); set `DOMAIN`, `CADDY_EMAIL`, a strong `POSTGRES_PASSWORD` and `TYPESENSE_API_KEY` in `.env` first. The full GCP runbook is in `docs/DEPLOY.md`; it includes a **free-tier demo path** (e2-micro, 10k sounds, one worker, free `sslip.io` hostname) and the standard 200k setup. A billing account is still required for GCP free tier.

## Web UI

A React + Vite + TypeScript client built with Ant Design. Start the API first, then:

```bash
cd ui
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to `http://127.0.0.1:8000`, so no CORS setup is needed. The page supports keyword/hybrid search, category/format/tag/duration filters, audio preview, simulated download and an AI generation modal; the GitHub link is in the top-right corner. Override the repository URL with `VITE_GITHUB_URL` in `ui/.env.local` if you fork it.

```bash
npm run build   # typecheck + production bundle in ui/dist
```

Pinned versions: React 19.3.1, Ant Design 6.7.2, Vite 8.4.0, TypeScript 5.9.3. Vite requires Node 20.19+ or 22.12+.

In the production Compose stack, Caddy serves `ui/dist` at `/`, proxies `/api/*` to FastAPI and keeps `/health` for compatibility.

## Documentation

- `docs/ARCHITECTURE.md` — architecture diagram and write/search paths
- `docs/DECISIONS.md` — decisions and rejected alternatives
- `docs/EXPLAIN_REPORT.md` — Postgres before/after indexes
- `docs/DEPLOY.md` — GCP VM + Compose runbook
- `docs/PERFORMANCE.md` — measured performance and design notes

## Development

Docker Compose reads `docker-compose.override.yml` automatically: db, Typesense and API publish to `127.0.0.1` only, and the API hot-reloads from `./api`. Run scripts inside the API container so they use the pinned Python 3.12 environment.

Use `uv` for local linting (Python 3.12): `uv run --python 3.12 ruff check api/app api/tests scripts db/`.

## Tests

Unit tests cover pure functions only (prompt hashing, format mapping, request validation, local URL signing and the mock generator). Run them from `api/`:

```bash
cd api
uv run --python 3.12 --extra dev pytest -q
```

The end-to-end test is `./scripts/smoke.sh` from the repository root, against a running dev stack. It checks health, search, idempotent generation and that the generated sound is searchable.
