from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

import httpx

from app.providers.eastmoney import HEADERS, market_of

logger = logging.getLogger(__name__)


def get_quote(code: str) -> dict[str, Any]:
    """腾讯行情（换手/量比/市值等字段完整，东财 502 时的主兜底）。"""
    code = code.zfill(6)
    mkt = market_of(code).lower()
    url = f"https://qt.gtimg.cn/q={mkt}{code}"
    with httpx.Client(
        timeout=15.0,
        headers={**HEADERS, "Referer": "https://finance.qq.com/"},
        follow_redirects=True,
    ) as c:
        r = c.get(url)
        r.raise_for_status()
        text = r.text
    match = re.search(r'="([^"]*)"', text)
    if not match or not match.group(1):
        raise RuntimeError(f"empty tencent quote for {code}")
    p = match.group(1).split("~")
    if len(p) < 50:
        raise RuntimeError(f"short tencent quote for {code}")

    def f(i: int, default: float = 0.0) -> float:
        try:
            v = p[i].strip()
            if not v or v == "-":
                return default
            return float(v)
        except Exception:
            return default

    price = f(3)
    pre = f(4)
    # 37 成交额（万元）→ 元；57 也可能是万元带小数
    amount = f(57) * 10000 if f(57) else f(37) * 10000
    # 45 总市值（亿元）→ 元
    total_mv = f(45) * 1e8
    circ_mv = f(44) * 1e8
    turnover = f(38)
    # 腾讯字段：56 多为量比；49 偶发其它比率，优先 56
    volume_ratio = f(56) if f(56) > 0 else f(49)

    return {
        "code": code,
        "name": (p[1] or code).replace(" ", "").replace("\u3000", ""),
        "market": market_of(code),
        "price": price,
        "open": f(5),
        "high": f(33),
        "low": f(34),
        "pre_close": pre,
        "change": round(f(31), 2),
        "change_pct": round(f(32), 2),
        "volume": int(f(6)),
        "amount": amount,
        "turnover_rate": round(turnover, 2),
        "amplitude": round(f(43), 2),
        "volume_ratio": round(volume_ratio, 2),
        "pe_ttm": round(f(39), 2),
        "pb": round(f(46), 2),
        "total_mv": total_mv,
        "circ_mv": circ_mv,
        "as_of": date.today().isoformat(),
        "degraded": False,
        "source": "tencent",
    }
