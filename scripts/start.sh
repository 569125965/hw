#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEMO=0
for arg in "$@"; do
  case "$arg" in
    --demo) DEMO=1 ;;
    --live) DEMO=0 ;;
  esac
done

mkdir -p "$ROOT/data" "$ROOT/.run"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[err] 未找到 python3。macOS: brew install python@3.12" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "[err] 未找到 npm。macOS: brew install node" >&2
  exit 1
fi

# 先停干净，避免 5173 被占导致 Vite 跳端口
"$ROOT/scripts/stop.sh" >/dev/null 2>&1 || true

VENV_PY="$ROOT/backend/.venv/bin/python"
VENV_PIP="$ROOT/backend/.venv/bin/pip"
if [[ ! -x "$VENV_PY" ]]; then
  echo "[start] 创建 Python 虚拟环境..."
  python3 -m venv "$ROOT/backend/.venv"
  "$VENV_PIP" install -U pip
  "$VENV_PIP" install -r "$ROOT/backend/requirements.txt"
fi

if [[ ! -d "$ROOT/web/node_modules" ]]; then
  echo "[start] npm install..."
  (cd "$ROOT/web" && npm install)
fi

export ASHARE_DEMO_MODE="$DEMO"
export ASHARE_CACHE_TTL="${ASHARE_CACHE_TTL:-120}"

echo "[start] API on :8000 (ASHARE_DEMO_MODE=$ASHARE_DEMO_MODE)"
nohup "$VENV_PY" -m uvicorn app.main:app \
  --app-dir "$ROOT/backend" \
  --host 0.0.0.0 --port 8000 \
  > "$ROOT/.run/api.log" 2>&1 &
echo $! > "$ROOT/.run/api.pid"

echo "[start] Web on :5173"
nohup npm --prefix "$ROOT/web" run dev -- --host 0.0.0.0 --port 5173 --strictPort \
  > "$ROOT/.run/web.log" 2>&1 &
echo $! > "$ROOT/.run/web.pid"

for i in {1..60}; do
  if curl -fsS "http://127.0.0.1:8000/api/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! curl -fsS "http://127.0.0.1:8000/api/v1/health" >/dev/null 2>&1; then
  echo "[err] API 启动失败，日志:" >&2
  tail -n 40 "$ROOT/.run/api.log" >&2 || true
  exit 1
fi

if ! curl -fsS "http://127.0.0.1:5173/" >/dev/null 2>&1; then
  echo "[err] Web 启动失败，日志:" >&2
  tail -n 40 "$ROOT/.run/web.log" >&2 || true
  exit 1
fi

echo "[ok] API healthy  http://127.0.0.1:8000/docs"
echo "[ok] Web          http://127.0.0.1:5173"
echo "Logs: $ROOT/.run/api.log , $ROOT/.run/web.log"
