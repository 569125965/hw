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

"$ROOT/scripts/stop.sh" >/dev/null 2>&1 || true

VENV_DIR="$ROOT/backend/.venv"
if [[ "$(uname -s)" == "Darwin" ]]; then
  VENV_PY="$VENV_DIR/bin/python"
  VENV_PIP="$VENV_DIR/bin/pip"
else
  VENV_PY="$VENV_DIR/bin/python"
  VENV_PIP="$VENV_DIR/bin/pip"
fi

if [[ ! -x "$VENV_PY" ]]; then
  echo "[start] 创建 Python 虚拟环境..."
  python3 -m venv "$VENV_DIR"
fi

# venv 在但依赖不完整时补装（本地常见问题）
if ! "$VENV_PY" -c "import fastapi, uvicorn, pandas, httpx" >/dev/null 2>&1; then
  echo "[start] 安装后端依赖（首次或依赖缺失）..."
  "$VENV_PY" -m pip install -U pip
  "$VENV_PY" -m pip install -r "$ROOT/backend/requirements.txt"
fi

if [[ ! -d "$ROOT/web/node_modules/vite" ]]; then
  echo "[start] npm install..."
  (cd "$ROOT/web" && npm install)
fi

export ASHARE_DEMO_MODE="$DEMO"
export ASHARE_CACHE_TTL="${ASHARE_CACHE_TTL:-120}"
export PYTHONUNBUFFERED=1

echo "[start] API on :8000 (ASHARE_DEMO_MODE=$ASHARE_DEMO_MODE)"
# 用绝对模块路径，避免 cwd 问题
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
  # 若进程已死，提前失败
  if [[ -f "$ROOT/.run/api.pid" ]]; then
    pid="$(cat "$ROOT/.run/api.pid" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
  fi
  sleep 0.5
done

if [[ "$api_ok" -ne 1 ]]; then
  echo "[err] 后端 API 未启动成功（这就是页面提示「无法连接研究服务」的原因）" >&2
  echo "[err] 请查看日志: $ROOT/.run/api.log" >&2
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

# 自检：前端代理路径
if curl -fsS "http://127.0.0.1:5173/api/v1/health" >/dev/null 2>&1; then
  echo "[ok] 前端代理 /api -> 后端 正常"
else
  echo "[warn] 直接 API 正常，但 Vite 代理 /api 暂不可用；请硬刷新浏览器或重启 start.sh" >&2
fi

echo "[ok] API  http://127.0.0.1:8000/docs"
echo "[ok] Web  http://127.0.0.1:5173"
echo "若浏览器仍报未连接：先 ./scripts/stop.sh 再 ./scripts/start.sh，并用无痕窗口打开 Web"
echo "Logs: $ROOT/.run/api.log , $ROOT/.run/web.log"
