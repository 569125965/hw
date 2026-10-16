#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# 默认实盘；仅 --demo 强制演示数据
DEMO=0
for arg in "$@"; do
  case "$arg" in
    --demo) DEMO=1 ;;
    --live) DEMO=0 ;;
  esac
done

mkdir -p "$ROOT/data" "$ROOT/.run" "$ROOT/backend/.venv"

if [[ ! -x "$ROOT/backend/.venv/bin/python" ]]; then
  python3 -m venv "$ROOT/backend/.venv"
  "$ROOT/backend/.venv/bin/pip" install -U pip
  "$ROOT/backend/.venv/bin/pip" install -r "$ROOT/backend/requirements.txt"
fi

if [[ ! -d "$ROOT/web/node_modules" ]]; then
  (cd "$ROOT/web" && npm install)
fi

export ASHARE_DEMO_MODE="$DEMO"
export ASHARE_CACHE_TTL="${ASHARE_CACHE_TTL:-300}"

# stop previous if any
"$ROOT/scripts/stop.sh" >/dev/null 2>&1 || true

echo "[start] API on :8000 (ASHARE_DEMO_MODE=$ASHARE_DEMO_MODE)"
nohup "$ROOT/backend/.venv/bin/uvicorn" app.main:app \
  --app-dir "$ROOT/backend" \
  --host 0.0.0.0 --port 8000 \
  > "$ROOT/.run/api.log" 2>&1 &
echo $! > "$ROOT/.run/api.pid"

echo "[start] Web on :5173"
nohup npm --prefix "$ROOT/web" run dev -- --host 0.0.0.0 --port 5173 \
  > "$ROOT/.run/web.log" 2>&1 &
echo $! > "$ROOT/.run/web.pid"

for i in {1..40}; do
  if curl -fsS "http://127.0.0.1:8000/api/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

curl -fsS "http://127.0.0.1:8000/api/v1/health" >/dev/null
echo "[ok] API healthy"
echo "[ok] Web: http://127.0.0.1:5173"
echo "[ok] API docs: http://127.0.0.1:8000/docs"
echo "Logs: $ROOT/.run/api.log , $ROOT/.run/web.log"
