#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "需要安装 Docker" >&2
  exit 1
fi

export ASHARE_DEMO_MODE="${ASHARE_DEMO_MODE:-0}"
mkdir -p "$ROOT/data"

echo "[deploy] build & up"
docker compose -f "$ROOT/docker-compose.yml" up -d --build

echo "[deploy] health wait"
for i in {1..60}; do
  if curl -fsS "http://127.0.0.1:8000/api/v1/health" >/dev/null 2>&1; then
    echo "[ok] API :8000"
    echo "[ok] Web :8080"
    exit 0
  fi
  sleep 2
done

echo "健康检查超时，请查看: docker compose logs" >&2
exit 1
