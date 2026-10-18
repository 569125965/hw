#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_API="${BASE_API:-http://127.0.0.1:8000}"

echo "[android-sim] verify native project (Compose, no WebView UI)"
if rg -n "import android.webkit.WebView|android.webkit.WebView\(|WebView\(" "$ROOT/android/app/src" >/dev/null 2>&1; then
  echo "unexpected WebView usage in app source" >&2
  exit 1
fi

test -f "$ROOT/android/app/src/main/java/com/asharelab/app/MainActivity.kt"
test -f "$ROOT/android/app/src/main/java/com/asharelab/app/ui/search/SearchScreen.kt"
test -f "$ROOT/android/app/src/main/java/com/asharelab/app/ui/research/ResearchScreen.kt"
test -f "$ROOT/android/app/src/main/java/com/asharelab/app/ui/chart/CandleChart.kt"
rg -n "Composable|MPAndroidChart|CombinedChart|Signal" "$ROOT/android" >/dev/null
rg -n "短买|中买|ScatterData|DownTriangle" "$ROOT/android/app/src/main/java/com/asharelab/app/ui/chart/CandleChart.kt" >/dev/null

echo "[android-sim] API contract used by Retrofit models"
curl -fsS "$BASE_API/api/v1/health" >/dev/null
curl -fsS "$BASE_API/api/v1/stocks/search?q=600519" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d["items"][0]["code"]=="600519"'
curl -fsS "$BASE_API/api/v1/stocks/600519/research" -o /tmp/android-research.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/android-research.json"))
need = ["quote","kline","fundamental","news","sentiment","forecast"]
for k in need:
    assert k in d and d[k], k
assert "price" in d["quote"]
assert d["kline"]["items"]
assert "signals" in d["kline"]
for s in d["kline"]["signals"]:
    for f in ("cycle","side","pair_id","index","price","label"):
        assert f in s
assert d["forecast"]["actions"]
print("android contract ok", "signals", len(d["kline"]["signals"]))
PY

if [[ -x "$ROOT/android/gradlew" ]] && command -v java >/dev/null 2>&1; then
  echo "[android-sim] assembleDebug"
  (cd "$ROOT/android" && ./gradlew :app:assembleDebug --stacktrace)
else
  echo "[android-sim] Gradle/SDK not available in this environment — structural + API contract checks only"
fi

echo "[ok] android native sim checks passed"
