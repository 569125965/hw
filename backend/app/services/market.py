from __future__ import annotations

import logging
from typing import Any

from app.core.cache import cache
from app.core.config import settings
from app.core.demo_data import demo_kline, demo_quote, demo_search
from app.providers import eastmoney as em
from app.services.indicators import add_indicators, df_to_records, kline_to_df
from app.services.signals import detect_signals

logger = logging.getLogger(__name__)


def search_stocks(q: str) -> list[dict[str, str]]:
    key = f"search:{q.strip().lower()}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    result: list[dict[str, str]] = []
    if not settings.demo_mode:
        try:
            result = em.search_stocks(q)
        except Exception as exc:  # noqa: BLE001
            logger.warning("live search failed: %s", exc)
            try:
                result = _ak_search(q)
            except Exception as exc2:  # noqa: BLE001
                logger.warning("ak search failed: %s", exc2)

    if not result:
        result = demo_search(q)
        for r in result:
            r["degraded"] = True  # type: ignore[typeddict-item]

    cache.set(key, result)
    return result


def get_quote(code: str) -> dict[str, Any]:
    code = _normalize_code(code)
    key = f"quote:{code}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    quote: dict[str, Any] | None = None
    if not settings.demo_mode:
        try:
            quote = em.get_quote(code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("em quote failed: %s", exc)
            try:
                quote = _ak_quote(code)
            except Exception as exc2:  # noqa: BLE001
                logger.warning("ak quote failed: %s", exc2)

    if quote is None:
        quote = demo_quote(code)
        quote["degraded"] = True
        quote["degrade_reason"] = "demo_fallback"
        quote["source"] = "demo"

    cache.set(key, quote)
    return quote


def get_kline(code: str, period: str = "day", limit: int = 180) -> dict[str, Any]:
    code = _normalize_code(code)
    key = f"kline:{code}:{period}:{limit}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    rows: list[dict[str, Any]] = []
    degraded = False
    reason = ""
    source = "live"

    if not settings.demo_mode:
        try:
            rows = em.get_kline(code, limit=limit)
            source = "live"
        except Exception as exc:  # noqa: BLE001
            logger.warning("live kline failed: %s", exc)
            reason = str(exc)

    if not rows:
        if not settings.demo_mode:
            # 实盘模式下宁可不返回演示K线污染分析；再抛给上层会变空，这里仅在显式 demo 才用
            raise RuntimeError(f"real kline unavailable for {code}: {reason}")
        rows = demo_kline(code, days=limit)
        degraded = True
        reason = reason or "demo_fallback"
        source = "demo"

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
        "source": source,
    }
    cache.set(key, payload)
    return payload


def _normalize_code(code: str) -> str:
    code = (code or "").strip().upper()
    code = code.replace("SH", "").replace("SZ", "").replace(".", "")
    if not code.isdigit():
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
    ohlc = (
        df.resample("W-FRI")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "amount": "sum",
            }
        )
        .dropna()
    )
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


def _ak_search(q: str) -> list[dict[str, str]]:
    import akshare as ak

    df = ak.stock_info_a_code_name()
    qn = q.strip()
    mask = df["code"].astype(str).str.contains(qn) | df["name"].astype(str).str.contains(qn)
    sub = df.loc[mask].head(20)
    result = []
    for _, row in sub.iterrows():
        code = str(row["code"]).zfill(6)
        result.append({"code": code, "name": str(row["name"]), "market": em.market_of(code)})
    return result


def _ak_quote(code: str) -> dict[str, Any]:
    # 用最近两日 K 线合成快照（spot 接口在部分网络不可用）
    rows = em.get_kline(code, limit=5)
    if len(rows) < 2:
        raise RuntimeError("insufficient bars for quote")
    last, prev = rows[-1], rows[-2]
    change = last["close"] - prev["close"]
    return {
        "code": code,
        "name": code,
        "market": em.market_of(code),
        "price": last["close"],
        "open": last["open"],
        "high": last["high"],
        "low": last["low"],
        "pre_close": prev["close"],
        "change": round(change, 2),
        "change_pct": round(change / prev["close"] * 100, 2) if prev["close"] else 0.0,
        "volume": last["volume"],
        "amount": last["amount"],
        "turnover_rate": 0.0,
        "amplitude": round((last["high"] - last["low"]) / prev["close"] * 100, 2) if prev["close"] else 0.0,
        "volume_ratio": 0.0,
        "pe_ttm": 0.0,
        "pb": 0.0,
        "total_mv": 0.0,
        "as_of": last["date"],
        "degraded": False,
        "source": "kline_derived",
    }
