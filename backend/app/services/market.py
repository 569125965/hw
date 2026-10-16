from __future__ import annotations

import logging
from typing import Any

from app.core.cache import cache
from app.core.config import settings
from app.core.demo_data import demo_kline, demo_quote, demo_search
from app.services.indicators import add_indicators, df_to_records, kline_to_df
from app.services.signals import detect_signals

logger = logging.getLogger(__name__)


def search_stocks(q: str) -> list[dict[str, str]]:
    key = f"search:{q.strip().lower()}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    result = demo_search(q)
    if not settings.demo_mode:
        try:
            live = _live_search(q)
            if live:
                result = live
        except Exception as exc:  # noqa: BLE001
            logger.warning("live search failed: %s", exc)

    cache.set(key, result)
    return result


def get_quote(code: str) -> dict[str, Any]:
    code = _normalize_code(code)
    key = f"quote:{code}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    quote = demo_quote(code)
    if not settings.demo_mode:
        try:
            live = _live_quote(code)
            if live:
                quote = live
        except Exception as exc:  # noqa: BLE001
            logger.warning("live quote failed: %s", exc)
            quote["degraded"] = True
            quote["degrade_reason"] = str(exc)
    else:
        quote["degraded"] = True
        quote["degrade_reason"] = "demo_mode"

    cache.set(key, quote)
    return quote


def get_kline(code: str, period: str = "day", limit: int = 180) -> dict[str, Any]:
    code = _normalize_code(code)
    key = f"kline:{code}:{period}:{limit}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    rows = demo_kline(code, days=limit)
    degraded = True
    reason = "demo_mode" if settings.demo_mode else "fallback"
    if not settings.demo_mode:
        try:
            live = _live_kline(code, period=period, limit=limit)
            if live:
                rows = live
                degraded = False
                reason = ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("live kline failed: %s", exc)
            reason = str(exc)

    if period == "week":
        rows = _to_week(rows)

    df = add_indicators(kline_to_df(rows))
    items = df_to_records(df)
    payload = {
        "code": code,
        "period": period,
        "items": items,
        "signals": detect_signals(items),
        "degraded": degraded,
        "degrade_reason": reason,
    }
    cache.set(key, payload)
    return payload


def _normalize_code(code: str) -> str:
    code = (code or "").strip().upper()
    code = code.replace("SH", "").replace("SZ", "").replace(".", "")
    if not code.isdigit():
        # try name search
        hits = search_stocks(code)
        if hits:
            return hits[0]["code"]
    return code.zfill(6)[-6:]


def _to_week(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows
    import pandas as pd

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    ohlc = df.resample("W-FRI").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "amount": "sum",
        }
    ).dropna()
    out = []
    for idx, row in ohlc.iterrows():
        out.append(
            {
                "date": idx.date().isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
                "amount": float(row["amount"]),
            }
        )
    return out


def _live_search(q: str) -> list[dict[str, str]]:
    import akshare as ak

    df = ak.stock_info_a_code_name()
    qn = q.strip()
    mask = df["code"].astype(str).str.contains(qn) | df["name"].astype(str).str.contains(qn)
    sub = df.loc[mask].head(20)
    result = []
    for _, row in sub.iterrows():
        code = str(row["code"]).zfill(6)
        market = "SH" if code.startswith(("5", "6", "9")) else "SZ"
        result.append({"code": code, "name": str(row["name"]), "market": market})
    return result


def _live_quote(code: str) -> dict[str, Any] | None:
    import akshare as ak

    spot = ak.stock_zh_a_spot_em()
    row = spot[spot["代码"].astype(str).str.zfill(6) == code]
    if row.empty:
        return None
    r = row.iloc[0]
    price = float(r["最新价"])
    pre = float(r["昨收"])
    change = price - pre
    return {
        "code": code,
        "name": str(r["名称"]),
        "market": "SH" if code.startswith(("5", "6", "9")) else "SZ",
        "price": price,
        "open": float(r["今开"]),
        "high": float(r["最高"]),
        "low": float(r["最低"]),
        "pre_close": pre,
        "change": round(change, 2),
        "change_pct": round(float(r["涨跌幅"]), 2),
        "volume": int(float(r["成交量"])),
        "amount": float(r["成交额"]),
        "turnover_rate": float(r.get("换手率", 0) or 0),
        "amplitude": float(r.get("振幅", 0) or 0),
        "volume_ratio": float(r.get("量比", 0) or 0),
        "pe_ttm": float(r.get("市盈率-动态", 0) or 0),
        "pb": float(r.get("市净率", 0) or 0),
        "total_mv": float(r.get("总市值", 0) or 0),
        "as_of": str(r.get("更新日期", "")) or None,
        "degraded": False,
    }


def _live_kline(code: str, period: str = "day", limit: int = 180) -> list[dict[str, Any]]:
    import akshare as ak

    symbol = code
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        adjust="qfq",
    )
    if df is None or df.empty:
        return []
    df = df.tail(limit)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "date": str(r["日期"])[:10],
                "open": float(r["开盘"]),
                "high": float(r["最高"]),
                "low": float(r["最低"]),
                "close": float(r["收盘"]),
                "volume": int(float(r["成交量"])),
                "amount": float(r["成交额"]),
            }
        )
    return rows
