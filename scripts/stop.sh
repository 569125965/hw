#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "${ROOT}/.run"

stop_pidfile() {
  local file="$1"
  local pid=""
  if [[ -f "$file" ]]; then
    pid=$(cat "$file" 2>/dev/null || true)
    if [[ -n "$pid" ]]; then
      kill "$pid" 2>/dev/null || true
      pkill -P "$pid" 2>/dev/null || true
      sleep 0.3
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
  fi
}

stop_pidfile "${ROOT}/.run/api.pid"
stop_pidfile "${ROOT}/.run/web.pid"

free_port() {
  local port="$1"
  local pids=""
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      kill -9 $pids 2>/dev/null || true
    fi
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
  fi
}

free_port 8000
free_port 5173
for p in 5174 5175 5176 5177 5178; do
  free_port "$p"
done

echo "[ok] stopped"
