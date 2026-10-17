#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ok=1

echo "== env check =="
echo "ROOT=$ROOT"

need() {
  if command -v "$1" >/dev/null 2>&1; then
    echo "[ok] $1: $($1 --version 2>&1 | head -1)"
  else
    echo "[miss] $1 not found"
    ok=0
  fi
}

need python3
need node
need npm
need curl

if python3 -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)'; then
  echo "[ok] Python >= 3.10"
else
  echo "[miss] need Python 3.10+"
  ok=0
fi

NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)
if [[ "$NODE_MAJOR" -ge 18 ]]; then
  echo "[ok] Node >= 18"
else
  echo "[miss] need Node.js 18+"
  ok=0
fi

if command -v lsof >/dev/null 2>&1; then
  for p in 8000 5173; do
    if lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "[warn] port $p in use"
    else
      echo "[ok] port $p free"
    fi
  done
fi

echo
if [[ "$ok" -eq 1 ]]; then
  echo "OK. Run:"
  echo "  cd \"$ROOT\" && ./scripts/start.sh"
  exit 0
fi
echo "Install missing deps first. macOS: brew install python@3.12 node"
exit 1
