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

# Python 版本窗
BEST=""
for c in python3.12 python3.13 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    ver="$("$c" -c 'import sys; print("%d.%d"%sys.version_info[:2])' 2>/dev/null || true)"
    minor="${ver#*.}"
    if [[ "${ver%%.*}" == "3" && "$minor" -ge 10 && "$minor" -le 13 ]]; then
      BEST="$c ($ver)"
      break
    fi
  fi
done

if [[ -n "$BEST" ]]; then
  echo "[ok] 可用后端 Python: $BEST"
else
  echo "[miss] 未找到 Python 3.10–3.13（3.14 会导致 pydantic-core 编译失败）"
  echo "       macOS: brew install python@3.12"
  ok=0
fi

if command -v python3 >/dev/null 2>&1; then
  DEF="$(python3 -c 'import sys; print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo "unknown")"
  DEF_MINOR="${DEF#*.}"
  if [[ "${DEF%%.*}" == "3" && "$DEF_MINOR" -gt 13 ]]; then
    echo "[warn] 默认 python3 是 $DEF，不要用它建 venv"
  fi
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
echo "Install missing deps first."
echo "  brew install python@3.12 node"
echo "  rm -rf backend/.venv && ./scripts/start.sh"
exit 1
