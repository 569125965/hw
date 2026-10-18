#!/usr/bin/env bash
set -euo pipefail
BASE_API="${BASE_API:-http://127.0.0.1:8000}"
BASE_WEB="${BASE_WEB:-http://127.0.0.1:5173}"

echo "[web-sim] health"
curl -fsS "$BASE_API/api/v1/health" | grep -q ok

echo "[web-sim] search -> research path"
CODE=$(curl -fsS "$BASE_API/api/v1/stocks/search?q=%E8%8C%85%E5%8F%B0" | python3 -c 'import sys,json; print(json.load(sys.stdin)["items"][0]["code"])')
curl -fsS "$BASE_API/api/v1/stocks/$CODE/research" -o /tmp/research.json
python3 <<'PY'
import json
from collections import defaultdict

d = json.load(open("/tmp/research.json"))
assert d["quote"]["price"] > 0
assert d["kline"]["items"]
assert "signals" in d["kline"]
sigs = d["kline"]["signals"]
pairs = defaultdict(list)
for s in sigs:
    pairs[(s["cycle"], s["pair_id"])].append(s["side"])
for key, sides in pairs.items():
    assert sorted(sides) == ["buy", "sell"], key
assert d["forecast"]["stance"]
print("research ok", d["name"], d["forecast"]["stance"], "signals", len(sigs))
PY

echo "[web-sim] fetch web index"
curl -fsS "$BASE_WEB" | grep -q "AShare"
echo "[ok] web sim user path passed"
