from __future__ import annotations

import logging
from typing import Any

import httpx

from app.providers.eastmoney import HEADERS, market_of, secid

logger = logging.getLogger(__name__)


def fetch_money_flow(code: str, limit: int = 120) -> list[dict[str, Any]]:
    """东财主力资金流日线。字段：主力/超大/大/中/小单净流入。"""
    code = code.zfill(6)
    path = (
        "/api/qt/stock/fflow/kline/get"
        f"?lmt={max(limit, 30)}&klt=101&secid={secid(code)}"
        "&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
    )
    hosts = (
        "https://push2.eastmoney.com",
        "https://push2delay.eastmoney.com",
    )
    payload = None
    last_err: Exception | None = None
    with httpx.Client(
        timeout=20.0,
        headers={**HEADERS, "Referer": "https://data.eastmoney.com/"},
        follow_redirects=True,
    ) as c:
        for host in hosts:
            try:
                r = c.get(host + path)
                r.raise_for_status()
                payload = r.json()
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.warning("money flow %s failed: %s", host, exc)
    if payload is None:
        if last_err:
            raise last_err
        return []
    kl = (((payload or {}).get("data") or {}).get("klines")) or []
    rows: list[dict[str, Any]] = []
    for line in kl[-limit:]:
        parts = str(line).split(",")
        if len(parts) < 6:
            continue
        # date, main, small, mid, large, super
        rows.append(
            {
                "date": parts[0][:10],
                "main_net": float(parts[1]),
                "small_net": float(parts[2]),
                "mid_net": float(parts[3]),
                "large_net": float(parts[4]),
                "super_net": float(parts[5]),
            }
        )
    return rows


def fetch_market_snapshot(code: str) -> dict[str, Any]:
    """个股即时字段补充（失败可空）。"""
    code = code.zfill(6)
    url = (
        "https://push2.eastmoney.com/api/qt/stock/get"
        f"?secid={secid(code)}&fields=f57,f58,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87"
    )
    try:
        with httpx.Client(timeout=12.0, headers=HEADERS, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            d = (r.json() or {}).get("data") or {}
        return {
            "main_net_inflow": d.get("f62"),
            "main_net_ratio": d.get("f184"),
            "market": market_of(code),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("market snapshot failed: %s", exc)
        return {}
