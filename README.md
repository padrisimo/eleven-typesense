# mini-Soundsnap

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

## Example searches (Phase 2, measured)

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

## Documentation

- `docs/ARCHITECTURE.md` — architecture diagram (Phase 6)
- `docs/DECISIONS.md` — decisions and rejected alternatives
- `docs/EXPLAIN_REPORT.md` — Postgres before/after indexes (Phase 3)
- `docs/DEPLOY.md` — GCP VM + Compose runbook (Phase 6)
- `docs/INTERVIEW_NOTES.md` — talking points with measured numbers (Phase 6)

## Development

Docker Compose reads `docker-compose.override.yml` automatically: db, Typesense and API publish to `127.0.0.1` only, and the API hot-reloads from `./api`. Run scripts inside the API container so they use the pinned Python 3.12 environment.

Use `uv` for local linting (Python 3.12): `uv run --python 3.12 ruff check api/ scripts/ db/`.
