#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

"${COMPOSE[@]}" up -d

for service in db typesense api; do
  container="$("${COMPOSE[@]}" ps -q "$service" || true)"
  if [ -z "$container" ]; then
    echo "$service: no container"
    continue
  fi
  status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container")"
  echo "$service: $status"
  if [ "$status" = "unhealthy" ]; then
    docker restart "$container"
    echo "$service: restarted"
  fi
done
