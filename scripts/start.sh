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

# 优先 3.12/3.13/3.11 —— 不要用 3.14（pydantic-core / PyO3 尚不支持）
pick_python() {
  local c
  for c in python3.12 python3.13 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      local ver
      ver="$("$c" -c 'import sys; print("%d.%d"%sys.version_info[:2])' 2>/dev/null || true)"
      if [[ -z "$ver" ]]; then
        continue
      fi
      local major minor
      major="${ver%%.*}"
      minor="${ver#*.}"
      if [[ "$major" -eq 3 && "$minor" -ge 10 && "$minor" -le 13 ]]; then
        echo "$c"
        return 0
      fi
    fi
  done
  return 1
}

if ! PY_CMD="$(pick_python)"; then
  echo "[err] 需要 Python 3.10–3.13（检测到系统可能是 3.14+，会导致 pydantic-core 编译失败）" >&2
  echo "[err] macOS 请执行:" >&2
  echo "  brew install python@3.12" >&2
  echo "  rm -rf backend/.venv" >&2
  echo "  ./scripts/start.sh" >&2
  exit 1
fi

PY_VER="$("$PY_CMD" -c 'import sys; print("%d.%d"%sys.version_info[:2])')"
echo "[start] 使用 $PY_CMD (Python $PY_VER)"

if ! command -v npm >/dev/null 2>&1; then
  echo "[err] 未找到 npm。macOS: brew install node" >&2
  exit 1
fi

"$ROOT/scripts/stop.sh" >/dev/null 2>&1 || true

VENV_DIR="$ROOT/backend/.venv"
VENV_PY="$VENV_DIR/bin/python"

# 若已有 venv 但版本不对（例如 3.14），删掉重建
if [[ -x "$VENV_PY" ]]; then
  CUR="$("$VENV_PY" -c 'import sys; print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo "0.0")"
  CUR_MINOR="${CUR#*.}"
  if [[ "${CUR%%.*}" != "3" || "$CUR_MINOR" -gt 13 || "$CUR_MINOR" -lt 10 ]]; then
    echo "[start] 现有 venv 为 Python $CUR，不兼容，正在重建..."
    rm -rf "$VENV_DIR"
  fi
fi

if [[ ! -x "$VENV_PY" ]]; then
  echo "[start] 创建虚拟环境 ($PY_CMD)..."
  "$PY_CMD" -m venv "$VENV_DIR"
fi

if ! "$VENV_PY" -c "import fastapi, uvicorn, pandas, httpx, pydantic" >/dev/null 2>&1; then
  echo "[start] 安装后端依赖..."
  "$VENV_PY" -m pip install -U pip setuptools wheel
  if ! "$VENV_PY" -m pip install -r "$ROOT/backend/requirements.txt"; then
    echo "[err] 依赖安装失败。若仍提到 pydantic-core / Python 3.14，请改用 3.12：" >&2
    echo "  brew install python@3.12 && rm -rf backend/.venv && ./scripts/start.sh" >&2
    exit 1
  fi
fi

if [[ ! -d "$ROOT/web/node_modules/vite" ]]; then
  echo "[start] npm install..."
  (cd "$ROOT/web" && npm install)
fi

export ASHARE_DEMO_MODE="$DEMO"
export ASHARE_CACHE_TTL="${ASHARE_CACHE_TTL:-120}"
export PYTHONUNBUFFERED=1

echo "[start] API on :8000 (ASHARE_DEMO_MODE=$ASHARE_DEMO_MODE)"
nohup "$VENV_PY" -m uvicorn app.main:app \
  --app-dir "$ROOT/backend" \
  --host 127.0.0.1 --port 8000 \
  > "$ROOT/.run/api.log" 2>&1 &
echo $! > "$ROOT/.run/api.pid"

echo "[start] Web on :5173"
nohup npm --prefix "$ROOT/web" run dev -- --host 127.0.0.1 --port 5173 --strictPort \
  > "$ROOT/.run/web.log" 2>&1 &
echo $! > "$ROOT/.run/web.pid"

api_ok=0
for i in {1..90}; do
  if curl -fsS "http://127.0.0.1:8000/api/v1/health" >/dev/null 2>&1; then
    api_ok=1
    break
  fi
  if [[ -f "$ROOT/.run/api.pid" ]]; then
    pid="$(cat "$ROOT/.run/api.pid" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
  fi
  sleep 0.5
done

if [[ "$api_ok" -ne 1 ]]; then
  echo "[err] 后端 API 未启动成功，日志:" >&2
  tail -n 50 "$ROOT/.run/api.log" >&2 || true
  exit 1
fi

web_ok=0
for i in {1..40}; do
  if curl -fsS "http://127.0.0.1:5173/" >/dev/null 2>&1; then
    web_ok=1
    break
  fi
  sleep 0.5
done

if [[ "$web_ok" -ne 1 ]]; then
  echo "[err] Web 启动失败，日志:" >&2
  tail -n 40 "$ROOT/.run/web.log" >&2 || true
  exit 1
fi

if curl -fsS "http://127.0.0.1:5173/api/v1/health" >/dev/null 2>&1; then
  echo "[ok] 前端代理 /api -> 后端 正常"
else
  echo "[warn] API 正常，但 Vite 代理暂不可用；请硬刷新浏览器" >&2
fi

echo "[ok] API  http://127.0.0.1:8000/docs"
echo "[ok] Web  http://127.0.0.1:5173"
echo "Logs: $ROOT/.run/api.log , $ROOT/.run/web.log"
