#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
docker compose -f "$ROOT/docker-compose.yml" down
echo "[ok] compose stopped"
